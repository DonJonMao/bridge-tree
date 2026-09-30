"""Conservative coverage labels and bounded-scope selection repair inputs.

These helpers do not establish semantic support, choose memories, or recover
invalid citations. The selector must validate provenance, requirement ownership
and selected-memory membership before deriving a coverage kind.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .evidence_spans import independent_premise_count


def derive_coverage_kind(
    declared_kind: str,
    status: str,
    facts: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    """Only weaken an explicit claim to inference; never assert coverage.

    In particular, a single partial premise or contradictions cannot become
    supporting facts here. The caller still checks that a ``covered`` status
    has support or at least two provenance-independent partial premises.
    """
    if declared_kind not in {"explicit", "inference"}:
        raise ValueError("coverage kind must be explicit or inference")
    if status not in {"covered", "partial", "missing", "ambiguous"}:
        raise ValueError("invalid coverage status")
    for fact in facts:
        if fact.get("kind") not in {"explicit", "inference"}:
            raise ValueError("mapped fact kind must be explicit or inference")
        if fact.get("relation") not in {"support", "partial", "contradiction"}:
            raise ValueError("invalid mapped fact relation")
    if declared_kind == "inference":
        return declared_kind, None

    reason = None
    if any(fact["kind"] == "inference" for fact in facts):
        reason = "cited_inferential_mapping"
    elif (
        status == "covered"
        and not any(fact["relation"] == "support" for fact in facts)
        and independent_premise_count(facts) >= 2
    ):
        reason = "joint_partial_inference"
    if reason is None:
        return declared_kind, None
    return "inference", {
        "declared_kind": declared_kind,
        "effective_kind": "inference",
        "status": status,
        "reason": reason,
        "evidence_ids": [fact["evidence_id"] for fact in facts if "evidence_id" in fact],
        "coverage_status_changed": False,
    }


def _unique_ids(values: Sequence[str], name: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of IDs")
    result = list(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{name} must contain nonempty string IDs")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not repeat IDs")
    return result


def compact_coverage_repair_payload(
    payload: Mapping[str, Any],
    *,
    pending_requirement_ids: Sequence[str],
    selected_ids: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Repair annotations for a fixed legal set without re-sending selection inputs.

    Preserve complete ledger records only for pending requirements and selected
    memories. No token-based trimming occurs here; the caller checks the final
    serialized request, including feedback and protocol overhead, before sending.
    Valid earlier coverage remains in the caller and is never regenerated.
    """
    pending = set(_unique_ids(pending_requirement_ids, "pending_requirement_ids"))
    selected = _unique_ids(selected_ids, "selected_ids")
    requirements = payload["requirements"]
    requirement_ids = _unique_ids([row["id"] for row in requirements], "requirement IDs")
    if pending - set(requirement_ids):
        raise ValueError("coverage repair names an unknown requirement")
    candidate_ids = set(_unique_ids(payload["candidate_ids"], "candidate_ids"))
    if set(selected) - candidate_ids:
        raise ValueError("coverage repair names an unavailable selected memory")

    ordered_pending = [identifier for identifier in requirement_ids if identifier in pending]
    selected_set = set(selected)
    ledger = payload["evidence_ledger"]
    kept = [
        row for row in ledger
        if row["requirement_id"] in pending and row["memory_id"] in selected_set
    ]
    value = {
        "query": deepcopy(payload["query"]),
        "requirements": deepcopy([row for row in requirements if row["id"] in pending]),
        "candidate_ids": list(selected),
        "evidence_ledger": deepcopy(kept),
        "allowed_evidence_by_requirement": {
            identifier: [row["evidence_id"] for row in kept if row["requirement_id"] == identifier]
            for identifier in ordered_pending
        },
        "repair_scope": {
            "requirement_ids": ordered_pending,
            "selected_ids": list(selected),
            "instruction": (
                "Keep selected_ids exactly as supplied, including order. Return the complete JSON header "
                "(selected_ids, conflicts, reason) and ONLY these pending coverage rows. "
                "Do not repeat previously validated coverage. Cite only the allowed evidence for each "
                "requirement; all supplied evidence belongs to the fixed selected set. "
                "If the available evidence cannot establish coverage, report an honest unresolved status. "
                "Do not add memories, invent evidence, or infer irrelevance from omitted/unassessed sources."
            ),
        },
    }
    # Preserve epistemic limitations, without treating evidence excluded by a
    # frozen-set repair as a new budget truncation or as proven irrelevance.
    if "mapping_incomplete" in payload:
        value["mapping_incomplete"] = deepcopy(payload["mapping_incomplete"])
    if "omitted_evidence_by_requirement" in payload:
        value["omitted_evidence_by_requirement"] = {
            identifier: deepcopy(payload["omitted_evidence_by_requirement"].get(identifier, 0))
            for identifier in ordered_pending
        }
    audit = {
        "policy_version": "coverage_repair_pending_selected_v3",
        "pending_requirement_ids": list(ordered_pending),
        "selected_ids": list(selected),
        "requirements_before": len(requirements),
        "requirements_after": len(value["requirements"]),
        "evidence_records_before": len(ledger),
        "evidence_records_after": len(kept),
        "retained_evidence_ids": [row["evidence_id"] for row in kept],
        "excluded_evidence_ids": [
            row["evidence_id"] for row in ledger
            if row["requirement_id"] not in pending or row["memory_id"] not in selected_set
        ],
    }
    return value, audit
