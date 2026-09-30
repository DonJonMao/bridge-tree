"""Method summaries from realized artifacts; no model or gold-label access."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

RELIABILITY_STATUSES = (
    "normal", "truncated", "partially_mapped", "truncated_and_partially_mapped",
    "coverage_unassessed",
)
EVIDENCE_STATES = ("empty", "mapped_only", "raw_only", "mixed")


def _numeric_costs(value: Mapping[str, Any], prefix: str = "") -> dict[str, float]:
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            result.update(_numeric_costs(item, name))
        elif isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item):
            result[name] = item
    return result


def reliability_cohorts(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Partition current outcomes, never infer normal completion from missing logs."""
    successful = [row for row in outcomes if row.get("status") == "success"]
    failed = [row for row in outcomes if row.get("status") == "error"]

    def reliability(row):
        value = row
        for name in ("diagnostics", "evidence_bridge_summary", "reliability"):
            value = value.get(name) if isinstance(value, Mapping) else None
        return value if isinstance(value, Mapping) else {}

    def coverage_state(row):
        value = reliability(row)
        if (value.get("coverage_validation_complete") is False
                or value.get("reliability_status") == "coverage_unassessed"
                or (value.get("unassessed_requirement_count") or 0) > 0):
            return "unassessed"
        return "complete" if value.get("coverage_validation_complete") is True else "unknown"

    def status(row):
        # A stale normal label must not hide explicitly unassessed coverage.
        if coverage_state(row) == "unassessed":
            return "coverage_unassessed"
        result = reliability(row).get("reliability_status")
        return result if result in RELIABILITY_STATUSES else "unknown"

    def evidence_state(row):
        value = reliability(row).get("evidence_state")
        return value if value in EVIDENCE_STATES else "unknown"

    def summarize(rows):
        costs = [_numeric_costs(row.get("costs", {})) for row in rows]
        metrics = {}
        for name in sorted({name for cost in costs for name in cost}):
            values = [cost[name] for cost in costs if name in cost]
            metrics[name] = {
                "observed_tasks": len(values), "missing_tasks": len(rows) - len(values),
                "sum": sum(values), "mean": sum(values) / len(values),
            }
        correct = sum(row.get("correct") is True for row in rows)
        return {
            "tasks": len(rows), "correct": correct,
            "accuracy": correct / len(rows) if rows else None,
            "cost_metrics": metrics,
        }

    return {
        "schema_version": 2,
        "scope": "current authoritative evidence_bridge outcomes; attempts are not accumulated",
        "successful_tasks": len(successful),
        "failed_tasks": len(failed),
        "completion_cohorts": {
            name: summarize([row for row in successful if status(row) == name])
            for name in (*RELIABILITY_STATUSES, "unknown")
        },
        "evidence_state_cohorts": {
            name: summarize([row for row in successful if evidence_state(row) == name])
            for name in (*EVIDENCE_STATES, "unknown")
        },
        "coverage_validation_cohorts": {
            name: summarize([row for row in successful if coverage_state(row) == name])
            for name in ("complete", "unassessed", "unknown")
        },
        "failure_cost_metrics": summarize(failed)["cost_metrics"],
    }


def _rows(value):
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []


def evidence_bridge_summary(
    candidate: Mapping[str, Any], costs: Mapping[str, Any], selected_ids: Sequence[str]
) -> dict[str, Any]:
    search = candidate.get("search") or {}
    selection = candidate.get("evidence_selection") or candidate.get("selection") or {}
    retrieval = candidate.get("retrieval") or {}
    initial = set(search.get("initial_target_ids", retrieval.get("initial_candidate_ids", ())))
    target_costs = _rows(search.get("target_costs", ()))
    visited = {row["target_id"] for row in target_costs if row.get("quanta", 0) > 0}
    ann = [int(row.get("ann_calls", 0)) for row in target_costs]
    measured = _rows(search.get("activations", ()))
    positive = [row for row in measured if row.get("activation", 0) > 0]
    scheduler = _rows(search.get("scheduler_events", ()))
    decisions = _rows(search.get("target_events", ()))
    phases: dict[str, dict[str, int]] = {}
    for row in scheduler:
        if row.get("event") != "quantum_completed":
            continue
        phase = phases.setdefault(str(row.get("phase")), {"quanta": 0, "ann_calls": 0, "scored_sets": 0})
        phase["quanta"] += 1
        phase["ann_calls"] += int(row.get("ann_calls_after", 0)) - int(row.get("ann_calls_before", 0))
        phase["scored_sets"] += int(row.get("scored_sets_after", 0)) - int(row.get("scored_sets_before", 0))
    proposals = _rows(retrieval.get("proposal_batches", ()))
    discovered = {
        hit.get("memory_id") for batch in proposals for hit in _rows(batch.get("hits", ())) if hit.get("memory_id")
    }
    selected = set(selected_ids)
    coverage_value = selection.get("coverage")
    coverage = (
        _rows(coverage_value)
        if not isinstance(coverage_value, Mapping)
        else [
            {"requirement_id": key, **dict(value)}
            for key, value in coverage_value.items()
            if isinstance(value, Mapping)
        ]
    )
    events = _rows(selection.get("events", selection.get("steps", ())))
    diagnostics = selection.get("diagnostics") or {}
    reliability = {
        key: diagnostics.get(key) for key in (
            "reliability_status", "selection_input_truncated", "partially_mapped", "unavailable_unit_count",
        )
    }
    for key in (
        "evidence_state", "evidence_empty_context", "coverage_validation_complete", "unassessed_requirement_count",
    ):
        if key in diagnostics:
            reliability[key] = diagnostics[key]
    unassessed_rows = [row for row in coverage if row.get("validation_complete") is False]
    if (unassessed_rows or reliability.get("coverage_validation_complete") is False
            or (reliability.get("unassessed_requirement_count") or 0) > 0
            or reliability.get("reliability_status") == "coverage_unassessed"):
        reliability["reliability_status"] = "coverage_unassessed"
        reliability["coverage_validation_complete"] = False
        reliability["unassessed_requirement_count"] = max(
            len(unassessed_rows), reliability.get("unassessed_requirement_count") or 0,
        )
    baseline = set(selection.get("baseline_ids", ()))
    baseline_count = len(baseline) if "baseline_ids" in selection else diagnostics.get("evidence_baseline_count")
    baseline_selected = (
        len(baseline & selected) if "baseline_ids" in selection
        else diagnostics.get("evidence_baseline_selected_count")
    )
    dispositions = _rows(selection.get("candidate_dispositions"))
    return {
        "schema_version": 3,
        "interpretation": "Observed search/coverage proxies; covered is not externally verified answer sufficiency.",
        "reliability": reliability,
        "search": {
            "available": bool(search),
            "initial_roots": len(initial),
            "visited_targets": len(visited),
            "visited_initial_roots": len(initial & visited),
            "initial_root_coverage": len(initial & visited) / len(initial) if initial else None,
            "max_target_ann_share": max(ann) / sum(ann) if ann and sum(ann) else None,
            "target_costs": target_costs,
            "phases": phases,
            "complete_measurements": len(measured),
            "positive_activations": len(positive),
            "positive_activation_nonpositive_target": sum(row.get("target_marginal_after", 0) <= 0 for row in positive),
            "pivot_attempts": sum(row.get("event") == "target_pivot" for row in decisions),
            "pivot_count": sum(row.get("event") == "target_pivot" and row.get("queued") is True for row in decisions),
            "pivot_rejections": sum(
                row.get("event") == "target_pivot" and row.get("queued") is not True for row in decisions
            ),
            "promoted_external_roots": sum(row.get("event") == "external_root_promoted" for row in decisions),
            "target_decisions": dict(
                Counter(str(row.get("decision")) for row in decisions if row.get("event") == "target_decision")
            ),
            "measured_set_count": len(search.get("measured_sets", ())),
            "archived_bundle_count": len(search.get("bundles", ())),
            "stop_reason": search.get("stop_reason"),
        },
        "selection": {
            "available": bool(selection),
            "requirements_count": len(selection.get("requirements", ())),
            "candidate_count": len(selection.get("candidate_ids", ())),
            "mapping_count": len(selection.get("mappings", ())),
            "coverage": coverage_value,
            "coverage_counts": dict(Counter(str(row.get("status")) for row in coverage)),
            "selected_memory_count": len(selected),
            "baseline_ids": selection.get("baseline_ids"),
            "baseline_count": baseline_count,
            "baseline_selected_count": baseline_selected,
            "baseline_retention_rate": (
                baseline_selected / baseline_count
                if baseline_count and baseline_selected is not None else None
            ),
            "raw_review_ids": selection.get("raw_review_ids"),
            "raw_review_count": diagnostics.get("evidence_raw_review_count"),
            "raw_selected_count": diagnostics.get("evidence_raw_selected_count"),
            "empty_context": diagnostics.get("evidence_empty_context"),
            "evidence_state": diagnostics.get("evidence_state"),
            "coverage_validation_complete": reliability.get("coverage_validation_complete"),
            "unassessed_requirement_count": reliability.get("unassessed_requirement_count"),
            "candidate_dispositions": dispositions,
            "candidate_disposition_counts": dict(Counter(str(row.get("disposition")) for row in dispositions)),
            "coverage_kind_normalizations": [
                {key: row.get(key) for key in ("requirement_id", "declared_kind", "kind", "normalization_reason")}
                for row in coverage if row.get("normalization_reason")
            ],
            "external_discovered": len(discovered - initial),
            "external_selected": len(selected - initial),
            "gap_probes": sum(row.get("stage") == "evidence_gap" for row in proposals),
            "removed_memories_across_revisions": sum(
                len(row.get("removed_ids", ())) for row in events if row.get("event") == "evidence_set_accepted"
            ),
            "diagnostics": selection.get("diagnostics"),
            "stop": selection.get("stop"),
        },
        "costs": {
            "ann_calls": costs.get("ann_calls"),
            "scored_sets": costs.get("scored_sets"),
            "reader_calls": costs.get("generator_calls"),
            "evidence_calls": costs.get("evidence_calls"),
            "evidence_reasoning": costs.get("evidence_reasoning"),
            "elapsed_ms": costs.get("elapsed_ms"),
        },
    }
