import io
import json
import urllib.error

import pytest

from bridgetree.clients import GeneratorClient, HTTPTransportError, RerankerClient, _post_json
from bridgetree.config import GeneratorConfig, RerankerConfig
from bridgetree.dependency_scoring import SetReranker
from bridgetree.request_audit import AuditWriteError, JsonlAuditSink, TransportBudget, TransportBudgetExceeded, request_audit_scope
from bridgetree.types import Memory


class Response:
    status = 200
    headers = {"x-request-id": "server-123"}
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.value).encode()


def setup_opener(monkeypatch, callback):
    calls = []
    class Opener:
        def open(self, request, timeout):
            payload = json.loads(request.data)
            calls.append(payload)
            return callback(payload)
    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *args: Opener())
    monkeypatch.setattr("bridgetree.clients.time.sleep", lambda *_: None)
    return calls


def test_durable_pre_call_and_null_real_tokens_without_payload_or_credentials(monkeypatch, tmp_path):
    path = tmp_path / "requests.jsonl"
    def respond(payload):
        on_disk = [json.loads(line) for line in path.read_text().splitlines()]
        assert on_disk[-1]["event"] == "http_attempt_started"
        return Response({"choices": [{"message": {"content": "(a)"}}]})
    calls = setup_opener(monkeypatch, respond)
    events = []
    disk = JsonlAuditSink(path)
    def sink(event):
        events.append(event)
        disk(event)
    with request_audit_scope({"task_id": "task", "phase": "diagnostic", "authorization": "secret"}, sink=sink, budget=TransportBudget(1)):
        client = GeneratorClient(GeneratorConfig("http://private", api_key="sk-123456789secret"))
        assert client.answer("PRIVATE PERSONAL TEXT", []) == "(a)"
    assert len(calls) == 1
    assert sum(event["event"] == "model_call_started" for event in events) == 1
    complete = next(event for event in events if event["event"] == "http_attempt_completed")
    assert complete["server_reported_input_tokens"] is None
    assert complete["server_request_id"] == "server-123"
    output = path.read_text()
    assert all(value not in output for value in ("PRIVATE PERSONAL TEXT", "http://private", "sk-123456789secret", "authorization"))


def test_server_usage_is_not_replaced_by_local_estimates(monkeypatch):
    setup_opener(monkeypatch, lambda _: Response({"usage": {"prompt_tokens": 321, "completion_tokens": 7}}))
    events = []
    with request_audit_scope({}, sink=events.append):
        _post_json("http://private", {"input": ["one"]}, 1)
    complete = next(x for x in events if x["event"] == "http_attempt_completed")
    assert complete["server_reported_input_tokens"] == 321
    assert complete["server_reported_output_tokens"] == 7
    assert complete["server_token_source"] == "response.usage"


def test_split_failed_singleton_has_original_indices_and_set_ids(monkeypatch):
    def respond(payload):
        docs = payload["documents"]
        if len(docs) == 2 or "bad memory" in docs[0]:
            raise urllib.error.HTTPError("http://private", 500, "secret raw server error", {}, io.BytesIO(b"private traceback"))
        return Response({"results": [{"index": 0, "relevance_score": .8}]})
    calls = setup_opener(monkeypatch, respond)
    events = []
    budget = TransportBudget(6)
    client = RerankerClient(RerankerConfig("http://private"))
    scorer = SetReranker("q", {"a": Memory("a", "good memory", 1, "s"), "b": Memory("b", "bad memory", 2, "s")}, client, set_budget=2)
    with request_audit_scope({"task_id": "task", "task_attempt": 3}, sink=events.append, budget=budget):
        with pytest.raises(HTTPTransportError):
            scorer.score_sets([["a"], ["b"]], reason="selection")
    assert len(calls) == budget.used == 6  # unchanged: parent 4 + child 1 + child 1
    assert sum(x["event"] == "model_call_started" for x in events) == 1
    starts = [x for x in events if x["event"] == "http_attempt_started"]
    assert [x["original_document_indices"] for x in starts] == [[0, 1]] * 4 + [[0], [1]]
    assert starts[-1]["documents"][0]["set_ids"] == ["b"]
    assert starts[-1]["parent_request_id"] == starts[0]["request_id"]
    assert starts[-1]["request_hash"] != starts[0]["request_hash"]
    assert starts[-1]["logical_request_hash"] == starts[0]["logical_request_hash"]
    assert starts[-1]["stage"] == "selection"
    assert events[-1]["event"] == "model_call_failed"
    assert all("bad memory" not in json.dumps(x) for x in events)
    # PR1 deliberately preserves failure semantics and does not cache partial results.
    assert scorer.scored_sets == 2
    assert scorer.events == []


def test_transport_budget_is_shared_by_retries_splits_and_resume(monkeypatch):
    def fail(_):
        raise urllib.error.HTTPError("http://private", 500, "failed", {}, None)
    calls = setup_opener(monkeypatch, fail)
    events = []
    budget = TransportBudget(5, used=3)
    with request_audit_scope({}, sink=events.append, budget=budget):
        with pytest.raises(TransportBudgetExceeded):
            RerankerClient(RerankerConfig("http://private")).rerank_all("q", ["a", "b"])
    assert len(calls) == 2
    assert budget.used == 5
    assert len([x for x in events if x["event"] == "http_attempt_started"]) == 2
    assert any(x["event"] == "http_budget_exhausted" for x in events)


def test_budget_exhaustion_after_successful_split_child_never_sends_next_child(monkeypatch):
    def respond(payload):
        if len(payload["documents"]) > 1:
            raise urllib.error.HTTPError("http://private", 500, "failed", {}, None)
        return Response({"results": [{"index": 0, "relevance_score": .8}]})
    calls = setup_opener(monkeypatch, respond)
    events = []
    with request_audit_scope({}, sink=events.append, budget=TransportBudget(5)):
        with pytest.raises(TransportBudgetExceeded):
            RerankerClient(RerankerConfig("http://private")).rerank_all("q", ["a", "b"])
    assert len(calls) == 5  # four parent attempts and one left child
    denied = next(x for x in events if x["event"] == "http_budget_exhausted")
    assert denied["original_document_indices"] == [1]
    assert denied["parent_request_id"] is not None


def test_audit_write_failure_does_not_send_or_retry(monkeypatch):
    calls = setup_opener(monkeypatch, lambda _: Response({"ok": True}))
    def fail(_):
        raise OSError("disk full")
    with request_audit_scope({}, sink=fail):
        with pytest.raises(AuditWriteError):
            _post_json("http://private", {"input": ["text"]}, 1)
    assert calls == []


def test_success_event_write_failure_does_not_resend(monkeypatch):
    calls = setup_opener(monkeypatch, lambda _: Response({"ok": True}))
    def sink(event):
        if event["event"] == "http_attempt_completed":
            raise OSError("disk full")
    with request_audit_scope({}, sink=sink):
        with pytest.raises(AuditWriteError):
            _post_json("http://private", {"input": ["text"]}, 1)
    assert len(calls) == 1


def test_nested_scopes_do_not_leak_task_identity(monkeypatch):
    setup_opener(monkeypatch, lambda _: Response({"ok": True}))
    events = []
    with request_audit_scope({"task_id": "outer"}, sink=events.append):
        with request_audit_scope({"task_id": "inner"}):
            _post_json("http://private", {"input": ["a"]}, 1)
        _post_json("http://private", {"input": ["b"]}, 1)
    starts = [x for x in events if x["event"] == "http_attempt_started"]
    assert [x["task_id"] for x in starts] == ["inner", "outer"]


@pytest.mark.parametrize("reason,stage", [("diagnostic_fresh_all", "score"), ("dense_rerank", "dense_rerank"), ("activation", "dependency_search"), ("selection", "selection"), ("selection_round", "selection")])
def test_scorer_stage_and_objective_metadata_do_not_claim_validated_utility(monkeypatch, reason, stage):
    setup_opener(monkeypatch, lambda _: Response({"results": [{"index": 0, "relevance_score": .6}]}))
    scorer = SetReranker("q", {"a": Memory("a", "text", 1, "s")}, RerankerClient(RerankerConfig("http://private")))
    events = []
    with request_audit_scope({"stage": "parent"}, sink=events.append):
        assert scorer.score_sets([["a"]], reason=reason) == [.6]
    start = next(x for x in events if x["event"] == "http_attempt_started")
    assert start["stage"] == stage
    assert start["objective_semantics"] == "legacy_query_relevance"
    assert start["utility_validation_id"] is None
    assert start["documents"][0]["set_ids"] == ["a"]
    assert scorer.cost["objective_semantics"] == "legacy_query_relevance"
