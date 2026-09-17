import io
import json
import urllib.error

import pytest

from bridgetree.clients import HTTPTransportError, RerankerClient
from bridgetree.config import RerankerConfig
from bridgetree.dependency_experiment import _is_retryable_infrastructure_failure
from bridgetree.request_audit import request_audit_scope


class Response(io.BytesIO):
    status = 200
    headers = {}

    def __init__(self, body):
        super().__init__(json.dumps(body).encode())


def install_opener(monkeypatch, callback):
    calls = []

    class Opener:
        def open(self, request, timeout):
            payload = json.loads(request.data) if not isinstance(request, str) else None
            calls.append(payload)
            return callback(payload)

    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *a: Opener())
    monkeypatch.setattr("bridgetree.clients.time.sleep", lambda _: None)
    return calls


@pytest.mark.parametrize("status,code", [(413, "input_capacity_exceeded"), (502, "score_unavailable")])
def test_structured_errors_stop_without_splitting_or_outer_retry(monkeypatch, status, code):
    def fail(payload):
        body = {
            "detail": {
                "code": code,
                "retryable": False,
                "input_tokens": 9000,
                "reserved_output_tokens": 1,
                "effective_max_model_len": 8192,
                "token_count_source": "submitted_prompt_token_ids",
                "message": "secret query and Bearer credential",
            }
        }
        raise urllib.error.HTTPError("http://test", status, "failed", {}, io.BytesIO(json.dumps(body).encode()))

    calls = install_opener(monkeypatch, fail)
    events = []
    with request_audit_scope(sink=events.append), pytest.raises(HTTPTransportError) as caught:
        RerankerClient(RerankerConfig("http://test")).rerank_all("q", ["a", "b"])
    assert len(calls) == 1
    assert not caught.value.batch_reducible
    assert not _is_retryable_infrastructure_failure(caught.value)
    assert caught.value.error_metadata["actual_input_tokens"] == 9000
    assert "secret query" not in json.dumps(events)
    assert any(e.get("service_error_code") == code for e in events)


def test_unknown_singleton_500_exhausts_once_without_claiming_permanent_input_error(monkeypatch):
    def fail(payload):
        raise urllib.error.HTTPError("http://test", 500, "failed", {}, io.BytesIO(b"Internal Server Error"))

    calls = install_opener(monkeypatch, fail)
    with pytest.raises(HTTPTransportError) as caught:
        RerankerClient(RerankerConfig("http://test")).rerank_all("q", ["a"])
    assert len(calls) == 4
    assert caught.value.retryable  # Error category remains potentially transient.
    assert caught.value.retry_budget_exhausted
    assert not _is_retryable_infrastructure_failure(caught.value)


def test_timeout_does_not_duplicate_a_possibly_running_batch(monkeypatch):
    def fail(payload):
        raise urllib.error.URLError(TimeoutError())

    calls = install_opener(monkeypatch, fail)
    with pytest.raises(HTTPTransportError) as caught:
        RerankerClient(RerankerConfig("http://test")).rerank_all("q", ["a", "b"])
    assert len(calls) == 1
    assert caught.value.error_metadata["server_execution_unknown"] is True
    assert not _is_retryable_infrastructure_failure(caught.value)


def test_proxy_wrapped_timeout_also_does_not_duplicate(monkeypatch):
    def fail(payload):
        body = {"detail": {"code": "proxy_internal_error", "retryable": None, "error_type": "TimeoutError"}}
        raise urllib.error.HTTPError("http://test", 500, "failed", {}, io.BytesIO(json.dumps(body).encode()))

    calls = install_opener(monkeypatch, fail)
    with pytest.raises(HTTPTransportError) as caught:
        RerankerClient(RerankerConfig("http://test")).rerank_all("q", ["a", "b"])
    assert len(calls) == 1
    assert caught.value.retryable
    assert not caught.value.batch_reducible
    assert caught.value.error_metadata["server_execution_unknown"] is True


def test_small_batches_preserve_documents_and_global_ranking(monkeypatch):
    docs = ["complete document " + str(i) for i in range(9)]

    def score(payload):
        return Response(
            {
                "results": [
                    {"index": i, "relevance_score": docs.index(doc) / 10} for i, doc in enumerate(payload["documents"])
                ]
            }
        )

    calls = install_opener(monkeypatch, score)
    client = RerankerClient(RerankerConfig("http://test", max_batch_documents=4))
    result = client.rerank("q", docs, 3)
    assert [x.index for x in result] == [8, 7, 6]
    assert [doc for p in calls for doc in p["documents"]] == docs
    assert [len(p["documents"]) for p in calls] == [4, 4, 1]
    assert client.transport_stats["logical_calls"] == 1


def test_partial_batches_never_return_partial_selection(monkeypatch):
    def score(payload):
        if payload["documents"] == ["c"]:
            raise TimeoutError()
        return Response({"results": [{"index": i, "score": 0.5} for i in range(2)]})

    calls = install_opener(monkeypatch, score)
    with pytest.raises(HTTPTransportError):
        RerankerClient(RerankerConfig("http://test", max_batch_documents=2)).rerank_all("q", ["a", "b", "c"])
    assert len(calls) == 2


def test_required_capacity_mismatch_prevents_scoring(monkeypatch):
    calls = install_opener(monkeypatch, lambda _: Response({"effective_max_model_len": 4096}))
    with pytest.raises(ValueError, match="capacity contract"):
        RerankerClient(RerankerConfig("http://test/rerank", required_max_model_len=8192)).rerank_all("q", ["a"])
    assert calls == [None]


def test_service_enforcement_is_distinct_from_local_exact_counts(monkeypatch):
    health = {
        "declared_max_model_len": 8192,
        "backend_max_model_len": 8192,
        "effective_max_model_len": 8192,
        "reserved_output_tokens": 1,
        "truncation_policy": "reject_without_truncation",
        "token_count_source": "submitted_prompt_token_ids",
    }
    calls = install_opener(
        monkeypatch, lambda p: Response(health if p is None else {"results": [{"index": 0, "score": 0.5}]})
    )
    client = RerankerClient(RerankerConfig("http://test/rerank", required_max_model_len=8192))
    events = []
    with request_audit_scope(sink=events.append):
        client.rerank_all("q", ["a"])
    contract = client.verify_capacity_contract()
    assert contract["capacity_verification"] == "server_enforced"
    assert contract["actual_input_tokens"] is None
    assert len(calls) == 2
    assert any(e.get("capacity_verification") == "server_enforced" for e in events)
