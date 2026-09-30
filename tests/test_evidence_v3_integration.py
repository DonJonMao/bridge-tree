"""Formal v3 execution against a real local HTTP chat endpoint, no model fees."""

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bridgetree.clients import GENERATOR_SYSTEM_PROMPT, GeneratorClient
from bridgetree.dependency_experiment import run_dependency_experiment
from bridgetree.diagnostic_observability import ModuleEventRecorder, observation_scope, observe

RAW_HISTORY = "I stopped using paper flashcards because shuffling the large deck took too long."
OPTION_SENTINEL = "OPTION_PRIVATE_SENTINEL"
GOLD_SENTINEL = "GOLD_PRIVATE_SENTINEL"


@pytest.fixture
def chat_endpoint(monkeypatch):
    monkeypatch.delenv("BRIDGETREE_HTTP_FIXTURE_API_KEY", raising=False)
    state = {"requests": [], "mode": "normal", "selected_ids": [], "server_errors": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                messages = request["messages"]
                if messages[0]["content"] == GENERATOR_SYSTEM_PROMPT:
                    operation = "generation"
                    content = "(a) The large deck took too long to shuffle."
                else:
                    payload = json.loads(messages[1]["content"])
                    if "max_requirements" in payload:
                        operation = "evidence_plan"
                        content = {"requirements": [{
                            "id": "r1", "description": "The user's prior experience with paper flashcards",
                            "necessary": True, "time_scope": "earlier learning experience",
                        }]}
                    elif "units" in payload:
                        operation = "evidence_map"
                        # A deliberately wrong semantic irrelevance decision is
                        # valid JSON with complete source-unit assessment.
                        content = {"units": [{
                            "unit_id": unit["unit_id"], "assessments": [],
                            "irrelevance_reason": "No matching preference found in this unit.",
                        } for unit in payload["units"]]}
                    else:
                        operation = "evidence_select_repair" if "repair_scope" in payload else "evidence_select"
                        if state["mode"] == "unknown_id":
                            chosen = ["memory_that_was_never_supplied"]
                        elif "repair_scope" in payload:
                            chosen = list(payload["repair_scope"]["selected_ids"])
                        else:
                            chosen = [row["memory_id"] for row in payload["raw_memory_candidates"]
                                      if RAW_HISTORY in row["text"]]
                            state["selected_ids"] = chosen
                        content = {
                            "selected_ids": chosen,
                            "coverage": [{
                                "requirement_id": "r1",
                                # Invalid covered-without-evidence persists
                                # across the bounded annotation-only repairs.
                                "status": "covered" if state["mode"] == "unassessed" else "missing",
                                "evidence_ids": [], "kind": "explicit",
                                "explanation": "Original history is useful despite the mapper's empty ledger.",
                            }],
                            "conflicts": [], "reason": "The original history is useful to the reader.",
                        }
                    content = json.dumps(content)
                state["requests"].append({"operation": operation, "payload": request})
                response = {
                    "id": f"local-chat-{len(state['requests'])}",
                    "usage": {"prompt_tokens": 101, "completion_tokens": 23, "total_tokens": 124},
                    "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                }
                status = 200
            except Exception as exc:
                state["server_errors"].append(str(exc))
                response, status = {"error": "local fixture rejected malformed request"}, 400
            encoded = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

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


def run_local(tmp_path, chat_endpoint, mode):
    from test_dependency_experiment import FakeEmbedder, FakeReranker, example, fake_config

    url, state = chat_endpoint
    state["mode"] = mode
    config = fake_config(tmp_path, methods=("evidence_bridge",))
    chat = replace(config.models.generator, endpoint=url, model="local-http-fixture",
                   api_key="test-only-key", api_key_env="BRIDGETREE_HTTP_FIXTURE_API_KEY", timeout_seconds=5)
    config = replace(
        config,
        app=replace(config.app, models=replace(config.models, generator=chat)),
        evidence_bridge=replace(config.evidence_bridge, selection=replace(
            config.evidence_bridge.selection,
            max_feedback_rounds=0, max_repairs_per_request=2, max_json_repairs=2,
            raw_memory_review=True, allow_unassessed_coverage=True,
        )),
    )
    item = replace(
        example(gold=f"(a) {GOLD_SENTINEL}", options=f'["(a) {OPTION_SENTINEL}", "(b) Other"]'),
        query="Why did I switch away from paper flashcards?",
        messages=[
            {"role": "user", "content": RAW_HISTORY},
            {"role": "assistant", "content": "You could consider digital flashcards."},
            {"role": "user", "content": "I enjoy listening to music when I walk."},
            {"role": "assistant", "content": "A playlist may help."},
        ],
    )
    embedder, reranker = FakeEmbedder(), FakeReranker()
    client = GeneratorClient(chat)
    root = tmp_path / "run"
    kwargs = {"examples": [item], "embedder": embedder, "reranker": reranker, "generator": client}
    run_dependency_experiment(config, root, **kwargs)
    outcome = json.loads(next((root / "outcomes").glob("*.json")).read_text())
    task_id = outcome["task"]["task_id"]
    candidate = json.loads((root / "candidate_pool" / f"{task_id}.json").read_text())
    return config, root, kwargs, outcome, candidate, state


@pytest.mark.parametrize("mode", ["normal", "unassessed"])
def test_raw_zero_mapping_history_reaches_reader_with_auditable_coverage_and_no_resume_calls(
    tmp_path, chat_endpoint, mode
):
    config, root, kwargs, outcome, candidate, state = run_local(tmp_path, chat_endpoint, mode)
    assert not state["server_errors"]
    assert outcome["status"] == "success", outcome.get("error")
    assert outcome["correct"] is True
    selection = candidate["evidence_selection"]
    assert selection["mappings"] == []
    assert selection["eligible_memory_ids"] == []
    assert len(outcome["selected_ids"]) == 1
    assert outcome["selected_ids"] == state["selected_ids"]
    assert set(outcome["selected_ids"]) <= set(selection["baseline_ids"])
    assert set(outcome["selected_ids"]) <= set(selection["raw_review_ids"])
    selected_disposition = next(row for row in selection["candidate_dispositions"] if row["selected"])
    assert selected_disposition["disposition"] == "selected_raw"
    assert selected_disposition["fully_mapped"] is True
    assert selected_disposition["mapped"] is False

    requests = state["requests"]
    evidence = [row for row in requests if row["operation"].startswith("evidence_")]
    readers = [row for row in requests if row["operation"] == "generation"]
    assert len(readers) == 1
    reader_text = json.dumps(readers[0]["payload"]["messages"])
    assert RAW_HISTORY in reader_text
    assert OPTION_SENTINEL in reader_text
    assert OPTION_SENTINEL not in json.dumps(evidence)
    assert GOLD_SENTINEL not in json.dumps(requests)
    costs = outcome["costs"]
    assert costs["evidence_calls"] == costs["evidence_reasoning"]["evidence_llm_calls"] == len(evidence)
    assert costs["adapter_invocations"]["evidence_adapter_invocations"] == len(evidence)
    assert costs["generator_calls"] == costs["adapter_invocations"]["generator_adapter_invocations"] == 1
    assert all(row["response_metadata"]["protocol"] == "plain" for row in selection["requests"])
    assert all(row["response_metadata"]["usage"]["total_tokens"] == 124 for row in selection["requests"])

    summary = json.loads((root / "summary.json").read_text())["methods"][0]["evidence_reliability"]
    validation = "unassessed" if mode == "unassessed" else "complete"
    completion = "coverage_unassessed" if mode == "unassessed" else "normal"
    assert summary["completion_cohorts"][completion]["tasks"] == 1
    assert summary["evidence_state_cohorts"]["raw_only"]["tasks"] == 1
    assert summary["coverage_validation_cohorts"][validation]["tasks"] == 1
    reliability = outcome["diagnostics"]["evidence_bridge_summary"]["reliability"]
    assert reliability["coverage_validation_complete"] is (mode == "normal")
    assert reliability["evidence_empty_context"] is False

    live_text = (root / "modules/events.jsonl").read_text()
    assert RAW_HISTORY not in live_text
    live = [json.loads(line) for line in live_text.splitlines()]
    raw_event = next(row for row in live if row["event"] == "evidence_raw_review_prepared")
    assert set(outcome["selected_ids"]) <= set(raw_event["raw_review_ids"])
    disposition_event = next(row for row in live if row["event"] == "evidence_candidate_dispositions")
    assert any(row["selected"] and row["disposition"] == "selected_raw"
               for row in disposition_event["dispositions"])
    if mode == "unassessed":
        repairs = [row for row in evidence if row["operation"] == "evidence_select_repair"]
        assert len(repairs) == config.evidence_bridge.selection.max_repairs_per_request == 2
        assert selection["coverage"][0]["status"] == "unassessed"
        assert selection["coverage"][0]["kind"] == "unknown"
        assert selection["coverage"][0]["validation_complete"] is False
        assert selection["coverage"][0]["unassessed_error"]
        assert summary["completion_cohorts"]["normal"]["tasks"] == 0
        recovery = next(row for row in live if row["event"] == "evidence_coverage_repair_prepared")
        assert recovery["pending_requirement_ids"] == ["r1"]
        assert recovery["selected_ids"] == outcome["selected_ids"]
        assert recovery["requirements_before"] == recovery["requirements_after"] == 1
        assert recovery["evidence_records_before"] == recovery["evidence_records_after"] == 0
        assert recovery["excluded_evidence_ids"] == []
        degraded = next(row for row in live if row["event"] == "evidence_coverage_unassessed")
        assert degraded["requirement_ids"] == ["r1"]
        assert degraded["failure_category"] == "evidence_relation"
    else:
        assert selection["coverage"][0]["status"] == "missing"
        assert selection["coverage"][0]["validation_complete"] is True
        assert not any(row["event"] == "evidence_coverage_unassessed" for row in live)

    physical = [json.loads(line) for line in (root / "modules/requests.jsonl").read_text().splitlines()]
    assert sum(row["event"] == "http_attempt_completed" for row in physical) == len(requests)
    before = (len(requests), len(kwargs["embedder"].calls), len(kwargs["reranker"].calls))
    resumed = run_dependency_experiment(config, root, resume=True, **kwargs)
    assert resumed["resume_noop"] is True
    assert before == (len(requests), len(kwargs["embedder"].calls), len(kwargs["reranker"].calls))


def test_unknown_selected_source_stays_a_failure_and_never_reaches_reader(tmp_path, chat_endpoint):
    config, root, kwargs, outcome, candidate, state = run_local(tmp_path, chat_endpoint, "unknown_id")
    assert not state["server_errors"]
    assert outcome["status"] == "error"
    assert outcome["error_type"] == "EvidenceValidationError"
    assert "unknown" in outcome["error"]
    assert not any(row["operation"] == "generation" for row in state["requests"])
    assert outcome["costs"]["adapter_invocations"]["generator_adapter_invocations"] == 0
    assert outcome["costs"]["evidence_calls"] == len(state["requests"])
    selection_attempts = [row for row in candidate["evidence_selection"]["requests"]
                          if row["operation"].startswith("evidence_select")]
    assert len(selection_attempts) == 1 + config.evidence_bridge.selection.max_repairs_per_request
    summary = json.loads((root / "summary.json").read_text())["methods"][0]["evidence_reliability"]
    assert summary["successful_tasks"] == 0
    assert summary["failed_tasks"] == 1
    assert summary["completion_cohorts"]["coverage_unassessed"]["tasks"] == 0
    assert summary["failure_cost_metrics"]["evidence_calls"]["sum"] == len(state["requests"])


@pytest.mark.parametrize("category", ["repair_input_budget", "input_budget", "call_budget"])
def test_recovery_budget_failure_categories_survive_live_recording(tmp_path, category):
    with observation_scope(ModuleEventRecorder(tmp_path)):
        observe("selection", "evidence_coverage_unassessed", requirement_ids=["r1"],
                failure_category=category, validation_error="private response text")
    event = json.loads((tmp_path / "modules/selection.jsonl").read_text())
    assert event["failure_category"] == category
    assert event["requirement_ids"] == ["r1"]
    assert "validation_error" not in event
