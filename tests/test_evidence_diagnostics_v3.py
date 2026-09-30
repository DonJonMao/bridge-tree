"""Observe raw-review and unassessed-coverage outcomes without hiding failures."""

import json

import pytest

from bridgetree.diagnostic_observability import ModuleEventRecorder, observation_scope, observe
from bridgetree.evidence_diagnostics import evidence_bridge_summary, reliability_cohorts


def outcome(state, complete, *, correct=True, reliability="normal", cost=2):
    diagnostics = {
        "reliability_status": reliability,
        "selection_input_truncated": reliability == "truncated",
        "partially_mapped": False,
        "evidence_state": state,
        "evidence_empty_context": state == "empty",
        "coverage_validation_complete": complete,
        "unassessed_requirement_count": 0 if complete else 1,
    }
    return {
        "status": "success", "correct": correct, "costs": {"evidence_calls": cost},
        "diagnostics": {"evidence_bridge_summary": {"reliability": diagnostics}},
    }


def test_success_cohorts_partition_independent_evidence_and_validation_states():
    rows = [
        outcome("empty", True),
        outcome("mapped_only", True, correct=False),
        outcome("raw_only", False, reliability="normal"),  # stale label must not hide degradation
        outcome("mixed", False, reliability="truncated", cost=4),
        {"status": "success", "correct": False, "costs": {}},
        {"status": "error", "costs": {"evidence_calls": 24},
         "diagnostics": {"evidence_bridge_summary": {"reliability": {"evidence_state": "mixed"}}}},
    ]
    result = reliability_cohorts(rows)
    assert result["successful_tasks"] == 5
    assert result["failed_tasks"] == 1
    for key in ("completion_cohorts", "evidence_state_cohorts", "coverage_validation_cohorts"):
        assert sum(g["tasks"] for g in result[key].values()) == 5
    completion = result["completion_cohorts"]
    assert completion["normal"]["tasks"] == 2
    assert completion["coverage_unassessed"]["tasks"] == 2
    assert completion["unknown"]["tasks"] == 1
    assert completion["coverage_unassessed"]["cost_metrics"]["evidence_calls"]["sum"] == 6
    for state in ("empty", "mapped_only", "raw_only", "mixed", "unknown"):
        assert result["evidence_state_cohorts"][state]["tasks"] == 1
    coverage = result["coverage_validation_cohorts"]
    assert coverage["complete"]["tasks"] == coverage["unassessed"]["tasks"] == 2
    assert coverage["unknown"]["tasks"] == 1
    assert coverage["complete"]["accuracy"] == .5
    assert coverage["unassessed"]["accuracy"] == 1
    assert result["failure_cost_metrics"]["evidence_calls"]["sum"] == 24


def test_v2_missing_validation_and_evidence_state_remain_unknown():
    rows = [{"status": "success", "correct": True, "diagnostics": {
        "evidence_bridge_summary": {"reliability": {"reliability_status": "normal"}},
    }}]
    result = reliability_cohorts(rows)
    assert result["completion_cohorts"]["normal"]["tasks"] == 1
    assert result["evidence_state_cohorts"]["unknown"]["tasks"] == 1
    assert result["coverage_validation_cohorts"]["unknown"]["tasks"] == 1


def test_summary_exposes_raw_selection_baseline_retention_and_coverage_audit():
    dispositions = [
        {"id": "a", "baseline": True, "mapped": True, "selected": True, "disposition": "selected_mapped"},
        {"id": "b", "baseline": True, "mapped": False, "selected": True, "disposition": "selected_raw"},
        {"id": "c", "baseline": False, "mapped": False, "selected": False,
         "disposition": "raw_review_not_selected"},
    ]
    coverage = [
        {"requirement_id": "r1", "status": "covered", "declared_kind": "explicit", "kind": "inference",
         "normalization_reason": "cited_inferential_mapping", "validation_complete": True},
        {"requirement_id": "r2", "status": "unassessed", "kind": "unknown", "validation_complete": False,
         "unassessed_error": "full original failure retained only in artifact"},
    ]
    diagnostics = {
        "reliability_status": "normal", "selection_input_truncated": True, "partially_mapped": True,
        "evidence_baseline_count": 2, "evidence_baseline_selected_count": 2,
        "evidence_raw_review_count": 3, "evidence_raw_selected_count": 1,
        "evidence_empty_context": False, "evidence_state": "mixed",
        "coverage_validation_complete": True, "unassessed_requirement_count": 0,
    }
    summary = evidence_bridge_summary({"evidence_selection": {
        "baseline_ids": ["a", "b"], "raw_review_ids": ["a", "b", "c"],
        "candidate_dispositions": dispositions, "coverage": coverage, "diagnostics": diagnostics,
    }}, {}, ["a", "b"])
    selection = summary["selection"]
    assert selection["baseline_count"] == selection["baseline_selected_count"] == 2
    assert selection["baseline_retention_rate"] == 1
    assert selection["raw_review_ids"] == ["a", "b", "c"]
    assert selection["raw_review_count"] == 3
    assert selection["raw_selected_count"] == 1
    assert selection["evidence_state"] == "mixed"
    assert selection["candidate_disposition_counts"] == {
        "selected_mapped": 1, "selected_raw": 1, "raw_review_not_selected": 1,
    }
    assert selection["candidate_dispositions"] == dispositions
    assert selection["coverage_kind_normalizations"] == [{
        "requirement_id": "r1", "declared_kind": "explicit", "kind": "inference",
        "normalization_reason": "cited_inferential_mapping",
    }]
    assert summary["reliability"]["reliability_status"] == "coverage_unassessed"
    assert summary["reliability"]["coverage_validation_complete"] is False
    assert summary["reliability"]["unassessed_requirement_count"] == 1
    assert summary["reliability"]["selection_input_truncated"] is True
    assert summary["reliability"]["partially_mapped"] is True


def test_empty_baseline_rate_is_undefined_and_missing_diagnostics_are_not_normal():
    summary = evidence_bridge_summary({"evidence_selection": {"baseline_ids": []}}, {}, [])
    assert summary["selection"]["baseline_retention_rate"] is None
    assert summary["reliability"]["reliability_status"] is None
    assert summary["selection"]["coverage_validation_complete"] is None


@pytest.mark.parametrize("reason", ["cited_inferential_mapping", "joint_partial_inference"])
def test_live_v3_events_preserve_ids_dispositions_and_fixed_reasons_without_text(tmp_path, reason):
    recorder = ModuleEventRecorder(tmp_path)
    with observation_scope(recorder):
        observe("evidence", "evidence_raw_review_prepared", raw_review_ids=["a", "b"],
                omitted_raw_review_ids=["c"], baseline_ids=["a"], input_tokens_after=900,
                raw_memories=[{"id": "a", "text": "PRIVATE_RAW_MEMORY"}])
        observe("evidence", "evidence_candidate_dispositions", dispositions=[{
            "id": "b", "baseline": False, "fully_mapped": True, "mapped": False,
            "raw_review_visible": True, "selected": True, "disposition": "selected_raw",
            "text": "PRIVATE_RAW_MEMORY",
        }])
        observe("selection", "evidence_coverage_kind_normalized", requirement_id="r1",
                declared_kind="explicit", effective_kind="inference", reason=reason,
                normalization_reason=reason, coverage_status_changed=False)
        observe("selection", "evidence_coverage_repair_prepared", pending_requirement_ids=["r1"],
                selected_ids=["b"], retained_evidence_ids=["ev_11111111111111111111"],
                dropped_evidence_ids=["ev_22222222222222222222"], input_tokens_after=1000,
                policy_version="coverage_repair_pending_selected_v3")
        observe("selection", "evidence_coverage_unassessed", requirement_ids=["r2"],
                failure_category="input_budget", validation_complete=False,
                validation_error="PRIVATE_ERROR_SOURCE_TEXT", unassessed_error="PRIVATE_ERROR_SOURCE_TEXT")
    text = (tmp_path / "modules/events.jsonl").read_text()
    assert "PRIVATE_" not in text
    events = [json.loads(line) for line in text.splitlines()]
    assert events[0]["raw_review_ids"] == ["a", "b"]
    assert events[0]["omitted_raw_review_ids"] == ["c"]
    assert events[0]["baseline_ids"] == ["a"]
    assert events[1]["dispositions"][0]["disposition"] == "selected_raw"
    assert events[1]["dispositions"][0]["raw_review_visible"] is True
    assert events[2]["reason"] == events[2]["normalization_reason"] == reason
    assert events[2]["coverage_status_changed"] is False
    assert events[3]["pending_requirement_ids"] == ["r1"]
    assert events[3]["selected_ids"] == ["b"]
    assert events[3]["retained_evidence_ids"] == ["ev_11111111111111111111"]
    assert events[3]["dropped_evidence_ids"] == ["ev_22222222222222222222"]
    assert events[3]["input_tokens_after"] == 1000
    assert events[4]["failure_category"] == "input_budget"
    assert events[4]["validation_complete"] is False
    assert len((tmp_path / "modules/evidence.jsonl").read_text().splitlines()) == 2
    assert len((tmp_path / "modules/selection.jsonl").read_text().splitlines()) == 3
