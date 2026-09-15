"""In-process background-worker integration: synthetic fixtures and fake HTTP.

No detached processes or real model endpoints are used by this test file.
"""
from __future__ import annotations

import json
import signal
import threading
import urllib.error

import pytest
import yaml

from bridgetree import clients, diagnostic_runner as runner
from bridgetree.diagnostic_background import run_pipeline
from test_diagnostic_runner import _Response, _fixture
from test_diagnostic_root_runner import RootHTTP


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected external network in background diagnostic tests")
    monkeypatch.setattr(clients.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(clients.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(clients.time, "sleep", lambda _: None)
    # Exercise the equality gate without races against unrelated agent edits.
    monkeypatch.setattr(runner, "source_identity", lambda: "synthetic-background-package-v1")
    monkeypatch.delenv("BRIDGETREE_TEST_DIAGNOSTIC_KEY", raising=False)


def read(path):
    return json.loads(path.read_text())


def background_fixture(tmp_path):
    # Unlike the root-only fixture, the complete pipeline needs a historical
    # archive with question metadata and measured selection scores.
    fixture = _fixture(tmp_path, dense=False, control=False, repeats=1, task_attempts=1)
    dependency = tmp_path / "dependency.yaml"
    dependency.write_text(yaml.safe_dump({"base_config": str(fixture.deployment), "dependency": {
        "initial_width": 3, "initial_expansion_width": 1, "proposal_width": 2,
        "max_ann_calls": 5, "max_scored_sets": 64, "max_selection_sets": 64,
        "pair_rescue_width": 0, "reranker_batch_size": 32, "reranker_max_input_tokens": 8192,
    }}))
    settings = yaml.safe_load(fixture.config.read_text())
    settings["deployment_config"] = str(dependency)
    settings["budgets"]["root_transport_attempts"] = 200
    fixture.config.write_text(yaml.safe_dump(settings))
    return fixture


class PipelineHTTP(RootHTTP):
    def __init__(self, *, generation_status=None, interrupt_first=False):
        super().__init__()
        self.generation_status = generation_status
        self.interrupt_first = interrupt_first

    def open(self, request, timeout):
        if self.interrupt_first:
            self.interrupt_first = False
            raise KeyboardInterrupt("synthetic worker interruption")
        payload = json.loads(request.data)
        if "messages" not in payload:
            return super().open(request, timeout)
        self.calls.append({"operation": "generation", "payload": payload})
        self.counts["generation"] += 1
        if self.generation_status is not None:
            raise urllib.error.HTTPError(request.full_url, self.generation_status, "fixture failure", {}, None)
        return _Response({"choices": [{"message": {"content": "(a) synthetic answer"}}],
                          "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}})


def install(monkeypatch, **kwargs):
    fake = PipelineHTTP(**kwargs)
    monkeypatch.setattr(clients.urllib.request, "build_opener", lambda *a, **kw: fake)
    return fake


def assert_closed(root, old_sigterm):
    assert not (root / ".background_worker_ready.json").exists()
    assert signal.getsignal(signal.SIGTERM) == old_sigterm
    assert not any(t.name == "diagnostic-heartbeat" and t.is_alive() for t in threading.enumerate())


def test_offline_pipeline_never_calls_models_and_writes_completion_progress_logs(tmp_path):
    fixture = _fixture(tmp_path, unknown_role="generator")
    old_sigterm = signal.getsignal(signal.SIGTERM)
    result = run_pipeline(fixture.config, fixture.run, offline=True, heartbeat_seconds=.01)
    assert result["status"] == "offline_complete" and result["offline"] is True
    assert result["weights_updated"] is False and result["optimizer_steps"] == 0
    assert read(fixture.run / "completion.json") == result
    progress = read(fixture.run / "progress.json")
    assert progress["state"] == "offline_complete"
    assert {k: p["planned"] for k, p in progress["phases"].items()} == {"score": 4, "generation": 12, "root": 3}
    assert all(p["pending"] == p["planned"] and p["physical_attempts"] == p["success"] == p["failed"] == 0
               for p in progress["phases"].values())
    assert not (fixture.run / "requests.jsonl").exists()
    assert not (fixture.run / "attempts.jsonl").exists()
    for name in ("offline_analysis.json", "evaluation.json", "diagnostic_report.json", "runtime.jsonl", "run.log",
                 "modules/events.jsonl", "modules/execution.jsonl"):
        assert (fixture.run / name).is_file()
    evaluation = read(fixture.run / "evaluation.json")
    assert not evaluation["eligible_for_benchmark"]
    assert all(c["successful_accuracy"] is None and c["pending"] == c["planned"] for c in evaluation["conditions"])
    runtime = runner.read_jsonl(fixture.run / "runtime.jsonl")
    assert runtime[0]["event"] == "pipeline_started"
    assert any(r["event"] == "pipeline_finished" for r in runtime)
    assert any(r["event"] == "heartbeat" and "progress" in r for r in runtime)
    assert_closed(fixture.run, old_sigterm)


def test_online_fake_http_runs_all_phases_and_reports_module_diagnostics(tmp_path, monkeypatch):
    fixture = background_fixture(tmp_path)
    target = tmp_path / "background-run"
    fake = install(monkeypatch)
    result = run_pipeline(fixture.config, target, heartbeat_seconds=.01)
    assert result["status"] == "completed", result
    assert [p["phase"] for p in result["phases"]] == ["planning", "historical_analysis", "online_identity", "score",
        "fresh_analysis", "generation", "evaluation", "root", "report"]
    progress = read(target / "progress.json")
    assert all(p["success"] == p["planned"] and p["pending"] == p["failed"] == p["unknown"] == 0
               for p in progress["phases"].values())
    assert sum(p["physical_attempts"] for p in progress["phases"].values()) == len(fake.calls)
    assert fake.counts["generation"] == 4 and fake.counts["embedding"] > 0 and fake.counts["reranker"] > 0
    assert progress["module_diagnostics"]["completed_trials"] == 3
    assert len(progress["module_diagnostics"]["per_root_trial"]) == 3
    assert progress["evaluation"]["independent_question_count"] == 1
    assert all(c["successful_accuracy"] == 1 for c in progress["evaluation"]["conditions"])
    assert read(target / "diagnostic_report.json")["counts"]["root_runs"] == 3
    events = runner.read_jsonl(target / "modules" / "events.jsonl")
    assert {r["module"] for r in events} >= {"execution", "proposal", "scoring", "activation", "state", "selection", "stop", "context"}
    for path in (target / "run.log", target / "modules" / "events.jsonl", target / "requests.jsonl"):
        text = path.read_text()
        assert "diagnostic-fixture.invalid" not in text
        assert "GOLD_ONLY_SENTINEL" not in text and "FUTURE_ONLY_SENTINEL" not in text
        assert "What should I do this weekend?" not in text


def test_resume_preserves_atomic_results_and_model_ledgers_without_recompute(tmp_path, monkeypatch):
    fixture = background_fixture(tmp_path)
    target = tmp_path / "background-run"
    fake = install(monkeypatch)
    first = run_pipeline(fixture.config, target, heartbeat_seconds=.01)
    assert first["status"] == "completed", first
    ledger_bytes = {name: (target / name).read_bytes() for name in ("attempts.jsonl", "requests.jsonl")}
    results = {str(p.relative_to(target)): p.read_bytes() for phase in ("score", "generation", "root")
               for p in (target / phase).glob("*.json")}
    calls = len(fake.calls)
    second = run_pipeline(fixture.config, target, resume=True, heartbeat_seconds=.01)
    assert second["status"] == "completed", second
    assert len(fake.calls) == calls
    for name, before in ledger_bytes.items():
        assert (target / name).read_bytes() == before
    for name, before in results.items():
        assert (target / name).read_bytes() == before
    events = runner.read_jsonl(target / "modules" / "execution.jsonl")
    assert sum(r["event"] == "task_reused" for r in events) == 11


def test_online_unknown_deployment_preflight_blocks_before_any_http(tmp_path):
    fixture = _fixture(tmp_path, unknown_role="generator")
    old_sigterm = signal.getsignal(signal.SIGTERM)
    result = run_pipeline(fixture.config, fixture.run, heartbeat_seconds=.01)
    assert result["status"] == "failed" and result["last_phase"] == "online_identity"
    assert result["error"]["error_type"] == "ValueError"
    gate = read(fixture.run / "online_preflight.json")
    assert gate["status"] == "blocked_before_network" and gate["network_calls"] == 0
    assert "generator" in gate["missing_identity_roles"]
    assert not (fixture.run / "requests.jsonl").exists()
    assert not (fixture.run / "attempts.jsonl").exists()
    progress = read(fixture.run / "progress.json")
    assert all(p["failed"] == p["physical_attempts"] == 0 and p["pending"] == p["planned"] for p in progress["phases"].values())
    assert_closed(fixture.run, old_sigterm)


def test_generation_failures_remain_execution_failures_not_wrong_answers(tmp_path, monkeypatch):
    fixture = background_fixture(tmp_path)
    target = tmp_path / "background-run"
    fake = install(monkeypatch, generation_status=400)
    result = run_pipeline(fixture.config, target, heartbeat_seconds=.01)
    assert result["status"] == "completed_with_failures", result
    progress = read(target / "progress.json")
    generation = progress["phases"]["generation"]
    assert generation["failed"] == generation["planned"] == fake.counts["generation"] == 4
    assert generation["success"] == generation["pending"] == 0 and generation["http_errors"] == {"400": 4}
    assert all(c["incorrect"] is None and c["successful_accuracy"] is None for c in progress["evaluation"]["conditions"])
    assert progress["phases"]["root"]["success"] == 3


def test_interrupt_preserves_reservation_and_restores_signal_and_heartbeat(tmp_path, monkeypatch):
    fixture = background_fixture(tmp_path)
    target = tmp_path / "background-run"
    install(monkeypatch, interrupt_first=True)
    old_sigterm = signal.getsignal(signal.SIGTERM)
    result = run_pipeline(fixture.config, target, heartbeat_seconds=.01)
    assert result["status"] == "interrupted" and result["last_phase"] == "score"
    progress = read(target / "progress.json")
    assert progress["phases"]["score"]["physical_attempts"] == 1
    assert progress["phases"]["score"]["success"] == progress["phases"]["score"]["failed"] == 0
    assert len(runner.read_jsonl(target / "attempts.jsonl")) == 1
    assert_closed(target, old_sigterm)


def test_new_run_and_resume_require_explicit_manifest_contract(tmp_path):
    fixture = _fixture(tmp_path)
    with pytest.raises(ValueError, match="cannot resume"):
        run_pipeline(fixture.config, fixture.run, resume=True, offline=True)
    run_pipeline(fixture.config, fixture.run, offline=True, heartbeat_seconds=.01)
    with pytest.raises(ValueError, match="use resume"):
        run_pipeline(fixture.config, fixture.run, offline=True)


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_heartbeat_interval_rejected_before_worker_start(tmp_path, interval):
    with pytest.raises(ValueError, match="heartbeat_seconds"):
        run_pipeline(tmp_path / "missing.yaml", tmp_path / "run", offline=True, heartbeat_seconds=interval)
    assert not (tmp_path / "run").exists()
