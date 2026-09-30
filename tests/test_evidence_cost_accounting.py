"""Count real native/legacy evidence interfaces independently of the reader."""

import json
from collections import Counter

import pytest

from bridgetree.clients import GeneratorClient
from bridgetree.dependency_experiment import DependencyTaskExecutor, run_dependency_experiment
from bridgetree.request_audit import current_audit_scope


@pytest.mark.parametrize("interface", ["native", "legacy"])
@pytest.mark.parametrize("behavior", ["success", "repair", "invalid_json", "backend_error"])
def test_evidence_attempt_costs_match_requests_and_exclude_reader(
    tmp_path, monkeypatch, interface, behavior
):
    """Exercise production GeneratorClient through the formal result writer.

    Two tasks share one executor so a cumulative service counter cannot be
    mistaken for the second task's own costs. A transport stub counts actual
    calls even when they raise, while all other model services stay offline.
    """
    from test_dependency_experiment import FakeEmbedder, FakeReranker, example, fake_config
    from test_evidence_selection import ScriptedBackend

    scripted = ScriptedBackend()
    calls = []
    plan_attempts = Counter()

    def post(endpoint, payload, timeout, headers):
        scope = current_audit_scope().metadata
        operation = scope["stage"]
        calls.append({"task_id": scope["task_id"], "operation": operation})
        if operation.startswith("evidence_"):
            if behavior == "backend_error":
                raise ValueError("fixture backend failed after receiving evidence request")
            if operation.startswith("evidence_plan"):
                plan_attempts[scope["task_id"]] += 1
            if behavior == "invalid_json" or (
                behavior == "repair"
                and operation == "evidence_plan"
                and plan_attempts[scope["task_id"]] == 1
            ):
                content = "invalid JSON from fixture"
            else:
                content = scripted.complete_messages(
                    payload["messages"], operation=operation, max_tokens=payload["max_tokens"]
                )
        else:
            assert operation == "generation"
            content = "(a) Test answer."
        return {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    monkeypatch.setattr("bridgetree.clients._post_json", post)
    config = fake_config(tmp_path, methods=("evidence_bridge",))
    native = GeneratorClient(config.models.generator)

    class LegacyClient:
        # Deliberately expose only the old evidence interface.
        complete_messages = native.complete_messages
        answer_plan = native.answer_plan

    root = tmp_path / "run"
    run_dependency_experiment(
        config,
        root,
        examples=[example("q1"), example("q2")],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=native if interface == "native" else LegacyClient(),
    )
    outcomes = [json.loads(p.read_text()) for p in (root / "outcomes").glob("*.json")]
    assert len(outcomes) == 2
    for outcome in outcomes:
        task_id = outcome["task"]["task_id"]
        sent = [call for call in calls if call["task_id"] == task_id]
        evidence_attempts = sum(call["operation"].startswith("evidence_") for call in sent)
        reader_attempts = sum(call["operation"] == "generation" for call in sent)
        costs = outcome["costs"]
        artifact = json.loads((root / "candidate_pool" / f"{task_id}.json").read_text())
        requests = artifact["evidence_selection"]["requests"]
        assert evidence_attempts > 0
        assert len(requests) == evidence_attempts
        assert costs["evidence_calls"] == evidence_attempts
        assert costs["evidence_reasoning"]["evidence_llm_calls"] == evidence_attempts
        assert costs["adapter_invocations"]["evidence_adapter_invocations"] == evidence_attempts
        assert costs["adapter_invocations"]["generator_adapter_invocations"] == reader_attempts
        assert outcome["diagnostics"]["evidence_bridge_summary"]["costs"]["evidence_calls"] == evidence_attempts
        if behavior in {"success", "repair"}:
            assert outcome["status"] == "success", outcome.get("error")
            assert costs["generator_calls"] == reader_attempts == 1
            assert costs["evidence_reasoning"]["evidence_json_repairs"] == (behavior == "repair")
        else:
            assert outcome["status"] == "error"
            assert reader_attempts == 0
            assert costs.get("generator_calls", 0) == 0
            expected = (
                1 if behavior == "backend_error"
                else 1 + config.evidence_bridge.selection.max_repairs_per_request
            )
            assert evidence_attempts == expected
            if behavior == "backend_error":
                assert requests[0]["failure_category"] == "service_or_backend"


def test_evidence_summary_uses_saved_selector_costs_when_adapter_snapshot_is_missing(tmp_path):
    """A partial artifact without adapter deltas must not report zero work."""
    from test_dependency_experiment import FakeEmbedder, FakeGenerator, FakeReranker, fake_config

    executor = DependencyTaskExecutor(
        fake_config(tmp_path, methods=("evidence_bridge",)),
        embedder=FakeEmbedder(), reranker=FakeReranker(), generator=FakeGenerator(),
    )
    selection = {"costs": {"evidence_llm_calls": 3}, "selected_ids": [], "requests": [{}, {}, {}]}

    class SelectorSnapshot:
        def partial_public_dict(self):
            return selection

    executor._active_evidence_selector = SelectorSnapshot()
    artifacts = {}
    executor._attach_evidence_details(artifacts)
    assert artifacts["costs"]["evidence_calls"] == 3
    assert artifacts["costs"]["evidence_reasoning"]["evidence_llm_calls"] == 3
    # Do not fabricate observed reader calls or overwrite adapter evidence.
    assert "generator_calls" not in artifacts["costs"]
    assert "adapter_invocations" not in artifacts["costs"]
