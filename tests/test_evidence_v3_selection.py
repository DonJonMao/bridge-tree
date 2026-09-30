"""Behavioral v3 checks: raw evidence reachability and honest local recovery."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from test_evidence_selection import REQUIREMENT, ScriptedBackend, feasible, records

from bridgetree.clients import HTTPTransportError, build_context_plan
from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.evidence_selection import MAP_PROMPT, EvidenceSelector, EvidenceValidationError


def irrelevant(payload):
    return {"units": [
        {"unit_id": unit["unit_id"], "assessments": [], "irrelevance_reason": "No mapped requirement."}
        for unit in payload["units"]
    ]}


def coverage(identifier="r1", *, status="missing", evidence_ids=(), explanation="No verified mapping."):
    return {
        "requirement_id": identifier, "status": status, "evidence_ids": list(evidence_ids),
        "kind": "explicit", "explanation": explanation,
    }


def proposal(ids, rows):
    return {"selected_ids": list(ids), "coverage": rows, "conflicts": [], "reason": "Review original history."}


def selector(backend, **settings):
    return EvidenceSelector(backend, EvidenceSelectionConfig(**settings), generation_feasible=feasible)


def run(value, bank, *, requirements=(REQUIREMENT,), baseline_ids=None):
    return value.select(
        "My activity has changed; respond using my history.", bank, list(bank), requirements=requirements,
        baseline_ids=list(bank) if baseline_ids is None else baseline_ids,
    )


def sent_payloads(value, operation):
    return [
        json.loads(request["messages"][1]["content"])
        for request in value.requests if request["operation"] == operation
    ]


def test_all_irrelevant_mapping_still_exposes_complete_baseline_and_reaches_reader_without_fake_support():
    bank = records("I disliked the old method because it hid the reasoning.")
    backend = ScriptedBackend(map_response=irrelevant, select_response=lambda p, _: proposal(
        p["candidate_ids"], [coverage()]
    ))
    value = selector(backend)
    result = run(value, bank)
    payload = sent_payloads(value, "evidence_select")[0]
    assert payload["candidate_ids"] == list(bank)
    assert payload["evidence_ledger"] == []
    assert payload["raw_memory_candidates"][0]["text"] == next(iter(bank.values())).text
    assert result.selected_ids == tuple(bank)
    assert result.mappings == ()
    assert result.coverage[0]["status"] == "missing"
    assert result.coverage[0]["evidence_ids"] == []
    assert result.coverage[0]["supporting_ids"] == []
    assert result.diagnostics["evidence_state"] == "raw_only"
    assert result.diagnostics["evidence_raw_selected_count"] == 1
    assert result.diagnostics["coverage_validation_complete"] is True
    reader = build_context_plan(
        "My activity has changed.", [bank[i] for i in result.selected_ids], "(a) old (b) new",
        token_budget=8192, selected_ids=result.selected_ids,
    )
    assert reader.within_budget
    assert next(iter(bank.values())).text in reader.messages[-1]["content"]


def test_disabling_raw_review_preserves_the_old_mapping_gate():
    bank = records("Earlier personal preference.")
    backend = ScriptedBackend(map_response=irrelevant, select_response=lambda p, _: proposal(
        p["candidate_ids"], [coverage()]
    ))
    value = selector(backend, raw_memory_review=False)
    result = run(value, bank)
    payload = sent_payloads(value, "evidence_select")[0]
    assert payload["candidate_ids"] == []
    assert payload["raw_memory_candidates"] == []
    assert result.selected_ids == ()
    assert result.diagnostics["evidence_empty_context"] is True


@pytest.mark.parametrize("filtered", [False, True])
def test_mapping_refusal_remains_terminal_instead_of_becoming_raw_review_success(filtered):
    bank = records("A relevant original memory.")

    class Backend:
        def complete_evidence_messages(self, messages, *, operation, **kwargs):
            assert operation == "evidence_map"  # No selection/reader continuation after refusal.
            return {"content": None, "refusal": None if filtered else "Refused.",
                    "finish_reason": "content_filter" if filtered else "stop"}

    value = selector(Backend())
    with pytest.raises(EvidenceValidationError, match="refused") as caught:
        run(value, bank)
    assert caught.value.category == "refusal"
    assert [request["operation"] for request in value.requests] == ["evidence_map"]
    assert value.requests[0]["failure_category"] == "refusal"
    assert value.selection_inputs == []
    assert value.partial_public_dict()["candidate_dispositions"][0]["disposition"] == "raw_review_pending"


def test_live_candidate_disposition_does_not_invent_input_budget_omission_before_raw_review():
    bank = records("An original memory awaiting independent review.")
    snapshots = {}
    backend = ScriptedBackend(map_response=irrelevant, select_response=lambda p, _: proposal(
        p["candidate_ids"], [coverage()]
    ))
    value = selector(backend)

    def capture(event):
        snapshots[event["event"]] = value.partial_public_dict()["candidate_dispositions"]

    value.event_sink = capture
    result = run(value, bank)
    assert snapshots["evidence_candidate_scope"][0]["disposition"] == "raw_review_pending"
    assert snapshots["evidence_mapping_batch_completed"][0]["disposition"] == "raw_review_pending"
    assert snapshots["evidence_raw_review_prepared"][0]["disposition"] == "raw_review_not_selected"
    assert result.artifact["candidate_dispositions"][0]["disposition"] == "selected_raw"
    assert all(row["disposition"] != "raw_review_input_budget" for rows in snapshots.values() for row in rows)


@pytest.mark.parametrize(
    "mapping_kind,relation,reason",
    [("inference", "support", "cited_inferential_mapping"),
     ("explicit", "partial", "joint_partial_inference")],
)
def test_coverage_kind_is_derived_after_citation_checks_without_spending_a_repair(mapping_kind, relation, reason):
    bank = records("An earlier user premise.", "A different later user premise.")

    def mapped(payload):
        output = ScriptedBackend.map_all(payload)
        for row in output["units"]:
            for assessment in row["assessments"]:
                assessment.update(kind=mapping_kind, relation=relation)
        return output

    backend = ScriptedBackend(map_response=mapped, select_response=lambda p, _: proposal(
        p["candidate_ids"], [coverage(status="covered", evidence_ids=p["allowed_evidence_by_requirement"]["r1"])]
    ))
    value = selector(backend)
    result = run(value, bank)
    row = result.coverage[0]
    assert row["status"] == "covered"
    assert row["kind"] == "inference"
    assert row["declared_kind"] == "explicit"
    assert row["normalization_reason"] == reason
    assert result.costs["evidence_json_repairs"] == 0
    assert all(fact["kind"] == mapping_kind and fact["relation"] == relation for fact in result.mappings)
    assert any(event["event"] == "evidence_coverage_kind_normalized" and event["reason"] == reason
               for event in value.events)


@pytest.mark.parametrize("select_hidden", [False, True])
def test_raw_input_omits_whole_records_and_hidden_raw_id_is_not_selectable(select_hidden):
    bank = records("Short original preference.", "A complete long original sentence. " * 2600)
    short_id, long_id = bank

    def select(payload, _):
        raw = payload["raw_memory_candidates"]
        assert [row["memory_id"] for row in raw] == [short_id]
        assert raw[0]["text"] == bank[short_id].text
        assert long_id not in payload["candidate_ids"]
        return proposal([long_id] if select_hidden else [short_id], [coverage()])

    value = selector(
        ScriptedBackend(map_response=irrelevant, select_response=select),
        max_json_repairs=0, max_repairs_per_request=0,
    )
    if select_hidden:
        with pytest.raises(EvidenceValidationError, match="invisible candidate"):
            run(value, bank)
        assert not any(event["event"] == "evidence_coverage_unassessed" for event in value.events)
    else:
        result = run(value, bank)
        assert result.selected_ids == (short_id,)
        assert result.diagnostics["selection_input_truncated"] is True
    audit = value.selection_inputs[-1]
    assert audit["truncated"] is True
    assert audit["raw_review_ids"] == [short_id]
    assert audit["omitted_raw_review_ids"] == [long_id]
    assert audit["input_tokens_after"] <= audit["selection_payload_limit"]
    assert all(r["input_tokens_estimate"] <= value.settings.input_token_budget for r in value.requests)


def two_requirements():
    return (REQUIREMENT, {**REQUIREMENT, "id": "r2", "description": "a distinct later need"})


def map_requirements(payload, *, raw_only_id=None):
    output = ScriptedBackend.map_all(payload)
    units = {unit["unit_id"]: unit for unit in payload["units"]}
    for row in output["units"]:
        if units[row["unit_id"]]["memory_id"] == raw_only_id:
            row.update(assessments=[], irrelevance_reason="No requirement mapping; retain for independent raw review.")
        elif row["assessments"]:
            first = row["assessments"][0]
            row["assessments"] = [{**first, "requirement_id": "r1"}, {**first, "requirement_id": "r2"}]
    return output


def test_bad_coverage_exhaustion_preserves_valid_rows_and_marks_unassessed_without_extra_gap():
    bank = records("The original user fact.")
    ids = list(bank)
    original_valid_row = None

    def select(payload, attempt):
        nonlocal original_valid_row
        if attempt == 1:
            alias = payload["allowed_evidence_by_requirement"]["r1"][0]
            original_valid_row = coverage("r1", status="covered", evidence_ids=[alias], explanation="Frozen proof.")
            return proposal(ids, [original_valid_row, coverage("r2", status="covered", evidence_ids=["invented"])])
        assert payload["repair_scope"]["requirement_ids"] == ["r2"]
        return proposal(ids, [coverage("r2", status="covered", evidence_ids=["still_invented"])])

    value = selector(
        ScriptedBackend(map_response=map_requirements, select_response=select),
        max_repairs_per_request=1,
    )
    result = run(value, bank, requirements=two_requirements())
    first, second = result.coverage
    assert first["status"] == "covered"
    assert first["explanation"] == "Frozen proof."
    assert first["cited_aliases"] == original_valid_row["evidence_ids"]
    assert first["validation_complete"] is True
    assert second["status"] == "unassessed"
    assert second["kind"] == "unknown"
    assert second["validation_complete"] is False
    assert second["evidence_ids"] == second["supporting_ids"] == []
    assert result.selected_ids == tuple(ids)
    assert result.stop_reason == "coverage_unassessed"
    assert result.diagnostics["reliability_status"] == "coverage_unassessed"
    assert result.diagnostics["coverage_validation_complete"] is False
    assert result.diagnostics["unassessed_requirement_count"] == 1
    assert result.diagnostics["evidence_feedback_rounds"] == 0
    assert result.costs["evidence_json_repairs"] == 1


def test_disabling_unassessed_recovery_keeps_bad_coverage_terminal():
    bank = records("Relevant raw text.")
    backend = ScriptedBackend(map_response=irrelevant, select_response=lambda p, _: proposal(
        p["candidate_ids"], [coverage(status="covered", evidence_ids=["invented"])]
    ))
    value = selector(backend, allow_unassessed_coverage=False, max_json_repairs=0, max_repairs_per_request=0)
    with pytest.raises(EvidenceValidationError, match="invisible evidence"):
        run(value, bank)


@pytest.mark.parametrize("failure", ["unknown_selected", "bad_header", "json", "http", "refusal"])
@pytest.mark.parametrize("after_valid_header", [False, True])
def test_noncoverage_failures_are_not_downgraded_even_after_a_valid_header(failure, after_valid_header):
    bank = records("An actual personal memory.")
    ids = list(bank)

    class Backend(ScriptedBackend):
        def complete_evidence_messages(self, messages, *, operation, max_tokens, **kwargs):
            payload = json.loads(messages[1]["content"])
            if operation.startswith("evidence_select"):
                self.selection_count += 1
                if after_valid_header and self.selection_count == 1:
                    result = proposal(ids, [coverage(status="covered", evidence_ids=["invented"])])
                elif failure == "http":
                    raise HTTPTransportError(attempts=1, status_code=503, retryable=True, cause_type="server")
                elif failure == "refusal":
                    return {"content": None, "finish_reason": "stop", "refusal": "Cannot comply."}
                elif failure == "unknown_selected":
                    result = proposal(["nonexistent"], [coverage()])
                elif failure == "bad_header":
                    result = {"selected_ids": ids, "coverage": [coverage()], "conflicts": []}
                elif failure == "json":
                    return {"content": '{"selected_ids":', "finish_reason": "stop", "refusal": None}
                else:
                    raise AssertionError(failure)
                return {"content": json.dumps(result), "finish_reason": "stop", "refusal": None}
            return {"content": json.dumps(irrelevant(payload)), "finish_reason": "stop", "refusal": None}

    value = selector(Backend(), max_repairs_per_request=1)
    expected = HTTPTransportError if failure == "http" else EvidenceValidationError
    with pytest.raises(expected):
        run(value, bank)
    assert not any(event["event"] == "evidence_coverage_unassessed" for event in value.events)


def test_successful_compact_repair_keeps_raw_only_selected_id_and_omits_frozen_and_unselected_evidence():
    bank = records("A mapped source.", "A useful original memory with no mapping.", "Another mapped candidate.")
    mapped, raw_only, unselected = bank
    original = None

    def select(payload, attempt):
        nonlocal original
        if attempt == 1:
            original = payload
            r1 = next(row["evidence_id"] for row in payload["evidence_ledger"]
                      if row["requirement_id"] == "r1" and row["memory_id"] == mapped)
            return proposal([mapped, raw_only], [coverage("r1", status="covered", evidence_ids=[r1]),
                                                 coverage("r2", status="covered", evidence_ids=[r1])])
        assert payload["candidate_ids"] == [mapped, raw_only]
        assert payload["repair_scope"]["selected_ids"] == [mapped, raw_only]
        assert [row["id"] for row in payload["requirements"]] == ["r2"]
        assert payload["evidence_ledger"]
        assert all(row["requirement_id"] == "r2" and row["memory_id"] == mapped
                   for row in payload["evidence_ledger"])
        assert unselected not in payload["candidate_ids"]
        assert not set(payload) & {"raw_memory_candidates", "candidate_costs", "previous_coverage"}
        assert len(json.dumps(payload)) < len(json.dumps(original))
        return proposal([mapped, raw_only], [coverage(
            "r2", status="covered", evidence_ids=payload["allowed_evidence_by_requirement"]["r2"]
        )])

    backend = ScriptedBackend(
        map_response=lambda p: map_requirements(p, raw_only_id=raw_only), select_response=select
    )
    value = selector(backend)
    result = run(value, bank, requirements=two_requirements())
    assert result.selected_ids == (mapped, raw_only)
    assert [row["status"] for row in result.coverage] == ["covered", "covered"]
    assert result.diagnostics["coverage_validation_complete"] is True
    assert result.diagnostics["evidence_state"] == "mixed"
    assert len(sent_payloads(value, "evidence_select_repair")) == 1
    assert all(r["input_tokens_estimate"] <= value.settings.input_token_budget for r in value.requests)


def test_mapping_cannot_spend_final_selection_calls_or_all_global_repair_slots():
    bank = records(*(f"Source {i}: " + "A previous personal preference. " * 8 for i in range(40)))
    first_id = next(iter(bank))

    def select(payload, attempt):
        if attempt == 1:
            return proposal([first_id], [coverage(status="covered", evidence_ids=["invented"])])
        return proposal([first_id], [coverage()])

    value = selector(ScriptedBackend(map_response=lambda p: "{", select_response=select))
    # A dynamic limit allows one complete source unit but not an accumulating
    # mapping batch, independent of changes to the system prompt's length.
    value.requirements = (REQUIREMENT,)
    query = "My activity has changed; respond using my history."
    units = [unit for memory in bank.values() for unit in value._make_units(query, memory)]
    single_budget = max(value._tokens(value._messages(MAP_PROMPT, value._map_payload(query, [u]))) for u in units) + 1
    value.settings = replace(value.settings, map_batch_token_budget=single_budget)
    result = run(value, bank, baseline_ids=[first_id])
    operations = [request["operation"] for request in value.requests]
    assert operations.count("evidence_map_repair") == 4  # Six global slots, two reserved for selection.
    assert operations.count("evidence_select_repair") == 1
    assert result.costs["evidence_llm_calls"] <= 24
    assert result.costs["evidence_json_repairs"] == 5
    assert result.diagnostics["partially_mapped"] is True
    assert result.selected_ids == (first_id,)
    assert result.coverage[0]["status"] == "missing"
    assert result.diagnostics["coverage_validation_complete"] is True
    assert any(event["event"] == "evidence_call_budget_exhausted" for event in value.events)
