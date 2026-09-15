import json
from pathlib import Path
import random

import pytest

from bridgetree.clients import build_context_plan
from bridgetree.diagnostic_config import digest
from bridgetree.diagnostic_identity import request_hash
from bridgetree.diagnostic_progress import build_progress, write_progress
from bridgetree.diagnostic_root_runner import root_trial_plan


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def append(path, value):
    with path.open("a") as stream:
        stream.write(json.dumps(value) + "\n")


@pytest.fixture
def frozen(tmp_path):
    plan = build_context_plan("synthetic question", [], model="fixture").public_dict()
    contexts = [{"condition_id": f"c{i}", "question_id": "q", "kind": "subset", "context_plan": plan,
                 "wire_payload_hash": request_hash(plan["request"])} for i in range(2)]
    value = {"schema_version": 1, "purpose": "posthoc_diagnostic", "eligible_for_benchmark": False,
             "cases": [{"question_id": "q"}], "contexts": contexts,
             "score_inputs": [{"subset_id": f"s{i}", "question_id": "q"} for i in range(3)],
             "root_seeds": [7], "repeats": 2, "order_seed": 3, "task_max_attempts": 2,
             "budgets": {"score_transport_attempts": 8, "generation_transport_attempts": 12,
                         "root_transport_attempts": 20}}
    value["manifest_id"] = digest(value)
    rng, trials = random.Random(3), []
    for repeat in range(2):
        block = list(contexts)
        rng.shuffle(block)
        for c in block:
            trials.append({"trial_id": digest([value["manifest_id"], c["condition_id"], repeat]),
                           "condition_id": c["condition_id"], "question_id": "q", "repeat_index": repeat})
    value.update(trials=trials, trials_hash=digest(trials))
    save(tmp_path / "manifest.json", value)
    return tmp_path, value


def result(manifest, phase, item, **extra):
    item_id = item.get("item_id", item.get("trial_id", item.get("subset_id")))
    return {"manifest_id": manifest["manifest_id"], "phase": phase, "item_id": item_id,
            **item, "status": "success", "task_attempt": 1, **extra}


def store(root, row):
    save(root / row["phase"] / (row["item_id"] + ".json"), row)


def test_empty_progress_is_pending_not_failed_or_incorrect(frozen):
    root, manifest = frozen
    before = set(root.iterdir())
    report = build_progress(root, phase="score", state="running")
    assert set(root.iterdir()) == before
    for phase, expected in (("score", 3), ("generation", 4), ("root", 2)):
        p = report["phases"][phase]
        assert p["planned"] == p["pending"] == expected
        assert p["success"] == p["failed"] == p["unknown"] == p["started"] == p["physical_attempts"] == 0
        assert p["server_reported_tokens"]["input"]["sum"] is None
        assert p["cache"]["generation_hits"] is None
    assert report["evaluation"]["available"] is False
    assert report["module_diagnostics"]["metrics"]["final_memory_count"]["sum"] is None


def test_atomic_and_durable_terminal_deduplicate_retry_pending_and_unknown(frozen):
    root, manifest = frozen
    a, b, c = manifest["score_inputs"]
    success = result(manifest, "score", a)
    store(root, success)
    append(root / "attempts.jsonl", {**success, "event": "task_attempt_completed"})
    recovered = result(manifest, "score", b, event="task_attempt_failed", status="error", retryable=False,
                       outcome_unknown=True, http_status=500)
    append(root / "attempts.jsonl", recovered)
    retry = result(manifest, "score", c, event="task_attempt_failed", status="error", retryable=True)
    append(root / "attempts.jsonl", {**retry, "event": "task_attempt_started"})
    append(root / "attempts.jsonl", retry)
    p = build_progress(root)["phases"]["score"]
    assert (p["success"], p["failed"], p["pending"], p["unknown"]) == (1, 1, 1, 0)
    assert p["outcome_unknown"] == 1
    assert p["outcome_sources"]["durable_terminal_event"] == 1
    assert p["started"] == 3
    assert p["in_progress_or_retry_pending"] == 1
    store(root, result(manifest, "score", c, status="error", outcome_unknown=True, error_type="InterruptedAttempt"))
    p = build_progress(root)["phases"]["score"]
    assert (p["success"], p["failed"], p["pending"], p["unknown"]) == (1, 1, 0, 1)
    assert sum(p[k] for k in ("success", "failed", "pending", "unknown")) == p["planned"]
    assert not (root / "score" / "s1.json").exists()  # No recovery writes.


def test_unknown_files_foreign_history_and_mismatched_trial_never_complete(frozen):
    root, manifest = frozen
    trial = manifest["trials"][0]
    store(root, result(manifest, "generation", trial, question_id="different"))
    save(root / "score" / "unplanned.json", {"status": "success"})
    for row in (result(manifest, "score", manifest["score_inputs"][0], manifest_id="old"),
                result(manifest, "score", manifest["score_inputs"][1], question_id="different"),
                result(manifest, "score", {"subset_id": "unplanned", "question_id": "q"})):
        append(root / "attempts.jsonl", {**row, "event": "task_attempt_completed"})
    report = build_progress(root)
    assert all(p["success"] == p["failed"] == 0 for p in report["phases"].values())
    assert {w["code"] for w in report["warnings"]} >= {"unknown_or_foreign_ledger_records_ignored", "unplanned_outcome_files_ignored", "outcome_identity_mismatch"}


def test_physical_retry_and_split_count_once_not_logical_or_task_totals(frozen):
    root, manifest = frozen
    base = {"run_identity": manifest["manifest_id"], "phase": "score", "task_id": "s0", "task_attempt": 1}
    for rid, attempt, status in (("parent", 1, 500), ("parent", 2, 500), ("child-left", 1, 200), ("child-right", 1, 200)):
        event = {**base, "request_id": rid, "transport_attempt": attempt}
        append(root / "requests.jsonl", {**event, "event": "http_attempt_started"})
        terminal = {**event, "event": "http_attempt_failed" if status == 500 else "http_attempt_completed",
                    "status_code": status, "elapsed_ms": 10, "server_reported_input_tokens": None if status == 500 else 0}
        append(root / "requests.jsonl", terminal)
        append(root / "requests.jsonl", terminal)  # Exact duplicate is not another physical call.
    append(root / "requests.jsonl", {**base, "event": "logical_request_completed", "elapsed_ms": 9999})
    p = build_progress(root)["phases"]["score"]
    assert (p["physical_attempts"], p["physical_completed"], p["physical_failed"]) == (4, 2, 2)
    assert p["http_errors"] == {"500": 2}
    assert p["transport_budget"] == {"used_reservations": 4, "remaining": 4, "cap": 8}
    assert p["physical_elapsed_ms"]["sum"] == 40
    assert p["server_reported_tokens"]["input"]["sum"] == 0
    assert p["server_reported_tokens"]["total"]["sum"] is None


def test_incremental_trailing_partial_ignored_but_middle_corruption_warned(frozen):
    root, manifest = frozen
    row = result(manifest, "score", manifest["score_inputs"][0], event="task_attempt_completed")
    raw = json.dumps(row)
    path = root / "attempts.jsonl"
    path.write_text(raw[:len(raw)//2])
    first = build_progress(root)
    assert first["phases"]["score"]["success"] == 0
    assert first["warnings"][0]["code"] == "incomplete_trailing_line_ignored"
    with path.open("a") as stream:
        stream.write(raw[len(raw)//2:] + "\n{broken}\n")
    second = build_progress(root)
    assert second["phases"]["score"]["success"] == 1
    assert second["warnings"] == [{"code": "corrupt_ledger_line", "file": "attempts.jsonl", "line": 2}]
    assert build_progress(root)["phases"] == second["phases"]
    path.write_text("")  # Truncation/rotation resets incremental state.
    assert build_progress(root)["phases"]["score"]["success"] == 0


def test_root_partial_metrics_missing_and_zero_are_distinct_and_small(frozen):
    root, manifest = frozen
    baseline, variant = root_trial_plan(manifest)
    trace = {"initial_target_ids": ["a", "b"], "root_pop_order": ["a"],
             "per_target": {"a": {"popped_state_count": 4}, "b": {"popped_state_count": 0}},
             "external_candidate_ids": [], "external_selected_ids": [],
             "archive_bundle_ids_hash": "archive", "final_selected_ids_hash": "empty"}
    search = {"final_ann_calls": 36, "ann_calls": 23, "scored_sets": 100,
              "activations": [{"signal": .2}, {"signal": -.2}], "bundles": [{"text": "x" * 2000000}]}
    selection = {"selected_ids": [], "scored_sets": 10, "stop": {"reason": "no_positive_marginal"}}
    store(root, result(manifest, "root", baseline, root_trace=trace, search=search, selection=selection))
    store(root, result(manifest, "root", variant, status="error", partial_artifacts={
        "root_trace": trace, "search": search, "selection": {**selection, "partial": True,
            "stop": {"reason": "execution_error"}}}))
    report = build_progress(root)
    mods = report["module_diagnostics"]
    good, failed = mods["per_root_trial"]
    assert good["ann_calls_total"] == 36  # Not 36+23.
    assert good["root_coverage"] == .5 and good["max_target_state_share"] == 1
    assert good["positive_signal_count"] == 1
    assert good["external_candidate_count"] == good["external_selected_count"] == good["final_memory_count"] == 0
    assert failed["final_memory_count"] is None and failed["external_selected_count"] is None
    assert failed["partial_selected_memory_count"] == 0 and not failed["selection_complete"]
    assert mods["metrics"]["final_memory_count"] == {"observed": 1, "missing": 1, "sum": 0, "mean": 0, "min": 0, "max": 0}
    assert mods["hash_comparisons"][0]["archive_hash_equal"] is True
    assert mods["hash_comparisons"][0]["selection_hash_equal"] is None
    assert len(json.dumps(report)) < 20000
    assert "bundles" not in json.dumps(report) and "xxxxxxxxxx" not in json.dumps(report)


def test_scorer_cumulative_cache_snapshots_not_summed(frozen):
    root, manifest = frozen
    events = [{"event": "set_score", "source": "reranker"}, {"event": "set_score", "source": "memory_cache"}]
    for item, values in zip(manifest["score_inputs"], [events[:1], events, events]):
        store(root, result(manifest, "score", item, scorer_events=values))
    cache = build_progress(root)["phases"]["score"]["cache"]["scoring"]
    assert cache["snapshots"]["q"] == {"event_count": 2, "sources": {"reranker": 1, "memory_cache": 1}}


def test_evaluation_only_posthoc_within_condition_and_no_unknown_accuracy(frozen):
    root, manifest = frozen
    one, two, three, four = manifest["trials"]
    store(root, result(manifest, "generation", one, generation_cache_hit=False))
    store(root, result(manifest, "generation", two, status="error", http_status=500, outcome_unknown=True))
    eval_rows = [{**t, "status": "success", "correct": True} for t in manifest["trials"]]
    save(root / "evaluation.json", {"manifest_id": manifest["manifest_id"], "trials": eval_rows})
    report = build_progress(root)
    evaluation = report["evaluation"]
    assert evaluation["scope"] == "posthoc_within_condition" and not evaluation["eligible_for_benchmark"]
    assert evaluation["independent_question_count"] == 1 and evaluation["technical_repeats_per_condition"] == 2
    assert sum(c["evaluated_successful_repeats"] for c in evaluation["conditions"]) == 1
    assert sum(c["incorrect"] or 0 for c in evaluation["conditions"]) == 0
    assert "accuracy" not in report and "accuracy" not in evaluation
    assert report["phases"]["generation"]["cache"]["generation_hits"] == 0


def test_write_progress_atomic_and_validated_manifest(frozen):
    root, manifest = frozen
    actual = write_progress(root, phase="root", state="running")
    assert json.loads((root / "progress.json").read_text()) == actual
    assert not list(root.glob("progress.json.*.tmp"))
    manifest["budgets"]["root_transport_attempts"] += 1
    save(root / "manifest.json", manifest)
    with pytest.raises(ValueError, match="invalid frozen"):
        build_progress(root)


def test_final_retry_failure_is_terminal_without_outcome_and_unknown_status_partition(frozen):
    root, manifest = frozen
    row = result(manifest, "score", manifest["score_inputs"][0], status="error", task_attempt=2,
                 retryable=True, event="task_attempt_failed")
    append(root / "attempts.jsonl", row)
    store(root, result(manifest, "score", manifest["score_inputs"][1], status="unrecognized"))
    p = build_progress(root)["phases"]["score"]
    assert (p["success"], p["failed"], p["unknown"], p["pending"]) == (0, 1, 1, 1)


def test_unchanged_outcomes_cached_and_root_missing_artifact_not_empty(frozen, monkeypatch):
    root, manifest = frozen
    trial = root_trial_plan(manifest)[0]
    store(root, result(manifest, "root", trial, status="error", partial_artifacts={"generation_calls": 0}))
    first = build_progress(root)
    metrics = first["module_diagnostics"]["per_root_trial"][0]
    assert not metrics["artifact_available"]
    assert metrics["positive_signal_count"] is metrics["ann_calls_total"] is metrics["final_memory_count"] is None
    original = Path.read_text
    def no_cached_read(path, *args, **kwargs):
        if path.name == "manifest.json" or path.parent == root / "root":
            raise AssertionError("unchanged large JSON was reparsed")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", no_cached_read)
    second = build_progress(root)
    assert second["module_diagnostics"] == first["module_diagnostics"]


def test_ledger_replacement_cannot_leave_old_completion_cached(frozen):
    root, manifest = frozen
    row = result(manifest, "score", manifest["score_inputs"][0], event="task_attempt_completed")
    path = root / "attempts.jsonl"
    append(path, row)
    assert build_progress(root)["phases"]["score"]["success"] == 1
    # Simulate replacement with a longer foreign-run ledger in the same inode.
    foreign = {**row, "manifest_id": "another-run-with-longer-id", "padding": "x" * 500}
    path.write_text(json.dumps(foreign) + "\n")
    report = build_progress(root)
    assert report["phases"]["score"]["success"] == 0
    assert {w["code"] for w in report["warnings"]} >= {"ledger_rewritten_cache_reset", "unknown_or_foreign_ledger_records_ignored"}
