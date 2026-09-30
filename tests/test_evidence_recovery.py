from __future__ import annotations

from copy import deepcopy

import pytest

from bridgetree.evidence_recovery import compact_coverage_repair_payload, derive_coverage_kind


def fact(identifier, *, memory="m1", kind="explicit", relation="support", start=0, group=None):
    return {
        "evidence_id": identifier,
        "assessment_id": "assessment_" + identifier,
        "memory_id": memory,
        "kind": kind,
        "relation": relation,
        "fragments": [{"start": start, "end": start + 10, "premise_group_ids": [group or identifier]}],
    }


def test_inferential_reference_only_weakens_label_and_preserves_source_decisions():
    facts = [fact("e1"), fact("e2", kind="inference")]
    before = deepcopy(facts)
    effective, audit = derive_coverage_kind("explicit", "covered", facts)
    assert effective == "inference"
    assert audit["reason"] == "cited_inferential_mapping"
    assert audit["declared_kind"] == "explicit"
    assert audit["effective_kind"] == "inference"
    assert audit["coverage_status_changed"] is False
    assert audit["evidence_ids"] == ["e1", "e2"]
    assert facts == before


def test_model_inference_is_never_upgraded_even_with_explicit_support():
    assert derive_coverage_kind("inference", "covered", [fact("e1")]) == ("inference", None)


def test_two_independent_partial_premises_need_inference():
    facts = [fact("e1", relation="partial"), fact("e2", memory="m2", relation="partial")]
    effective, audit = derive_coverage_kind("explicit", "covered", facts)
    assert effective == "inference"
    assert audit["reason"] == "joint_partial_inference"
    assert all(row["relation"] == "partial" for row in facts)


@pytest.mark.parametrize(
    "facts",
    [
        [],
        [fact("e1", relation="partial")],
        [fact("e1", relation="partial"), fact("e1", relation="partial")],
        [fact("e1", relation="partial"), fact("e2", relation="partial", start=5)],
        [fact("e1", relation="partial", group="same"),
         fact("e2", relation="partial", start=20, group="same")],
        [fact("e1", relation="contradiction"), fact("e2", memory="m2", relation="contradiction")],
        [fact("e1", relation="partial"), fact("e2", memory="m2", relation="contradiction")],
    ],
)
def test_insufficient_or_nonindependent_premises_do_not_get_joint_inference(facts):
    # This is not an approval of 'covered': the caller's sufficiency validator
    # must still reject it. No invented premise or support masks that failure.
    assert derive_coverage_kind("explicit", "covered", facts) == ("explicit", None)


def test_multiple_fragments_of_one_assessment_are_one_premise():
    row = fact("e1", relation="partial")
    row["fragments"].append({"start": 20, "end": 30, "premise_group_ids": ["another"]})
    assert derive_coverage_kind("explicit", "covered", [row]) == ("explicit", None)


@pytest.mark.parametrize("status", ["partial", "ambiguous"])
def test_unresolved_partial_facts_do_not_automatically_become_synthesis(status):
    facts = [fact("e1", relation="partial"), fact("e2", memory="m2", relation="partial")]
    assert derive_coverage_kind("explicit", status, facts) == ("explicit", None)


@pytest.mark.parametrize("kind,status", [("guess", "covered"), ("explicit", "unassessed")])
def test_invalid_model_enums_are_not_silently_normalized(kind, status):
    with pytest.raises(ValueError):
        derive_coverage_kind(kind, status, [])


@pytest.mark.parametrize("field,value", [("kind", "guess"), ("relation", "unrelated")])
def test_invalid_mapping_enums_are_not_treated_as_verified_facts(field, value):
    row = fact("e1")
    row[field] = value
    with pytest.raises(ValueError):
        derive_coverage_kind("explicit", "covered", [row])


def payload():
    return {
        "query": "How did my preference change?",
        "requirements": [
            {"id": "r1", "description": "earlier experience", "necessary": True, "time_scope": "past"},
            {"id": "r2", "description": "later experience", "necessary": True, "time_scope": "recent"},
        ],
        "candidate_ids": ["m1", "m2", "m3"],
        "evidence_ledger": [
            {"evidence_id": "r1_e1", "requirement_id": "r1", "memory_id": "m1",
             "fragments": [{"quote": "first"}]},
            {"evidence_id": "r2_e1", "requirement_id": "r2", "memory_id": "m1",
             "fragments": [{"quote": "later"}]},
            {"evidence_id": "r2_e2", "requirement_id": "r2", "memory_id": "m2",
             "fragments": [{"quote": "unselected"}]},
        ],
        "allowed_evidence_by_requirement": {"r1": ["r1_e1"], "r2": ["r2_e1", "r2_e2"]},
        "raw_memory_candidates": [{"memory_id": "m3", "text": "complete original text"}],
        "candidate_costs": [{"memory_id": "m1", "raw_memory_tokens_estimate": 100}],
        "previous_coverage": [{"requirement_id": "r1", "status": "covered"}],
        "previous_selected_ids": ["m2"],
        "reader_budget_rejection": {"selected_ids": ["m2"]},
        "mapping_incomplete": True,
        "omitted_evidence_by_requirement": {"r1": 2, "r2": 3},
        "validation_feedback": "Stale, long feedback from an earlier request.",
    }


def test_repair_only_exposes_pending_requirements_and_selected_legal_sources():
    original = payload()
    before = deepcopy(original)
    value, audit = compact_coverage_repair_payload(
        original, pending_requirement_ids=["r2"], selected_ids=["m1", "m3"]
    )
    assert value["query"] == original["query"]
    assert value["requirements"] == [original["requirements"][1]]
    assert value["candidate_ids"] == ["m1", "m3"]  # Raw-only selected memory stays in fixed header.
    assert value["evidence_ledger"] == [original["evidence_ledger"][1]]
    assert value["allowed_evidence_by_requirement"] == {"r2": ["r2_e1"]}
    assert value["repair_scope"]["selected_ids"] == ["m1", "m3"]
    assert value["repair_scope"]["requirement_ids"] == ["r2"]
    assert "selected_ids, conflicts, reason" in value["repair_scope"]["instruction"]
    assert value["mapping_incomplete"] is True
    assert value["omitted_evidence_by_requirement"] == {"r2": 3}
    assert audit["retained_evidence_ids"] == ["r2_e1"]
    assert audit["excluded_evidence_ids"] == ["r1_e1", "r2_e2"]
    assert audit["evidence_records_before"] == 3
    assert audit["evidence_records_after"] == 1
    assert not set(value) & {
        "raw_memory_candidates", "candidate_costs", "previous_coverage",
        "previous_selected_ids", "reader_budget_rejection", "validation_feedback",
    }
    assert original == before
    value["evidence_ledger"][0]["fragments"][0]["quote"] = "edited copy"
    value["requirements"][0]["description"] = "edited copy"
    assert original == before


def test_repair_preserves_canonical_requirement_order_and_fixed_selected_order():
    value, _ = compact_coverage_repair_payload(
        payload(), pending_requirement_ids=["r2", "r1"], selected_ids=["m3", "m1"]
    )
    assert value["repair_scope"]["requirement_ids"] == ["r1", "r2"]
    assert value["candidate_ids"] == ["m3", "m1"]
    assert value["repair_scope"]["selected_ids"] == ["m3", "m1"]


def test_empty_selected_set_does_not_make_unselected_support_available():
    value, audit = compact_coverage_repair_payload(payload(), pending_requirement_ids=["r1"], selected_ids=[])
    assert value["evidence_ledger"] == []
    assert value["allowed_evidence_by_requirement"] == {"r1": []}
    assert value["candidate_ids"] == []
    assert audit["evidence_records_after"] == 0


def test_no_pending_requirements_never_repeats_validated_coverage():
    value, _ = compact_coverage_repair_payload(payload(), pending_requirement_ids=[], selected_ids=["m1"])
    assert value["requirements"] == []
    assert value["evidence_ledger"] == []
    assert value["allowed_evidence_by_requirement"] == {}
    assert value["candidate_ids"] == ["m1"]


@pytest.mark.parametrize(
    "pending,selected",
    [(["unknown"], ["m1"]), (["r1"], ["unknown"]), (["r1", "r1"], ["m1"]),
     (["r1"], ["m1", "m1"]), ("r1", ["m1"]), (["r1"], "m1"), ([""], ["m1"])],
)
def test_repair_rejects_invalid_scopes_instead_of_expanding_selection(pending, selected):
    with pytest.raises(ValueError):
        compact_coverage_repair_payload(payload(), pending_requirement_ids=pending, selected_ids=selected)


def test_repair_does_not_truncate_a_large_relevant_fact_to_appear_within_budget():
    original = payload()
    original["evidence_ledger"][0]["fragments"][0]["quote"] = "a" * 20000
    value, _ = compact_coverage_repair_payload(original, pending_requirement_ids=["r1"], selected_ids=["m1"])
    assert value["evidence_ledger"][0] == original["evidence_ledger"][0]
    # Final serialized-token enforcement belongs to EvidenceSelector._request.
