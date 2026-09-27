"""Local HTTP acceptance for the deployment's explicit protocol smoke check."""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from bridgetree.clients import HTTPTransportError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def endpoint():
    state = {"requests": [], "http_status": 200, "finish_reason": "stop", "content": json.dumps({
        "requirements": [{
            "id": "r1", "description": "The tea preference stated last spring",
            "necessary": True, "time_scope": "last spring",
        }],
    })}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(state["http_status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "id": "probe-response", "usage": {"prompt_tokens": 101, "completion_tokens": 19},
                "choices": [{"finish_reason": state["finish_reason"], "message": {"content": state["content"]}}],
            }).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/chat", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "probe_evidence_protocol", ROOT / "scripts/probe_evidence_protocol.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("protocol", ["plain", "json_object", "json_schema"])
def test_probe_same_config_and_http_protocol_without_secrets(endpoint, tmp_path, monkeypatch, capsys, protocol):
    url, state = endpoint
    secret = "TEST_CREDENTIAL_MUST_NOT_APPEAR"
    monkeypatch.setenv("BRIDGETREE_CHAT_API_KEY", secret)
    override = tmp_path / "deployment.yaml"
    override.write_text(json.dumps({
        "models": {"generator": {"endpoint": url, "model": "probe-fixture"}},
        "evidence_bridge": {"selection": {"response_format": protocol}},
    }))
    output = tmp_path / "state" / "probe.json"
    assert load_probe().main([
        "--config", str(ROOT / "configs/evidence_bridge.yaml"), "--override-config", str(override),
        "--output", str(output),
    ]) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "passed"
    assert report["scope"] == "deployment_preflight"
    assert report["experiment_task"] is False
    assert report["logical_calls"] == report["transport_attempts"] == len(state["requests"]) == 1
    assert report["configured_response_format"] == report["response_format"] == protocol
    assert report["response_metadata"]["server_finish_reason"] == "stop"
    assert report["response_metadata"]["server_reported_input_tokens"] == 101
    if protocol == "plain":
        assert "response_format" not in state["requests"][0]
    else:
        assert state["requests"][0]["response_format"]["type"] == protocol
    assert secret not in capsys.readouterr().out
    assert secret not in output.read_text()


@pytest.mark.parametrize("failure", ["http_rejection", "malformed_json", "output_length"])
def test_probe_fails_before_run_without_repairs_or_fallback(endpoint, tmp_path, capsys, failure):
    url, state = endpoint
    if failure == "http_rejection":
        state["http_status"] = 400
    elif failure == "malformed_json":
        state["content"] = "invalid JSON"
    else:
        state["finish_reason"] = "length"
    override = tmp_path / "deployment.yaml"
    override.write_text(json.dumps({"models": {"generator": {"endpoint": url}}}))
    assert load_probe().main([
        "--config", str(ROOT / "configs/evidence_bridge.yaml"), "--override-config", str(override),
        "--response-format", "json_object",
    ]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["logical_calls"] == report["transport_attempts"] == len(state["requests"]) == 1
    assert state["requests"][0]["response_format"] == {"type": "json_object"}
    assert report["protocol_fallback"] is False
    assert report["error_type"]
    if failure == "http_rejection":
        assert report["http_status"] == 400
        assert report["cause_type"] == "HTTPError"
        assert report["attempts"] == 1


@pytest.mark.parametrize("cause,expected", [("URLError", "URLError"), ("Bearer PRIVATE_RESPONSE", None)])
def test_probe_reports_only_safe_transport_cause_and_attempt_count(monkeypatch, cause, expected):
    probe = load_probe()

    def failure(*_args, **_kwargs):
        raise HTTPTransportError(attempts=4, status_code=None, retryable=True, cause_type=cause)

    monkeypatch.setattr(probe.EvidenceSelector, "plan", failure)
    report = probe.probe(str(ROOT / "configs/evidence_bridge.yaml"))
    assert report["status"] == "failed"
    assert report["error_type"] == "HTTPTransportError"
    assert report["cause_type"] == expected
    assert report["attempts"] == 4
    assert "PRIVATE_RESPONSE" not in json.dumps(report)
