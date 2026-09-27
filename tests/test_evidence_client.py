"""Evidence response protocol and metadata at the real HTTP client boundary."""

import io
import json
import urllib.error

import pytest

from bridgetree.clients import GeneratorClient, HTTPTransportError, estimate_evidence_tokens, estimate_tokens
from bridgetree.config import GeneratorConfig
from bridgetree.request_audit import JsonlAuditSink, TransportBudget, request_audit_scope

MESSAGES = [{"role": "user", "content": "Return a JSON object describing the evidence."}]
SCHEMA = {
    "type": "object", "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"], "additionalProperties": False,
}


@pytest.mark.parametrize("text,minimum", [
    ("我之前喜欢茉莉花茶后来不再喜欢" * 20, 300),
    ("🫖" * 30, 40),
    ("source_" + "a" * 300, 103),
    ("!?.;:[]{}", 9),
])
def test_evidence_estimator_accounts_for_unspaced_text_without_replacing_reader_rule(text, minimum):
    assert estimate_evidence_tokens(text) >= minimum
    assert estimate_evidence_tokens(text) >= estimate_tokens(text)
    assert estimate_tokens("我之前喜欢茉莉花茶后来不再喜欢" * 20) == 1
    assert estimate_evidence_tokens("") == 0


def client(**kwargs):
    return GeneratorClient(GeneratorConfig(endpoint="http://fixture.invalid/chat", api_key="fixture", **kwargs))


@pytest.mark.parametrize("protocol", ["plain", "json_object", "json_schema"])
def test_protocol_is_explicit_isolated_and_preserves_raw_metadata(monkeypatch, protocol):
    calls = []
    raw = {
        "id": "chat-7", "usage": {"prompt_tokens": 17, "completion_tokens": 8, "provider_detail": {"x": 1}},
        "choices": [{"message": {"content": ' \n{"ok": true}\n ', "refusal": None}, "finish_reason": "stop"}],
    }

    def post(url, payload, timeout, headers):
        calls.append(payload)
        return raw

    monkeypatch.setattr("bridgetree.clients._post_json", post)
    generator = client(provider_request_params={"response_format": {"type": "json_object"}, "seed": 9})
    result = generator.complete_evidence_messages(
        MESSAGES, max_tokens=333, operation="evidence_map", response_format=protocol,
        json_schema=SCHEMA if protocol == "json_schema" else None,
    )
    assert result == {
        "content": ' \n{"ok": true}\n ', "finish_reason": "stop", "refusal": None,
        "usage": raw["usage"], "response_id": "chat-7", "protocol": protocol, "response_error": None,
    }
    payload = calls[0]
    assert payload["max_tokens"] == 333
    assert payload["seed"] == 9
    assert payload["messages"] == MESSAGES
    if protocol == "plain":
        assert "response_format" not in payload
    elif protocol == "json_object":
        assert payload["response_format"] == {"type": "json_object"}
    else:
        assert payload["response_format"] == {
            "type": "json_schema", "json_schema": {"name": "evidence_map", "strict": True, "schema": SCHEMA},
        }
    generator.answer("query", [])
    assert calls[1]["response_format"] == {"type": "json_object"}
    assert calls[1]["max_tokens"] == 512
    assert generator.config.provider_request_params == {"response_format": {"type": "json_object"}, "seed": 9}


@pytest.mark.parametrize(
    "content,reason,refusal,error",
    [(" ", "length", None, "empty_content"),
     ('{"unfinished":', "length", None, None),
     (None, "stop", "Cannot comply", "nontext_content"),
     ([], None, None, "nontext_content")],
)
def test_incomplete_empty_or_refused_output_keeps_metadata(monkeypatch, content, reason, refusal, error):
    monkeypatch.setattr("bridgetree.clients._post_json", lambda *a, **k: {
        "choices": [{"message": {"content": content, "refusal": refusal}, "finish_reason": reason}],
    })
    result = client().complete_evidence_messages(MESSAGES, max_tokens=5, operation="evidence_map")
    assert result["content"] == content
    assert result["finish_reason"] == reason
    assert result["refusal"] == refusal
    assert result["response_error"] == error
    assert result["usage"] is None
    assert result["response_id"] is None


def test_malformed_chat_envelope_retains_root_metadata(monkeypatch):
    monkeypatch.setattr("bridgetree.clients._post_json", lambda *a, **k: {
        "id": "broken-5", "usage": {"total_tokens": 42}, "choices": [],
    })
    result = client().complete_evidence_messages(MESSAGES, max_tokens=5, operation="evidence_map")
    assert result["response_id"] == "broken-5"
    assert result["usage"] == {"total_tokens": 42}
    assert result["response_error"] == "missing_choices"
    assert result["finish_reason"] is None
    assert result["content"] is None
    with pytest.raises(ValueError, match="no choices"):
        client().complete_messages(MESSAGES, max_tokens=5, operation="evidence_map")


@pytest.mark.parametrize("kwargs", [
    {"response_format": "auto"},
    {"response_format": "json_schema"},
    {"response_format": "json_object", "json_schema": SCHEMA},
    {"response_format": "json_schema", "json_schema": {"type": "array"}},
    {"response_format": "json_schema", "json_schema": {"type": "object", "bad": float("nan")}},
    {"operation": "generation"},
    {"max_tokens": True},
])
def test_bad_protocol_arguments_never_send(monkeypatch, kwargs):
    def post(*a, **k):
        pytest.fail("invalid protocol must not send")

    monkeypatch.setattr("bridgetree.clients._post_json", post)
    args = {"max_tokens": 5, "operation": "evidence_map", **kwargs}
    with pytest.raises(ValueError):
        client().complete_evidence_messages(MESSAGES, **args)


def test_unsupported_protocol_is_not_retried_as_plain(monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(json.loads(request.data))
            raise urllib.error.HTTPError(
                "http://fixture.invalid/chat", 400, "unsupported response_format", {}, io.BytesIO(b"unsupported"),
            )

    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *a: Opener())
    with pytest.raises(HTTPTransportError) as caught:
        client().complete_evidence_messages(
            MESSAGES, max_tokens=5, operation="evidence_map", response_format="json_schema", json_schema=SCHEMA,
        )
    assert caught.value.status_code == 400
    assert len(calls) == 1
    assert calls[0]["response_format"]["type"] == "json_schema"


def test_audit_keeps_finish_protocol_and_usage_without_model_text(monkeypatch, tmp_path):
    class Response:
        status = 200
        headers = {"x-request-id": "http-42"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "id": "chat-42", "usage": {"prompt_tokens": 99, "completion_tokens": 5},
                "choices": [{"finish_reason": "length", "message": {
                    "content": "PRIVATE RAW RESPONSE", "refusal": "PRIVATE REFUSAL",
                }}],
            }).encode()

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *a: Opener())
    path = tmp_path / "audit.jsonl"
    budget = TransportBudget(1)
    with request_audit_scope({}, sink=JsonlAuditSink(path), budget=budget):
        result = client().complete_evidence_messages(
            MESSAGES, max_tokens=5, operation="evidence_map", response_format="json_object",
        )
    assert result["refusal"] == "PRIVATE REFUSAL"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    done = next(event for event in events if event["event"] == "http_attempt_completed")
    assert done["server_request_id"] == "http-42"
    assert done["server_response_id"] == "chat-42"
    assert done["server_finish_reason"] == "length"
    assert done["server_refusal"] is True
    assert done["response_protocol"] == "json_object"
    assert done["server_reported_input_tokens"] == 99
    assert done["server_reported_output_tokens"] == 5
    assert done["token_estimator_id"] == "regex_or_utf8_bytes_div3_v2"
    expected = estimate_evidence_tokens(json.dumps(MESSAGES, ensure_ascii=False))
    expected += estimate_evidence_tokens(json.dumps({"type": "json_object"}, ensure_ascii=False))
    assert done["estimated_input_tokens"] == expected
    assert budget.used == 1
    assert "PRIVATE" not in path.read_text()
