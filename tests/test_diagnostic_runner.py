"""PR3 integration tests: synthetic data, real clients, mocked HTTP only."""
from __future__ import annotations

import copy
import csv
import io
import json
import tarfile
import urllib.error
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from bridgetree import clients
from bridgetree.diagnostic_config import digest, file_digest
from bridgetree.diagnostic_evaluation import evaluate_diagnostics
from bridgetree.diagnostic_identity import request_hash
from bridgetree import diagnostic_runner as runner
from bridgetree.types import ContextPlan


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("unexpected real network access in diagnostic test")

    monkeypatch.setattr(clients.urllib.request, "build_opener", blocked)
    monkeypatch.setattr(clients.urllib.request, "urlopen", blocked)
    monkeypatch.setattr(clients.time, "sleep", lambda seconds: None)
    # Keep a stable package revision while agents edit unrelated files. The
    # genuine source equality gate still runs, and has its own drift test.
    monkeypatch.setattr(runner, "source_identity", lambda: "synthetic-package-revision-v1")
    monkeypatch.delenv("BRIDGETREE_TEST_DIAGNOSTIC_KEY", raising=False)


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_tar(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, value in members.items():
            data = json.dumps(value).encode()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def _questions(path, answer="(a)"):
    fields = ["question_id", "persona_id", "user_question_or_message", "all_options",
              "shared_context_id", "end_index_in_shared_context", "correct_answer", "answer_explanation"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "question_id": "q-tiny", "persona_id": "persona-tiny",
            "user_question_or_message": "What should I do this weekend?",
            "all_options": json.dumps(["(a) Choice alpha", "(b) Choice beta"]),
            "shared_context_id": "history-tiny", "end_index_in_shared_context": 5,
            "correct_answer": answer, "answer_explanation": "GOLD_ONLY_SENTINEL",
        })


def _fixture(tmp_path, *, repeats=2, universe_size=2, dense=True, control=True,
             task_attempts=2, generation_cap=100, score_cap=100, unknown_role=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    base = yaml.safe_load(Path("configs/default.yaml").read_text())
    for role in ("embedding", "reranker", "generator"):
        base["models"][role]["endpoint"] = f"http://diagnostic-fixture.invalid/{role}"
        base["models"][role]["model"] = f"fake-{role}"
        base["models"][role]["deployment_identity"] = (
            {} if role == unknown_role else {
                "identity_source": "operator_declared", "deployment_revision": f"fixture-{role}-v1",
            }
        )
    base["models"]["generator"]["api_key"] = ""
    base["models"]["generator"]["api_key_env"] = "BRIDGETREE_TEST_DIAGNOSTIC_KEY"
    base["data"].update(split="32k", memory_granularity="user_assistant_pair", include_system_persona=True)
    deployment = tmp_path / "deployment.yaml"
    deployment.write_text(yaml.safe_dump(base), encoding="utf-8")
    questions, contexts = tmp_path / "questions.csv", tmp_path / "contexts.jsonl"
    _questions(questions)
    _write_json(contexts, {"history-tiny": [
        {"role": "system", "content": "A synthetic person."},
        {"role": "user", "content": "I enjoy making music with software."},
        {"role": "assistant", "content": "That sounds enjoyable."},
        {"role": "user", "content": "I play the piano on weekends."},
        {"role": "assistant", "content": "You could practice a new tune."},
        {"role": "user", "content": "FUTURE_ONLY_SENTINEL must remain invisible."},
    ]})
    full, detail = tmp_path / "full.tgz", tmp_path / "detail.tgz"
    _write_tar(full, {"outcomes/dense-task.json": {
        "task": {"question_id": "q-tiny", "method_id": "dense"}, "status": "success",
        "selected_ids": ["q-tiny:m00001", "q-tiny:m00002"],
        "correct": True, "prediction": "GOLD_ARCHIVE_SENTINEL",
    }})
    detail_artifact = {
        "task_id": "activation-task", "method_id": "activation", "schema_version": 1,
        "question_id": "q-tiny",
        "search": {
            "activations": [{"premise_ids": [], "target_id": "q-tiny:m00001",
                             "group_ids": ["q-tiny:m00002"],
                             "P": .1, "Pe": .5, "PG": .4, "PGe": .45,
                             "activation": -.35, "context_marginal": -.05}],
            "bundles": [{"memory_ids": ["q-tiny:m00001"]}, {"memory_ids": ["q-tiny:m00002"]}],
        },
        "selection": {
            "selected_ids": ["q-tiny:m00001"], "initial_scored_sets": 4, "final_scored_sets": 4,
            "stop": {"reason": "no_positive_marginal"},
            "rounds": [
                {"current_ids": [], "accepted_bundle_ids": ["q-tiny:m00001"],
                 "selected_ids_after": ["q-tiny:m00001"], "comparisons": [
                     {"current_ids": [], "bundle_ids": ["q-tiny:m00001"],
                      "union_ids": ["q-tiny:m00001"], "feasible": True,
                      "base_score": .1, "combined_score": .5, "marginal": .4, "accepted": True},
                     {"current_ids": [], "bundle_ids": ["q-tiny:m00002"],
                      "union_ids": ["q-tiny:m00002"], "feasible": True,
                      "base_score": .1, "combined_score": .4, "marginal": .3, "accepted": False}]},
                {"current_ids": ["q-tiny:m00001"], "accepted_bundle_ids": None,
                 "selected_ids_after": ["q-tiny:m00001"], "comparisons": [
                     {"current_ids": ["q-tiny:m00001"], "bundle_ids": ["q-tiny:m00002"],
                      "union_ids": ["q-tiny:m00001", "q-tiny:m00002"], "feasible": True,
                      "base_score": .5, "combined_score": .45, "marginal": -.05, "accepted": False}]},
            ],
        },
    }
    _write_tar(detail, {"candidate_pool/activation-task.json": detail_artifact})
    settings = {
        "schema_version": 1, "deployment_config": str(deployment),
        "detail_archive": {"path": str(detail), "sha256": file_digest(detail)},
        "full_archive": {"path": str(full), "sha256": file_digest(full)},
        "questions": str(questions), "contexts": str(contexts),
        "cases": [{"name": "tiny", "question_id": "q-tiny", "task_id": "activation-task",
                   "universe": [f"m0000{i}" for i in range(1, universe_size + 1)],
                   "controls": ([{"name": "explicit_singleton", "memory_ids": ["m00001"],
                                  "rationale": "predeclared repeated context control"}] if control else [])}],
        "repeats": repeats, "order_seed": 17, "root_seeds": [0, 1],
        "task_max_attempts": task_attempts, "include_dense_controls": dense,
        "budgets": {"score_logical_inputs": 16, "generation_trials": 40,
                    "score_transport_attempts": score_cap, "generation_transport_attempts": generation_cap,
                    "root_runs": 3, "root_transport_attempts": 20},
    }
    config = tmp_path / "diagnostic.yaml"
    config.write_text(yaml.safe_dump(settings), encoding="utf-8")
    return SimpleNamespace(config=config, deployment=deployment, questions=questions, contexts=contexts,
                           full=full, detail=detail, detail_artifact=detail_artifact,
                           settings=settings, run=tmp_path / "run")


class FakeHTTP:
    def __init__(self, *, status=None, interrupt_first=False):
        self.status = status
        self.interrupt_first = interrupt_first
        self.calls = []

    def open(self, request, timeout):
        payload = json.loads(request.data)
        self.calls.append(payload)
        if self.interrupt_first:
            self.interrupt_first = False
            raise KeyboardInterrupt("simulated crash after durable reservation")
        if self.status is not None:
            raise urllib.error.HTTPError(request.full_url, self.status, "synthetic failure", {}, None)
        response = ({"choices": [{"message": {"content": "(a) synthetic answer"}}]}
                    if "messages" in payload else
                    {"results": [{"index": i, "relevance_score": .25} for i in range(len(payload["documents"]))]})
        response["usage"] = {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}
        return _Response(response)


class _Response:
    status = 200
    headers = {"x-request-id": "fixture-server-request"}

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _http(monkeypatch, **kwargs):
    fake = FakeHTTP(**kwargs)
    monkeypatch.setattr(clients.urllib.request, "build_opener", lambda *args, **kwargs: fake)
    return fake


def _all_keys(value):
    if isinstance(value, dict):
        return set(value).union(*( _all_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(v) for v in value))
    return set()


def test_plan_counts_public_projection_and_context_plan_roundtrip_are_offline(tmp_path):
    fixture = _fixture(tmp_path)
    summary = runner.plan_diagnostics(fixture.config, fixture.run)
    manifest = runner.load_manifest(fixture.run)
    assert summary["network_calls"] == 0
    assert summary["counts"] == {"score_logical_inputs": 4, "generation_trials": 12, "root_runs": 3}
    assert summary["unknown_deployments"] == []
    assert summary["eligible_for_benchmark"] is False
    assert manifest["cases"][0]["cutoff"]["end_index"] == 5
    assert {m["memory_id"] for m in manifest["cases"][0]["visible_memories"]} == {
        "q-tiny:m00000", "q-tiny:m00001", "q-tiny:m00002",
    }
    assert not ({"correct_answer", "answer_explanation", "correct", "prediction"} & _all_keys(manifest))
    assert all(marker not in json.dumps(manifest) for marker in (
        "GOLD_ONLY_SENTINEL", "GOLD_ARCHIVE_SENTINEL", "FUTURE_ONLY_SENTINEL",
    ))
    for context in manifest["contexts"]:
        plan = ContextPlan.from_public_dict(context["context_plan"])
        assert plan.public_dict() == context["context_plan"]
        assert request_hash(plan.request_dict()) == context["wire_payload_hash"]
        assert "Choice alpha" in json.dumps(plan.request_dict())
    for item in manifest["score_inputs"]:
        assert "Choice alpha" not in item["document"]
        assert "GOLD" not in item["document"]
    assert runner.plan_diagnostics(fixture.config, fixture.run) == summary


def test_gold_only_edit_changes_evaluation_not_frozen_manifest_or_requests(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    before = runner.load_manifest(fixture.run)
    fake = _http(monkeypatch)
    runner.run_generations(fixture.run, fixture.config, execute=True)
    first = evaluate_diagnostics(fixture.run, fixture.questions)
    assert all(c["successful_accuracy"] == 1.0 for c in first["conditions"])
    _questions(fixture.questions, "(b)")
    runner.plan_diagnostics(fixture.config, fixture.run)
    assert runner.load_manifest(fixture.run) == before
    second = evaluate_diagnostics(fixture.run, fixture.questions)
    assert first["manifest_id"] == second["manifest_id"]
    assert first["gold_source_sha256"] != second["gold_source_sha256"]
    assert all(c["successful_accuracy"] == 0.0 for c in second["conditions"])
    assert len(fake.calls) == before["counts"]["generation_trials"]


@pytest.mark.parametrize("phase", ["score", "generation"])
def test_no_execute_performs_zero_network_and_creates_no_trial_ledger(tmp_path, phase):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    function = runner.run_scores if phase == "score" else runner.run_generations
    summary = function(fixture.run, fixture.config)
    assert summary["execute"] is False and summary["network_calls"] == 0
    assert not (fixture.run / "requests.jsonl").exists()
    assert not (fixture.run / "attempts.jsonl").exists()


@pytest.mark.parametrize("role,phase", [("reranker", "score"), ("generator", "generation")])
def test_unknown_deployment_is_blocked_before_network(tmp_path, role, phase):
    fixture = _fixture(tmp_path, unknown_role=role)
    summary = runner.plan_diagnostics(fixture.config, fixture.run)
    assert role in summary["unknown_deployments"]
    function = runner.run_scores if phase == "score" else runner.run_generations
    with pytest.raises(ValueError, match="unfrozen deployment identity"):
        function(fixture.run, fixture.config, execute=True)
    gate = json.loads((fixture.run / (phase + "_gate.json")).read_text())
    assert gate["status"] == "blocked_before_network" and gate["network_calls"] == 0
    assert not (fixture.run / "requests.jsonl").exists()


def test_source_and_deployment_drift_are_not_bypassed_by_test_fixture(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    monkeypatch.setattr(runner, "source_identity", lambda: "a-different-package-revision")
    with pytest.raises(ValueError, match="source snapshot differs"):
        runner.run_generations(fixture.run, fixture.config, execute=True)
    monkeypatch.setattr(runner, "source_identity", lambda: "synthetic-package-revision-v1")
    deployment = yaml.safe_load(fixture.deployment.read_text())
    deployment["models"]["generator"]["deployment_identity"]["deployment_revision"] = "different-checkpoint"
    fixture.deployment.write_text(yaml.safe_dump(deployment))
    with pytest.raises(ValueError, match="deployment/request settings differ"):
        runner.run_generations(fixture.run, fixture.config, execute=True)


def test_repeats_use_real_client_each_time_bypass_generation_cache_and_resume_once(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch)
    monkeypatch.setattr(clients.GenerationCache, "answer_plan", lambda *args, **kwargs: pytest.fail("generation cache used"))
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert summary["success"] == summary["planned"] == 12
    assert len(fake.calls) == 12
    assert summary["transport_attempts_used"] == 12
    frequencies = Counter(request_hash(p) for p in fake.calls)
    assert max(frequencies.values()) == 4  # subset + explicit identical singleton, each repeated twice
    assert all(n >= 2 for n in frequencies.values())
    requests = runner.read_jsonl(fixture.run / "requests.jsonl")
    starts = [r for r in requests if r["event"] == "http_attempt_started"]
    assert len(starts) == 12 and len({r["task_id"] for r in starts}) == 12
    before = (fixture.run / "attempts.jsonl").read_bytes()
    assert runner.run_generations(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == 12 and (fixture.run / "attempts.jsonl").read_bytes() == before


def test_score_phase_uses_real_client_with_query_only_input_and_resumes(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch)
    summary = runner.run_scores(fixture.run, fixture.config, execute=True)
    assert summary["success"] == 4
    assert len(fake.calls) == 4
    empty_calls = [p for p in fake.calls if "[No personal memories supplied.]" in p["documents"][0]]
    assert len(empty_calls) == 1 and len(empty_calls[0]["documents"]) == 1
    manifest = runner.load_manifest(fixture.run)
    empty_input = next(item for item in manifest["score_inputs"] if not item["memory_ids"])
    empty_result = json.loads((fixture.run / "score" / (empty_input["subset_id"] + ".json")).read_text())
    assert empty_result["score"] == .25  # observed HTTP score, not a fabricated zero baseline
    assert request_hash(empty_calls[0]) == empty_input["wire_payload_hash"]
    assert all("messages" not in p and "Choice alpha" not in json.dumps(p) for p in fake.calls)
    assert all(p["query"] == "What should I do this weekend?" for p in fake.calls)
    assert runner.run_scores(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == 4


def test_terminal_http_errors_are_not_retried_again_on_resume(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, status=400)
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert summary["failed"] == 2 and summary["success"] == 0
    assert len(fake.calls) == 2
    fake.status = None
    assert runner.run_generations(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == 2
    evaluation = evaluate_diagnostics(fixture.run, fixture.questions)
    assert all(c["failed"] == 1 and c["fixed_trial_denominator_accuracy"] == 0.0
               and c["successful_accuracy"] is None for c in evaluation["conditions"])


def test_http_retries_and_task_attempts_have_finite_predeclared_bounds(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False, task_attempts=2)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, status=503)
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 2 * 2 * clients._HTTP_MAX_TRANSPORT_ATTEMPTS
    assert summary["transport_attempts_used"] == len(fake.calls)
    attempts = runner.read_jsonl(fixture.run / "attempts.jsonl")
    assert sum(r["event"] == "task_attempt_started" for r in attempts) == 4
    assert max(r["task_attempt"] for r in attempts) == 2
    before = len(fake.calls)
    runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == before


def test_physical_cap_survives_crash_and_resume_without_resetting_used_slots(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False,
                       task_attempts=2, generation_cap=2)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, interrupt_first=True)
    with pytest.raises(KeyboardInterrupt, match="simulated crash"):
        runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 1
    starts = [r for r in runner.read_jsonl(fixture.run / "requests.jsonl") if r["event"] == "http_attempt_started"]
    assert len(starts) == 1
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert summary["transport_attempts_used"] == summary["transport_attempts_cap"] == 2
    assert len(fake.calls) == 2
    assert summary["success"] == 1 and summary["failed"] == 1
    runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 2


def test_physical_budget_caps_retry_storms_and_terminal_budget_results(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False, generation_cap=3)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, status=503)
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == summary["transport_attempts_used"] == 3
    assert summary["failed"] == 2
    fake.status = None
    runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 3


def test_crashed_task_attempts_exhaust_fixed_limit_even_with_transport_budget_left(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False,
                       task_attempts=2, generation_cap=20)
    runner.plan_diagnostics(fixture.config, fixture.run)
    manifest = runner.load_manifest(fixture.run)
    fake = _http(monkeypatch, interrupt_first=True)
    for _ in range(2):
        fake.interrupt_first = True
        with pytest.raises(KeyboardInterrupt):
            runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 2
    summary = runner.run_generations(fixture.run, fixture.config, execute=True)
    assert summary["success"] == 1 and summary["failed"] == 1
    assert summary["transport_attempts_used"] == len(fake.calls) == 3
    first = manifest["trials"][0]
    result = json.loads((fixture.run / "generation" / (first["trial_id"] + ".json")).read_text())
    assert result["error_type"] == "InterruptedAttempt"
    assert result["task_attempt"] == 2 and result["outcome_unknown"] is True
    runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 3


@pytest.mark.parametrize("phase", ["score", "generation"])
def test_fsynced_completion_is_restored_after_crash_before_outcome_without_reexecution(tmp_path, monkeypatch, phase):
    fixture = _fixture(tmp_path, repeats=2, universe_size=1, dense=False, control=False,
                       task_attempts=2, generation_cap=4, score_cap=2)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch)
    function = runner.run_scores if phase == "score" else runner.run_generations
    real_atomic_json = runner.atomic_json

    def crash_before_outcome(path, value):
        if Path(path).parent == fixture.run / phase:
            raise KeyboardInterrupt("crash after completion fsync but before outcome write")
        return real_atomic_json(path, value)

    monkeypatch.setattr(runner, "atomic_json", crash_before_outcome)
    with pytest.raises(KeyboardInterrupt, match="after completion fsync"):
        function(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == 1
    events = runner.read_jsonl(fixture.run / "attempts.jsonl")
    completed = [e for e in events if e["event"] == "task_attempt_completed"]
    assert len(completed) == 1 and completed[0]["status"] == "success"
    recovered_id = completed[0]["item_id"]
    outcome_path = fixture.run / phase / (recovered_id + ".json")
    assert not outcome_path.exists()
    monkeypatch.setattr(runner, "atomic_json", real_atomic_json)
    summary = function(fixture.run, fixture.config, execute=True)
    expected_count = 2 if phase == "score" else 4
    assert summary["success"] == summary["planned"] == expected_count
    assert len(fake.calls) == summary["transport_attempts_used"] == expected_count
    restored = json.loads(outcome_path.read_text())
    assert restored == {k: v for k, v in completed[0].items() if k not in {"event", "at_epoch"}}
    starts = [e for e in runner.read_jsonl(fixture.run / "attempts.jsonl")
              if e["event"] == "task_attempt_started" and e["item_id"] == recovered_id]
    assert len(starts) == 1 and starts[0]["task_attempt"] == 1
    assert function(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == expected_count


def _crash_after_failure_fsync(monkeypatch):
    real_append_jsonl = runner.append_jsonl

    def append_then_crash(path, value):
        real_append_jsonl(path, value)
        if value.get("event") == "task_attempt_failed":
            raise KeyboardInterrupt("crash after failure fsync but before outcome write")

    monkeypatch.setattr(runner, "append_jsonl", append_then_crash)
    return real_append_jsonl


@pytest.mark.parametrize("phase", ["score", "generation"])
@pytest.mark.parametrize("http_status,task_attempts", [(400, 1), (400, 3), (503, 1)])
def test_fsynced_terminal_failure_is_restored_without_retry_or_error_reclassification(
        tmp_path, monkeypatch, phase, http_status, task_attempts):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False,
                       task_attempts=task_attempts)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, status=http_status)
    function = runner.run_scores if phase == "score" else runner.run_generations
    real_append_jsonl = _crash_after_failure_fsync(monkeypatch)
    with pytest.raises(KeyboardInterrupt, match="after failure fsync"):
        function(fixture.run, fixture.config, execute=True)
    failed = [e for e in runner.read_jsonl(fixture.run / "attempts.jsonl")
              if e["event"] == "task_attempt_failed"]
    assert len(failed) == 1
    event = failed[0]
    assert event["error_type"] == "HTTPTransportError" and event["http_status"] == http_status
    assert event["retryable"] is (http_status == 503)
    outcome_path = fixture.run / phase / (event["item_id"] + ".json")
    assert not outcome_path.exists()
    failed_call_count = len(fake.calls)
    monkeypatch.setattr(runner, "append_jsonl", real_append_jsonl)
    fake.status = None
    summary = function(fixture.run, fixture.config, execute=True)
    assert summary["success"] == 1 and summary["failed"] == 1
    assert len(fake.calls) == summary["transport_attempts_used"] == failed_call_count + 1
    restored = json.loads(outcome_path.read_text())
    assert restored == {k: v for k, v in event.items() if k not in {"event", "at_epoch"}}
    assert restored["task_attempt"] == 1 and restored["error_type"] != "InterruptedAttempt"
    starts = [e for e in runner.read_jsonl(fixture.run / "attempts.jsonl")
              if e["event"] == "task_attempt_started" and e["item_id"] == event["item_id"]]
    assert len(starts) == 1
    assert function(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == failed_call_count + 1


@pytest.mark.parametrize("phase", ["score", "generation"])
def test_fsynced_retryable_failure_with_budget_remaining_continues_next_attempt(tmp_path, monkeypatch, phase):
    fixture = _fixture(tmp_path, repeats=1, universe_size=1, dense=False, control=False, task_attempts=3)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch, status=503)
    function = runner.run_scores if phase == "score" else runner.run_generations
    real_append_jsonl = _crash_after_failure_fsync(monkeypatch)
    with pytest.raises(KeyboardInterrupt, match="after failure fsync"):
        function(fixture.run, fixture.config, execute=True)
    failed = [e for e in runner.read_jsonl(fixture.run / "attempts.jsonl")
              if e["event"] == "task_attempt_failed"]
    assert len(failed) == 1 and failed[0]["retryable"] is True and failed[0]["task_attempt"] == 1
    failed_call_count = len(fake.calls)
    monkeypatch.setattr(runner, "append_jsonl", real_append_jsonl)
    fake.status = None
    summary = function(fixture.run, fixture.config, execute=True)
    assert summary["success"] == summary["planned"] == 2 and summary["failed"] == 0
    assert len(fake.calls) == summary["transport_attempts_used"] == failed_call_count + 2
    result = json.loads((fixture.run / phase / (failed[0]["item_id"] + ".json")).read_text())
    assert result["status"] == "success" and result["task_attempt"] == 2
    starts = [e["task_attempt"] for e in runner.read_jsonl(fixture.run / "attempts.jsonl")
              if e["event"] == "task_attempt_started" and e["item_id"] == failed[0]["item_id"]]
    assert starts == [1, 2]
    assert function(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == failed_call_count + 2


@pytest.mark.parametrize("ledger", ["requests.jsonl", "attempts.jsonl"])
def test_truncated_ledger_is_rejected_not_silently_dropped(tmp_path, ledger):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    (fixture.run / ledger).write_text('{"event":"unfinished"', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid durable ledger"):
        runner.run_generations(fixture.run, fixture.config, execute=True)


def test_manifest_and_archive_tampering_are_rejected_before_execution(tmp_path):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    manifest_path = fixture.run / "manifest.json"
    original = manifest_path.read_text()
    manifest = json.loads(original)
    manifest["budgets"]["generation_transport_attempts"] += 1
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest identity mismatch"):
        runner.run_generations(fixture.run, fixture.config, execute=True)
    manifest_path.write_text(original)
    fixture.detail.write_bytes(fixture.detail.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        runner.run_generations(fixture.run, fixture.config, execute=True)


def test_trial_question_binding_cannot_be_changed_by_rehashing_trial_ledger(tmp_path):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    manifest = runner.load_manifest(fixture.run)
    manifest["trials"][0]["question_id"] = "not-the-context-question"
    manifest["trials_hash"] = digest(manifest["trials"])
    _write_json(fixture.run / "manifest.json", manifest)
    with pytest.raises(ValueError, match="trial|question|identity"):
        runner.load_manifest(fixture.run)


def test_predeclared_count_budget_must_cover_complete_plan_before_any_network(tmp_path):
    fixture = _fixture(tmp_path)
    settings = copy.deepcopy(fixture.settings)
    settings["budgets"]["generation_trials"] = 11
    fixture.config.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError, match="generation_trials budget too small"):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()


@pytest.mark.parametrize("role", ["reranker", "generator"])
def test_infeasible_score_or_reader_context_rejected_before_manifest_and_network(tmp_path, role):
    fixture = _fixture(tmp_path)
    deployment = yaml.safe_load(fixture.deployment.read_text())
    if role == "reranker":
        override = tmp_path / "capacity-override.yaml"
        override.write_text(yaml.safe_dump({"dependency": {"reranker_max_input_tokens": 1}}))
        settings = copy.deepcopy(fixture.settings)
        settings["deployment_override"] = str(override)
        fixture.config.write_text(yaml.safe_dump(settings))
    else:
        deployment["models"]["generator"]["context_token_budget"] = 1
    fixture.deployment.write_text(yaml.safe_dump(deployment))
    with pytest.raises(ValueError, match="over its estimated capacity"):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()
    assert not (fixture.run / "requests.jsonl").exists()


@pytest.mark.parametrize("duplicate", ["case", "universe", "control_name", "control_memory", "root_seed"])
def test_duplicate_plan_entries_fail_before_network(tmp_path, duplicate):
    fixture = _fixture(tmp_path)
    settings = copy.deepcopy(fixture.settings)
    case = settings["cases"][0]
    if duplicate == "case":
        settings["cases"].append(copy.deepcopy(case))
    elif duplicate == "universe":
        case["universe"] = ["m00001", "q-tiny:m00001"]
    elif duplicate == "control_name":
        case["controls"].append(copy.deepcopy(case["controls"][0]))
    elif duplicate == "control_memory":
        case["controls"][0]["memory_ids"] = ["m00001", "q-tiny:m00001"]
    else:
        settings["root_seeds"] = [0, 0]
    fixture.config.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError, match="unique|duplicate"):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()


@pytest.mark.parametrize("definition", ["universe", "control"])
def test_nonvisible_history_never_enters_diagnostic_plan(tmp_path, definition):
    fixture = _fixture(tmp_path)
    settings = copy.deepcopy(fixture.settings)
    case = settings["cases"][0]
    if definition == "universe":
        case["universe"] = ["m00003"]
    else:
        case["controls"][0]["memory_ids"] = ["m00003"]
    fixture.config.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError, match="visible"):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()


@pytest.mark.parametrize("invalid", ["missing_search", "nonvisible_selection", "duplicate_selection"])
def test_historical_archive_is_validated_not_only_hashed(tmp_path, invalid):
    fixture = _fixture(tmp_path)
    artifact = copy.deepcopy(fixture.detail_artifact)
    if invalid == "missing_search":
        artifact.pop("search")
    elif invalid == "nonvisible_selection":
        artifact["selection"]["selected_ids"] = ["q-tiny:m00003"]
    else:
        artifact["selection"]["selected_ids"] = ["q-tiny:m00001", "q-tiny:m00001"]
    _write_tar(fixture.detail, {"candidate_pool/activation-task.json": artifact})
    settings = copy.deepcopy(fixture.settings)
    settings["detail_archive"]["sha256"] = file_digest(fixture.detail)
    fixture.config.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError, match="search/selection|unique visible"):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()
    assert not (fixture.run / "requests.jsonl").exists()


@pytest.mark.parametrize("name,value", [("schema_version", True), ("repeats", True),
                                        ("order_seed", 1.5), ("include_dense_controls", 1),
                                        ("unknown_protocol_switch", True)])
def test_diagnostic_config_rejects_wrong_types_and_unknown_fields(tmp_path, name, value):
    fixture = _fixture(tmp_path)
    settings = copy.deepcopy(fixture.settings)
    settings[name] = value
    fixture.config.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError):
        runner.plan_diagnostics(fixture.config, fixture.run)
    assert not (fixture.run / "manifest.json").exists()


def test_trial_execution_order_cannot_be_changed_by_rehashing_trial_ledger(tmp_path):
    fixture = _fixture(tmp_path)
    runner.plan_diagnostics(fixture.config, fixture.run)
    manifest = runner.load_manifest(fixture.run)
    manifest["trials"][0], manifest["trials"][1] = manifest["trials"][1], manifest["trials"][0]
    manifest["trials_hash"] = digest(manifest["trials"])
    _write_json(fixture.run / "manifest.json", manifest)
    with pytest.raises(ValueError, match="trial|order|identity"):
        runner.load_manifest(fixture.run)


def test_resume_rejects_a_terminal_result_copied_from_another_trial(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, repeats=2, universe_size=1, dense=False, control=False)
    runner.plan_diagnostics(fixture.config, fixture.run)
    fake = _http(monkeypatch)
    runner.run_generations(fixture.run, fixture.config, execute=True)
    manifest = runner.load_manifest(fixture.run)
    first, second = manifest["trials"][:2]
    source = fixture.run / "generation" / (first["trial_id"] + ".json")
    target = fixture.run / "generation" / (second["trial_id"] + ".json")
    target.write_bytes(source.read_bytes())
    before = len(fake.calls)
    with pytest.raises(ValueError, match="result|trial|identity"):
        runner.run_generations(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == before
