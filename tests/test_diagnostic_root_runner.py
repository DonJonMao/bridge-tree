"""Root-run integration: real HTTP clients/search/selector, stub transport.

The fixture declares synthetic deployment identity. validate_online still
compares that identity, the source snapshot and all dependency settings.
"""
from __future__ import annotations

import json
import re
import urllib.error
from collections import Counter

import pytest
import yaml

from bridgetree import clients, diagnostic_runner as runner
from bridgetree.diagnostic_config import file_digest
from bridgetree.diagnostic_root_runner import root_trial_plan, run_root_diagnostics
from bridgetree.root_tie_diagnostics import root_tie_order
from test_diagnostic_runner import _Response, _fixture, _write_tar


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected real network in root diagnostic test")
    monkeypatch.setattr(clients.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(clients.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(clients.time, "sleep", lambda _: None)
    monkeypatch.setattr(runner, "source_identity", lambda: "synthetic-root-package-v1")
    monkeypatch.delenv("BRIDGETREE_TEST_DIAGNOSTIC_KEY", raising=False)


def root_fixture(tmp_path, *, physical_cap=200, ann_cap=5, search_cap=64,
                 selection_cap=64, task_attempts=1, unknown_role=None):
    fixture = _fixture(tmp_path, dense=False, control=False, repeats=1,
                       task_attempts=task_attempts, unknown_role=unknown_role)
    dependency = tmp_path / "dependency.yaml"
    dependency.write_text(yaml.safe_dump({"base_config": str(fixture.deployment), "dependency": {
        "initial_width": 3, "initial_expansion_width": 1, "proposal_width": 2,
        "max_ann_calls": ann_cap, "max_scored_sets": search_cap,
        "max_selection_sets": selection_cap, "pair_rescue_width": 0,
        "reranker_batch_size": 32, "reranker_max_input_tokens": 8192,
    }}))
    settings = yaml.safe_load(fixture.config.read_text())
    # The root integration has its own historical selection fixture. Keep it
    # complete enough for the archive identity gate, without depending on
    # unrelated score/generation tests' minimal detail format.
    _write_tar(fixture.detail, {"candidate_pool/activation-task.json": {
        "task_id": "activation-task", "method_id": "activation", "schema_version": 1,
        "search": {"activations": [], "bundles": [{"memory_ids": ["q-tiny:m00001"]}]},
        "selection": {"selected_ids": ["q-tiny:m00001"], "rounds": [],
                      "initial_scored_sets": 0, "final_scored_sets": 0,
                      "stop": {"reason": "archive_exhausted"}},
    }})
    settings["detail_archive"]["sha256"] = file_digest(fixture.detail)
    settings["deployment_config"] = str(dependency)
    settings["budgets"]["root_transport_attempts"] = physical_cap
    fixture.config.write_text(yaml.safe_dump(settings))
    fixture.dependency = dependency
    runner.plan_diagnostics(fixture.config, fixture.run)
    return fixture


class RootHTTP:
    """Deterministic Qwen-shaped transport with known non-submodular scores."""
    def __init__(self, *, fail_rerank=None, fail_rerank_call=None, fail_embedding_call=None,
                 fail_document_ids=None):
        self.calls = []
        self.counts = Counter()
        self.fail_rerank = fail_rerank
        self.fail_rerank_call = fail_rerank_call
        self.fail_embedding_call = fail_embedding_call
        self.fail_document_ids = fail_document_ids

    def open(self, request, timeout):
        payload = json.loads(request.data)
        operation = "embedding" if "input" in payload else "reranker" if "documents" in payload else "generation"
        self.calls.append({"operation": operation, "payload": payload})
        self.counts[operation] += 1
        assert operation != "generation", "root diagnostics must never generate"
        if operation == "embedding":
            if self.counts[operation] == self.fail_embedding_call:
                raise urllib.error.HTTPError(request.full_url, 400, "embedding failure", {}, None)
            # Equal vectors intentionally expose the stable memory-ID tie.
            return _Response({"data": [{"index": i, "embedding": [1.0, 0.0, 0.0]}
                                       for i in range(len(payload["input"]))]})
        if self.fail_rerank is not None and (self.fail_rerank_call is None or
                                            self.counts[operation] == self.fail_rerank_call):
            raise urllib.error.HTTPError(request.full_url, self.fail_rerank, "reranker failure", {}, None)
        values = {(): 0., (0,): .1, (1,): .2, (2,): .3,
                  (0, 1): .7, (0, 2): .8, (1, 2): .9, (0, 1, 2): .75}
        results = []
        for index, document in enumerate(payload["documents"]):
            ids = tuple(sorted({int(value) for value in re.findall(r"q-tiny:m(\d+)", document)}))
            if ids == self.fail_document_ids:
                raise urllib.error.HTTPError(request.full_url, 400, "selection input failure", {}, None)
            results.append({"index": index, "relevance_score": values[ids]})
        return _Response({"results": results, "usage": {"prompt_tokens": 10}})


def install_http(monkeypatch, **kwargs):
    fake = RootHTTP(**kwargs)
    monkeypatch.setattr(clients.urllib.request, "build_opener", lambda *a, **kw: fake)
    return fake


def outcomes(fixture):
    manifest = runner.load_manifest(fixture.run)
    return [json.loads((fixture.run / "root" / (trial["item_id"] + ".json")).read_text())
            for trial in root_trial_plan(manifest)]


def test_noexecute_freezes_all_seed_counts_without_network_or_results(tmp_path):
    fixture = root_fixture(tmp_path)
    summary = run_root_diagnostics(fixture.run, fixture.config)
    assert summary["execute"] is False
    assert summary["network_calls"] == summary["generation_calls"] == 0
    assert [row["root_tie_seed"] for row in summary["root_trials"]] == [None, 0, 1]
    assert summary["max_ann_calls_total"] == 15
    assert summary["unique_set_limits_per_trial"] == {"max_scored_sets": 64, "max_selection_sets": 64}
    assert not (fixture.run / "requests.jsonl").exists()
    assert not (fixture.run / "attempts.jsonl").exists()
    assert not (fixture.run / "root").exists()


def test_true_search_selector_seed_runs_preserve_budgets_and_default_order(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    fake = install_http(monkeypatch)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    rows = outcomes(fixture)
    assert summary["planned"] == summary["success"] == 3
    assert summary["all_seeds_reported"] is True
    assert summary["generation_calls"] == 0
    assert [row["root_tie_seed"] for row in rows] == [None, 0, 1]
    assert [row["root_tie_break"] for row in rows] == ["legacy_lexical", "seeded_hash", "seeded_hash"]
    initial = ["q-tiny:m00000", "q-tiny:m00001", "q-tiny:m00002"]
    for row in rows:
        trace, search, selection = row["root_trace"], row["search"], row["selection"]
        expected = root_tie_order(initial, mode=row["root_tie_break"], seed=row["root_tie_seed"])
        assert trace["initial_candidate_order"] == initial
        assert trace["root_tie_order"] == list(expected)
        assert trace["root_pop_order"] == [expected[0]]
        assert search["initial_ann_calls"] == 4
        assert search["final_ann_calls"] == 5
        assert search["stop_reason"] == "ann_budget_exhausted"
        assert search["scored_sets"] <= 64
        assert selection["scored_sets"] <= 64
        assert selection["initial_scored_sets"] == search["final_scored_sets"]
        assert trace["logical_unique_sets_charged_delta"] == search["scored_sets"]
        assert trace["final_selected_ids"] == selection["selected_ids"]
        assert row["context_plan"]["selected_ids"] == selection["selected_ids"]
        assert row["context_plan"]["budget_status"] == "within_budget"
    assert rows[0]["selection"]["selected_ids"] == ["q-tiny:m00000", "q-tiny:m00002"]
    assert rows[1]["selection"]["selected_ids"] == ["q-tiny:m00001", "q-tiny:m00002"]
    assert rows[2]["selection"]["selected_ids"] == rows[0]["selection"]["selected_ids"]
    assert len(summary["comparisons"]) == 2
    assert summary["comparisons"][0]["final_selection"]["equal"] is False
    assert summary["comparisons"][1]["final_selection"]["equal"] is True
    assert all(row["other_protocols_verified"] for row in summary["comparisons"])
    # Exactly one memory-bank encode, plus 5 query/proposal encodes per run.
    assert fake.counts["embedding"] == 16
    assert summary["transport_attempts_used"] == len(fake.calls)
    starts = [event for event in runner.read_jsonl(fixture.run / "requests.jsonl")
              if event["event"] == "http_attempt_started"]
    assert len(starts) == len(fake.calls)
    assert all(event["phase"] == "root" for event in starts)
    assert not fake.counts["generation"]


def test_root_resume_reuses_terminal_trials_without_repeating_http(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    fake = install_http(monkeypatch)
    first = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    request_bytes = (fixture.run / "requests.jsonl").read_bytes()
    attempt_bytes = (fixture.run / "attempts.jsonl").read_bytes()
    calls = len(fake.calls)
    second = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert first == second
    assert len(fake.calls) == calls
    assert (fixture.run / "requests.jsonl").read_bytes() == request_bytes
    assert (fixture.run / "attempts.jsonl").read_bytes() == attempt_bytes


@pytest.mark.parametrize("role", ["embedding", "reranker"])
def test_root_unknown_identity_blocks_before_network(tmp_path, role):
    fixture = root_fixture(tmp_path, unknown_role=role)
    with pytest.raises(ValueError, match="unfrozen deployment identity"):
        run_root_diagnostics(fixture.run, fixture.config, execute=True)
    gate = json.loads((fixture.run / "root_gate.json").read_text())
    assert gate["network_calls"] == 0
    assert gate["status"] == "blocked_before_network"
    assert not (fixture.run / "requests.jsonl").exists()


def test_manifest_and_dependency_drift_not_bypassed(tmp_path):
    fixture = root_fixture(tmp_path)
    dependency = yaml.safe_load(fixture.dependency.read_text())
    dependency["dependency"]["max_ann_calls"] += 1
    fixture.dependency.write_text(yaml.safe_dump(dependency))
    with pytest.raises(ValueError, match="dependency settings differ"):
        run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert not (fixture.run / "requests.jsonl").exists()


def test_root_source_drift_and_tampered_manifest_block_before_http(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    monkeypatch.setattr(runner, "source_identity", lambda: "different-root-source")
    with pytest.raises(ValueError, match="source snapshot differs"):
        run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert not (fixture.run / "requests.jsonl").exists()
    manifest_path = fixture.run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["root_seeds"] = [9, 10]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest identity mismatch"):
        run_root_diagnostics(fixture.run, fixture.config)
    assert not (fixture.run / "requests.jsonl").exists()


def test_search_http_failure_archives_partial_and_continues_seeds(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    fake = install_http(monkeypatch, fail_rerank=400)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert summary["failed"] == summary["planned"] == 3
    rows = outcomes(fixture)
    for row in rows:
        assert row["status"] == "error" and row["http_status"] == 400
        partial = row["partial_artifacts"]
        assert partial["search"]["stop_reason"] == "execution_error"
        assert partial["root_trace"]["search_complete"] is False
        assert partial["root_trace"]["final_selected_ids"] is None
        assert partial["retrieval"]["ann_calls"] == 5
        assert row["task_attempt"] == 1
    assert all(not comparison["final_selection"]["available"] for comparison in summary["comparisons"])
    assert fake.counts["reranker"] == 3


def test_embedding_failure_before_search_keeps_partial_retrieval(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    install_http(monkeypatch, fail_embedding_call=3)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    first, second, third = outcomes(fixture)
    assert first["status"] == "error"
    assert first["partial_artifacts"]["retrieval"]["ann_calls"] == 1
    assert "search" not in first["partial_artifacts"]
    assert second["status"] == third["status"] == "success"
    assert summary["all_seeds_reported"] is True


def test_selection_failure_retains_committed_round_and_completed_search(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    install_http(monkeypatch, fail_document_ids=(0, 1, 2))
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert summary["failed"] == 3
    for row in outcomes(fixture):
        partial = row["partial_artifacts"]
        assert partial["selection"]["stop"]["reason"] == "execution_error"
        assert len(partial["selection"]["selected_ids"]) == 2
        assert len(partial["selection"]["rounds"]) == 1
        assert partial["selection"]["rounds"][0]["complete"] is True
        assert partial["root_trace"]["search_complete"] is True
        assert partial["search"]["stop_reason"] == "ann_budget_exhausted"


def test_phase_transport_cap_is_actual_http_not_adapter_count(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path, physical_cap=2)
    fake = install_http(monkeypatch)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert summary["transport_attempts_used"] == len(fake.calls) == 2
    assert summary["failed"] == 3
    assert all(row["status"] == "budget_exhausted" for row in outcomes(fixture))
    assert run_root_diagnostics(fixture.run, fixture.config, execute=True) == summary
    assert len(fake.calls) == 2


def test_http_retry_counts_as_transport_attempt_not_new_root_trial(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path)
    fake = install_http(monkeypatch, fail_rerank=500, fail_rerank_call=1)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert summary["success"] == summary["planned"] == 3
    assert summary["transport_attempts_used"] == len(fake.calls)
    assert all(row["task_attempt"] == 1 for row in outcomes(fixture))
    events = runner.read_jsonl(fixture.run / "requests.jsonl")
    failed = [e for e in events if e["event"] == "http_attempt_failed"]
    assert len(failed) == 1 and failed[0]["status_code"] == 500
    starts = [e for e in events if e["event"] == "http_attempt_started"]
    assert len({e["task_id"] for e in starts}) == 3
    repeated_requests = Counter(e["request_id"] for e in starts)
    assert max(repeated_requests.values()) == 2


def test_transport_cap_during_set_scoring_is_not_algorithmic_success(tmp_path, monkeypatch):
    # 1 memory-bank + 4 initial probes + 1 conditional probe exhausts the
    # physical budget immediately before the first real reranker request.
    fixture = root_fixture(tmp_path, physical_cap=6)
    fake = install_http(monkeypatch)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert len(fake.calls) == summary["transport_attempts_used"] == 6
    assert summary["failed"] == 3
    assert all(row["status"] == "budget_exhausted" for row in outcomes(fixture))


def test_search_score_quota_and_selection_quota_stay_per_trial(tmp_path, monkeypatch):
    fixture = root_fixture(tmp_path, search_cap=1, selection_cap=1)
    install_http(monkeypatch)
    summary = run_root_diagnostics(fixture.run, fixture.config, execute=True)
    assert summary["success"] == 3  # logical algorithmic stops are not HTTP errors
    for row in outcomes(fixture):
        assert row["search"]["stop_reason"] == "score_budget_exhausted"
        assert row["search"]["scored_sets"] <= 1
        assert row["selection"]["stop"]["reason"] == "score_budget_exhausted"
        assert row["selection"]["scored_sets"] <= 1
        assert row["selection"]["selected_ids"] == []
