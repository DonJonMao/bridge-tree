from __future__ import annotations

import json
from dataclasses import replace

import pytest

from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.evidence_selection import (
    EvidenceInputBudgetExceeded,
    EvidenceSelectionInfeasible,
    EvidenceSelector,
    EvidenceValidationError,
    _parse,
)
from bridgetree.personamem import messages_to_memories
from bridgetree.types import Memory

REQUIREMENT = {
    "id": "r1",
    "description": "earlier learning experience explaining the change",
    "necessary": True,
    "time_scope": "earlier experience",
}


def feasible(ids):
    return {
        "feasible": True,
        "token_count": 100 + len(ids) * 100,
        "budget": 1000,
        "reason": "within_budget",
        "context_hash": "test",
        "options": "MUST_NOT_REACH_EVIDENCE",
    }


def records(*texts):
    values = messages_to_memories(
        [{"role": "user", "content": text} for text in texts], "q", memory_granularity="user_only"
    )
    return {m.memory_id: m for m in values}


class ScriptedBackend:
    def __init__(self, *, map_response=None, select_response=None, plan_response=None):
        self.requests = []
        self.map_response = map_response
        self.select_response = select_response
        self.plan_response = plan_response
        self.selection_count = 0

    def complete_messages(self, messages, *, operation, max_tokens):
        payload = json.loads(messages[1]["content"])
        self.requests.append((operation, messages, max_tokens))
        if operation.startswith("evidence_plan"):
            value = self.plan_response(payload) if self.plan_response else {"requirements": [REQUIREMENT]}
        elif operation.startswith("evidence_map"):
            value = self.map_response(payload) if self.map_response else self.map_all(payload)
        elif operation.startswith("evidence_select"):
            self.selection_count += 1
            value = (
                self.select_response(payload, self.selection_count)
                if self.select_response
                else self.select_all(payload)
            )
        else:
            raise AssertionError(operation)
        return value if isinstance(value, str) else json.dumps(value)

    @staticmethod
    def map_all(payload):
        return {
            "units": [
                {
                    "unit_id": unit["unit_id"],
                    "assessments": [
                        {
                            "requirement_id": "r1",
                            "claim": "a relevant earlier experience",
                            "kind": "explicit",
                            "relation": "support",
                            "time_scope": "earlier",
                            "span_ids": [unit["span_id"]],
                        }
                    ] if unit["provenance"] != "unknown_gap" and unit["text"].strip() else [],
                    "irrelevance_reason": "Structural text only" if unit["provenance"] == "unknown_gap" else "",
                }
                for unit in payload["units"]
            ]
        }

    @staticmethod
    def select_all(payload):
        facts = payload["evidence_ledger"]
        return selection(payload["candidate_ids"], facts)


def selection(ids, facts, *, status=None):
    facts = [f for f in facts if f["memory_id"] in ids]
    return {
        "selected_ids": list(ids),
        "coverage": [
            {
                "requirement_id": "r1",
                "status": status or ("covered" if facts else "missing"),
                "evidence_ids": [f["evidence_id"] for f in facts] if status != "missing" else [],
                "kind": "inference" if any(f["kind"] == "inference" for f in facts) else "explicit",
                "explanation": "Earlier source explains the experience" if facts else "Historical evidence is missing",
            }
        ],
        "conflicts": [],
        "reason": "joint source coverage",
    }


def make_selector(backend=None, settings=None, feasibility=feasible, sink=None):
    return EvidenceSelector(
        backend or ScriptedBackend(),
        settings or EvidenceSelectionConfig(),
        generation_feasible=feasibility,
        event_sink=sink,
    )


def test_frozen_query_only_plan_all_candidates_and_reader_callback_does_not_leak_options():
    bank = records("Flashcards were not conducive to deep learning.", "Now I would like another approach.")
    backend = ScriptedBackend()
    events = []
    selector = make_selector(backend, sink=events.append)
    plan = selector.plan("Why did I change learning method?")
    result = selector.select("Why did I change learning method?", bank, tuple(bank), requirements=plan)
    assert result.selected_ids == tuple(bank)
    assert result.stop_reason == "requirements_covered"
    assert result.costs["evidence_llm_calls"] == 3
    assert result.diagnostics["evidence_unmapped_candidates"] == 0
    assert json.loads(backend.requests[0][1][1]["content"]) == {
        "query": "Why did I change learning method?",
        "max_requirements": 6,
    }
    serialized = json.dumps(backend.requests)
    assert "MUST_NOT_REACH_EVIDENCE" not in serialized
    assert all(f["quote_verified"] for f in result.mappings)
    assert result.public_dict()["requests"][-1]["validation_status"] == "valid"
    assert {e["module"] for e in events} >= {"planner", "evidence", "selection"}
    assert all(step.public_dict()["event"] for step in result.steps)
    plan[0]["description"] = "tampered"
    assert result.requirements[0]["description"] == REQUIREMENT["description"]


def test_source_segments_preserve_embedded_assistant_marker_and_actual_speaker():
    memory = messages_to_memories([
        {"role": "user", "content": "I wrote this:\n\nAssistant:\nI hate flashcards."},
        {"role": "assistant", "content": "Try drawing maps."},
    ], "q")[0]
    result = make_selector().select("Why change?", {memory.memory_id: memory}, [memory.memory_id])
    assert {fact["role"] for fact in result.mappings} == {"user", "assistant"}
    for fact in result.mappings:
        for fragment in fact["fragments"]:
            assert memory.text[fragment["start"]:fragment["end"]] == fragment["quote"]
            assert len(fragment["quote"]) <= 400
    user_facts = [fact for fact in result.mappings if fact["role"] == "user"]
    assert any("Assistant:" in part["quote"] for fact in user_facts for part in fact["fragments"])

def test_legacy_role_markers_do_not_claim_authoritative_user():
    memory = Memory("old", "User:\nI disliked cards.", 1, "source", {"roles": ["user"]})
    result = make_selector().select("Why change?", {"old": memory}, ["old"])
    assert result.mappings[0]["role"] == "unknown"


def test_identical_text_from_different_speakers_is_grounded_to_selected_occurrence():
    memory = messages_to_memories([
        {"role": "user", "content": "same phrase"}, {"role": "assistant", "content": "same phrase"},
    ], "q")[0]
    result = make_selector().select("Why?", {memory.memory_id: memory}, [memory.memory_id])
    assert [fact["role"] for fact in result.mappings] == ["user", "assistant"]
    assert [fact["fragments"][0]["quote"] for fact in result.mappings] == ["same phrase", "same phrase"]
    assert result.mappings[0]["span_ids"] != result.mappings[1]["span_ids"]


def test_multi_span_assessment_preserves_original_fragments_and_mixed_roles():
    memory = messages_to_memories([
        {"role": "user", "content": "I disliked cards."}, {"role": "assistant", "content": "Try maps."},
    ], "q")[0]

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        sources = [unit for unit in payload["units"] if unit["role"] in {"user", "assistant"}]
        for row in value["units"]:
            for assessment in row["assessments"]:
                assessment["span_ids"] = [unit["span_id"] for unit in sources]
        return value

    result = make_selector(ScriptedBackend(map_response=mapping)).select(
        "Why?", {memory.memory_id: memory}, [memory.memory_id]
    )
    assert len(result.mappings) == 1  # Same assessment repeated under another owner is deduplicated.
    fact = result.mappings[0]
    assert fact["role"] == "ambiguous"
    assert {part["role"] for part in fact["fragments"]} == {"user", "assistant"}
    for part in fact["fragments"]:
        assert memory.text[part["start"]:part["end"]] == part["quote"]

def test_complete_long_candidate_is_split_without_losing_tail():
    text = "earlier " * 1200 + "the final reason is deep learning"
    bank = records(text)
    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=4000, max_llm_calls=64)
    result = make_selector(settings=settings).select("Why change?", bank, list(bank))
    ranges = [(e["start"], e["end"]) for e in result.artifact["exposures"]]
    assert len(ranges) > 1
    covered = set()
    for left, right in ranges:
        covered.update(range(left, right))
    memory = next(iter(bank.values()))
    assert covered == set(range(len(memory.text)))
    assert any("deep learning" in fragment["quote"] for fact in result.mappings for fragment in fact["fragments"])
    assert all(e["status"] == "mapped" for e in result.artifact["exposures"])


def test_feedback_maps_new_ids_and_whole_selection_removes_previous_memory():
    bank = records("A vague old idea.", "Flashcards were not conducive to deep learning.")
    old, new = bank

    def choose(payload, turn):
        return selection(
            [old] if turn == 1 else [new], payload["evidence_ledger"], status="partial" if turn == 1 else "covered"
        )

    calls = []

    def expand(missing, selected_ids):
        calls.append((missing, selected_ids))
        return [old, new]

    selector = make_selector(ScriptedBackend(select_response=choose))
    result = selector.select("Why change?", bank, [old], expand=expand)
    assert result.selected_ids == (new,)
    assert calls[0][0][0]["description"] == REQUIREMENT["description"]
    assert calls[0][1] == (old,)
    assert result.diagnostics["evidence_feedback_rounds"] == 1
    assert result.diagnostics["evidence_mapped_candidates"] == 2
    accepted = [s.public_dict() for s in result.steps if s.public_dict()["event"] == "evidence_set_accepted"]
    assert accepted[-1]["removed_ids"] == [old]
    assert accepted[-1]["added_ids"] == [new]


def test_actual_context_budget_causes_complete_revision_not_silent_truncation():
    bank = records("one fact", "second fact")
    ids = list(bank)

    def capacity(values):
        return {"feasible": len(values) <= 1, "token_count": 100 + len(values) * 100, "budget": 200}

    def choose(payload, turn):
        if turn == 2:
            assert payload["reader_budget_rejection"]["selected_ids"] == ids
        return selection(ids if turn == 1 else [ids[1]], payload["evidence_ledger"])

    result = make_selector(ScriptedBackend(select_response=choose), feasibility=capacity).select("Why?", bank, ids)
    assert result.selected_ids == (ids[1],)
    assert result.diagnostics["evidence_selection_revisions"] == 1
    assert [r["accepted"] for r in result.artifact["selection_rounds"]] == [False, True]


def test_infeasible_set_exhausts_revision_budget_and_retains_rejections():
    bank = records("fact")

    def reject(ids):
        return {"feasible": not ids, "token_count": 1000 if ids else 100, "budget": 200}

    selector = make_selector(settings=replace(EvidenceSelectionConfig(), max_selection_revisions=1), feasibility=reject)
    with pytest.raises(EvidenceSelectionInfeasible):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert len(partial["selection_rounds"]) == 2
    assert partial["selected_ids"] == []
    assert partial["stop_reason"] == "execution_error"


@pytest.mark.parametrize("corruption", ["unknown_span", "missing_unit", "fake_role", "unknown_requirement"])
def test_invalid_map_rows_are_rejected_locally_and_never_fabricate_coverage(corruption):
    bank = records("An authentic fact")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        if corruption == "missing_unit":
            value["units"] = []
        else:
            for row in value["units"]:
                for assessment in row["assessments"]:
                    if corruption == "unknown_span":
                        assessment["span_ids"] = ["invented_source"]
                    elif corruption == "fake_role":
                        assessment["role"] = "user"
                    else:
                        assessment["requirement_id"] = "wrong"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping), replace(EvidenceSelectionConfig(), max_json_repairs=0)
    )
    selector.requirements = (dict(REQUIREMENT),)
    units = selector._make_units("Why?", next(iter(bank.values())))
    with pytest.raises(EvidenceValidationError):
        selector._validate_map(mapping({"units": units}), units)
    result = selector.select("Why?", bank, list(bank), requirements=(dict(REQUIREMENT),))
    invalid = [request for request in result.artifact["requests"] if request["validation_status"] == "invalid"]
    assert invalid and all(request["raw_response"] for request in invalid)
    assert result.diagnostics["evidence_unmapped_candidates"] == 1
    assert result.diagnostics["partially_mapped"] is True
    assert result.selected_ids == ()
    assert result.coverage[0]["status"] == "missing"
    assert not result.mappings

def test_covered_without_quoted_support_is_rejected():
    bank = records("unrelated")

    def mapping(payload):
        return {
            "units": [
                {"unit_id": u["unit_id"], "assessments": [], "irrelevance_reason": "irrelevant"}
                for u in payload["units"]
            ]
        }

    def choose(payload, turn):
        value = selection([], [])
        value["coverage"][0]["status"] = "covered"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping, select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0, allow_unassessed_coverage=False),
    )
    with pytest.raises(EvidenceValidationError, match="supporting evidence"):
        selector.select("Why?", bank, list(bank))


def test_format_repair_counts_against_local_global_and_call_budgets():
    count = 0

    def planner(payload):
        nonlocal count
        count += 1
        return "{broken" if count == 1 else {"requirements": [REQUIREMENT]}

    bank = records("fact")
    backend = ScriptedBackend(plan_response=planner)
    result = make_selector(backend).select("Why?", bank, list(bank))
    assert result.costs["evidence_llm_calls"] == 4
    assert result.costs["evidence_json_repairs"] == 1
    assert backend.requests[1][0] == "evidence_plan_repair"
    assert result.diagnostics["evidence_validation_failures"] == 1


def test_small_call_budget_reserves_legal_empty_selection_and_reports_unmapped_sources():
    bank = records("fact")
    backend = ScriptedBackend()
    result = make_selector(backend, replace(EvidenceSelectionConfig(), max_llm_calls=2)).select(
        "Why?", bank, list(bank)
    )
    assert result.costs["evidence_llm_calls"] == 2
    assert [operation for operation, _, _ in backend.requests] == ["evidence_plan", "evidence_select"]
    assert result.diagnostics["evidence_mapped_candidates"] == 0
    assert result.diagnostics["partially_mapped"] is True
    assert result.selected_ids == ()
    assert result.coverage[0]["status"] == "missing"


def test_complete_ledger_over_budget_is_record_truncated_with_visible_citation_scope():
    bank = records(*["word " * 30 + str(i) for i in range(14)])
    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=1800, input_token_budget=2200)
    backend = ScriptedBackend()
    selector = make_selector(backend, settings)
    result = selector.select("Why?", bank, list(bank))
    assert result.diagnostics["evidence_mapped_candidates"] == len(bank)
    assert len(result.mappings) >= len(bank)
    assert result.diagnostics["selection_input_truncated"] is True
    assert result.diagnostics["reliability_status"] == "truncated"
    requests = [r for r in result.artifact["requests"] if r["operation"].startswith("evidence_select")]
    assert requests and all(r["input_tokens_estimate"] <= settings.input_token_budget for r in requests)
    payload = json.loads(requests[-1]["messages"][1]["content"])
    assert 0 < len(payload["evidence_ledger"]) < len(result.mappings)
    assert set(payload["candidate_ids"]) == {fact["memory_id"] for fact in payload["evidence_ledger"]}
    assert set(result.selected_ids) <= set(payload["candidate_ids"])
    assert result.artifact["selection_inputs"][-1]["truncated"] is True
    assert len(result.artifact["mappings"]) == len(result.mappings)


def test_irreducible_query_overflow_is_explicit_before_any_call():
    backend = ScriptedBackend()
    selector = make_selector(backend, replace(EvidenceSelectionConfig(), input_token_budget=1000,
                                               map_batch_token_budget=1000))
    with pytest.raises(EvidenceInputBudgetExceeded):
        selector.plan("不可裁剪的查询" * 2000)
    assert not backend.requests

def test_unresolved_empty_context_is_reported_honestly_and_feedback_can_stop():
    selector = make_selector()
    result = selector.select("Why?", {}, [], expand=lambda missing, ids: [])
    assert not result.selected_ids
    assert result.coverage[0]["status"] == "missing"
    assert result.stop_reason == "feedback_no_new_candidates"
    assert result.diagnostics["evidence_feedback_rounds"] == 1


def test_query_change_cannot_reuse_frozen_plan():
    selector = make_selector()
    selector.plan("first query")
    with pytest.raises(EvidenceValidationError, match="differs"):
        selector.select("second query", {}, [])


def test_a_later_map_failure_keeps_valid_sources_and_exact_offsets():
    bank = records(*[("words " * 100) + str(i) for i in range(3)])
    count = 0

    def mapping(payload):
        nonlocal count
        count += 1
        if count >= 2:
            return "{broken"
        return ScriptedBackend.map_all(payload)

    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=1600, max_json_repairs=0)
    result = make_selector(ScriptedBackend(map_response=mapping), settings).select("Why?", bank, list(bank))
    assert result.mappings
    assert result.diagnostics["partially_mapped"] is True
    assert any(exposure["status"] == "mapped" for exposure in result.artifact["exposures"])
    assert any(exposure["status"] != "mapped" for exposure in result.artifact["exposures"])
    assert any(request["raw_response"] == "{broken" for request in result.artifact["requests"])
    assert result.selected_ids
    for fact in result.mappings:
        for part in fact["fragments"]:
            assert bank[fact["memory_id"]].text[part["start"]:part["end"]] == part["quote"]

def test_inference_is_not_promoted_to_explicit_coverage():
    bank = records("user recorded a past feeling")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        next(row for row in value["units"] if row["assessments"])["assessments"][0]["kind"] = "inference"
        return value

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"][0]["kind"] = "explicit"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping, select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0),
    )
    result = selector.select("Why?", bank, list(bank))
    assert result.coverage[0]["declared_kind"] == "explicit"
    assert result.coverage[0]["kind"] == "inference"
    assert result.coverage[0]["normalization_reason"] == "cited_inferential_mapping"
    assert result.costs["evidence_json_repairs"] == 0


def test_selection_cannot_cite_evidence_from_removed_memory():
    bank = records("one relevant fact", "another relevant fact")

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["selected_ids"] = value["selected_ids"][:1]
        return value

    selector = make_selector(
        ScriptedBackend(select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0, allow_unassessed_coverage=False)
    )
    with pytest.raises(EvidenceValidationError, match="outside final selected set"):
        selector.select("Why?", bank, list(bank))


def test_malformed_non_scalar_model_field_is_typed_failure_and_repairable():
    bank = records("one authentic fact")
    count = 0

    def mapping(payload):
        nonlocal count
        count += 1
        value = ScriptedBackend.map_all(payload)
        if count == 1:
            next(row for row in value["units"] if row["assessments"])["assessments"][0]["requirement_id"] = ["r1"]
        return value

    selector = make_selector(ScriptedBackend(map_response=mapping))
    result = selector.select("Why?", bank, list(bank))
    assert result.costs["evidence_json_repairs"] == 1
    assert result.stop_reason == "requirements_covered"


def test_global_repair_limit_cannot_be_reused_by_later_stage_but_valid_empty_selection_survives():
    count = 0

    def planner(payload):
        nonlocal count
        count += 1
        return "{bad" if count == 1 else {"requirements": [REQUIREMENT]}

    bank = records("a source")
    backend = ScriptedBackend(plan_response=planner, map_response=lambda payload: "{bad")
    selector = make_selector(backend, replace(EvidenceSelectionConfig(), max_json_repairs=1))
    result = selector.select("Why?", bank, list(bank))
    assert result.costs["evidence_json_repairs"] == 1
    assert sum(operation.endswith("_repair") for operation, _, _ in backend.requests) == 1
    assert result.selected_ids == ()
    assert result.coverage[0]["status"] == "missing"
    assert result.diagnostics["partially_mapped"] is True

def test_source_offsets_cannot_be_invalid_even_when_quote_exists():
    memory = Memory(
        "bad",
        "User:\nsource",
        1,
        "s",
        {"source_segments": [{"role": "user", "start": 0, "end": 100, "source_message_indices": [1]}]},
    )
    selector = make_selector()
    with pytest.raises(EvidenceValidationError, match="source segment offsets"):
        selector.select("Why?", {"bad": memory}, ["bad"])


def test_unknown_feedback_id_is_never_mapped_or_selected():
    bank = records("partial evidence")

    def choose(payload, turn):
        return selection(payload["candidate_ids"], payload["evidence_ledger"], status="partial")

    selector = make_selector(ScriptedBackend(select_response=choose))
    with pytest.raises(EvidenceValidationError, match="not a visible real memory"):
        selector.select("Why?", bank, list(bank), expand=lambda missing, ids: ["future_memory"])
    partial = selector.partial_public_dict()
    assert partial["selected_ids"] == list(bank)
    assert "future_memory" not in partial["candidate_ids"]


@pytest.mark.parametrize(
    "relations,kind,passes",
    [
        (["partial", "partial"], "inference", True),
        (["partial", "partial"], "explicit", True),
        (["partial"], "inference", False),
        (["contradiction", "contradiction"], "inference", False),
    ],
)
def test_joint_partial_evidence_can_cover_only_as_distinct_inference(relations, kind, passes):
    bank = records(*[f"different authentic premise {i}" for i in range(len(relations))])
    relation_by_id = dict(zip(bank, relations))

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        for unit, assessed in zip(payload["units"], value["units"]):
            for assessment in assessed["assessments"]:
                assessment["relation"] = relation_by_id[unit["memory_id"]]
        return value

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"][0]["kind"] = kind
        value["coverage"][0]["explanation"] = "These distinct premises jointly connect the experience and the reason"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping, select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0, allow_unassessed_coverage=False),
    )
    if passes:
        result = selector.select("Why?", bank, list(bank))
        assert result.coverage[0]["coverage_basis"] == "joint_inference"
        assert result.coverage[0]["kind"] == "inference"
        assert result.diagnostics["evidence_coverage_is_model_judgement"] is True
    else:
        with pytest.raises(EvidenceValidationError, match="supporting evidence"):
            selector.select("Why?", bank, list(bank))


def test_optional_gaps_do_not_spend_feedback_after_necessary_coverage():
    bank = records("a required historical fact")
    optional = {"id": "r2", "description": "optional extra context", "necessary": False, "time_scope": "unknown"}

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"].append(
            {
                "requirement_id": "r2",
                "status": "missing",
                "evidence_ids": [],
                "kind": "explicit",
                "explanation": "Optional detail is absent",
            }
        )
        return value

    def forbidden(missing, selected):
        raise AssertionError("Optional gap must not consume targeted retrieval")

    backend = ScriptedBackend(
        plan_response=lambda payload: {"requirements": [REQUIREMENT, optional]}, select_response=choose
    )
    result = make_selector(backend).select("Why?", bank, list(bank), expand=forbidden)
    assert result.stop_reason == "necessary_requirements_covered"
    assert result.coverage[1]["status"] == "missing"
    assert result.diagnostics["evidence_missing_requirements"] == 1
    assert result.diagnostics["evidence_feedback_rounds"] == 0


def test_plan_with_only_optional_requirements_is_rejected():
    backend = ScriptedBackend(plan_response=lambda payload: {"requirements": [{**REQUIREMENT, "necessary": False}]})
    selector = make_selector(backend, replace(EvidenceSelectionConfig(), max_json_repairs=0))
    with pytest.raises(EvidenceValidationError, match="at least one necessary"):
        selector.plan("Why?")


def test_keyboard_interrupt_records_attempt_and_partial_exposure_without_repair():
    class InterruptedBackend(ScriptedBackend):
        def complete_messages(self, messages, *, operation, max_tokens):
            if operation == "evidence_map":
                raise KeyboardInterrupt("user interrupted")
            return super().complete_messages(messages, operation=operation, max_tokens=max_tokens)

    bank = records("source fact")
    selector = make_selector(InterruptedBackend())
    with pytest.raises(KeyboardInterrupt):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict(stop_reason="interrupted")
    assert partial["requests"][-1]["error_type"] == "KeyboardInterrupt"
    assert partial["requests"][-1]["elapsed_ms"] >= 0
    assert partial["exposures"][-1]["status"] == "requested_but_not_validated"
    assert partial["costs"]["evidence_json_repairs"] == 0
    assert partial["costs"]["evidence_llm_calls"] == 2
    assert partial["stop_reason"] == "interrupted"


@pytest.mark.parametrize("wrapped", [
    '\ufeff {"value":"原文🙂"}',
    '```json\r\n{"value":"原文🙂"}\r\n```',
    '```JSON\n{"value":"原文🙂"}\n```',
    'Here is the result:\n{"value":"原文🙂"}\nEnd of response.',
])
def test_complete_unique_json_wrapper_does_not_change_source_content(wrapped):
    assert _parse(wrapped) == {"value": "原文🙂"}


@pytest.mark.parametrize("invalid", [
    '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
    '{"outer":{"inner":1}', '{"x":1', '{"x":1}{"x":2}',
    '```json\n{"x":1}', 'true {"x":1}', '{"x":1} null',
    '[{"x":1}]', '[1] {"x":1}', '', 'no json here',
])
def test_parser_never_salvages_incomplete_ambiguous_or_nonfinite_json(invalid):
    with pytest.raises(EvidenceValidationError):
        _parse(invalid)


def test_one_bad_assessment_retains_good_fact_and_repairs_only_pending_unit():
    bank = records("One authentic fact.", "Another authentic fact.")
    count = 0
    retained_claim = "This valid original assessment must survive unchanged"

    def mapping(payload):
        nonlocal count
        count += 1
        value = ScriptedBackend.map_all(payload)
        assessed = [row for row in value["units"] if row["assessments"]]
        if count == 1:
            assessed[0]["assessments"][0]["claim"] = retained_claim
            bad = {**assessed[-1]["assessments"][0], "relation": "made_up_relation", "claim": "Repair this only"}
            assessed[-1]["assessments"].append(bad)
        else:
            assert len(payload["units"]) == 1
            assert payload["repair_scope"]["unit_ids"] == [payload["units"][0]["unit_id"]]
            assert retained_claim in json.dumps(payload["repair_scope"], ensure_ascii=False)
            assert "raw_response" not in payload
            assessed[0]["assessments"][0]["claim"] = "Repair this only"
        return value

    backend = ScriptedBackend(map_response=mapping)
    result = make_selector(backend).select("Why?", bank, list(bank))
    assert count == 2
    assert result.costs["evidence_json_repairs"] == 1
    assert sum(fact["claim"] == retained_claim for fact in result.mappings) == 1
    assert len(result.mappings) == 3
    assert result.diagnostics["partially_mapped"] is False
    assert result.selected_ids == tuple(bank)


def test_partially_valid_assessment_remains_eligible_after_failed_local_recovery():
    bank = records("Valid underlying evidence.")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        for row in value["units"]:
            if row["assessments"]:
                row["assessments"].append({**row["assessments"][0], "span_ids": ["invented"]})
        return value

    result = make_selector(ScriptedBackend(map_response=mapping)).select("Why?", bank, list(bank))
    assert result.selected_ids == tuple(bank)
    assert len(result.mappings) == 1
    assert result.costs["evidence_json_repairs"] == 2
    assert result.diagnostics["evidence_mapped_candidates"] == 0
    assert result.diagnostics["eligible_memory_count"] == 1
    assert result.diagnostics["partially_mapped"] is True
    assert result.coverage[0]["status"] == "covered"


def test_explicit_output_truncation_splits_mapping_batch_and_keeps_metadata():
    class TruncatedBackend(ScriptedBackend):
        def complete_evidence_messages(self, messages, *, operation, max_tokens, response_format, json_schema):
            raw = self.complete_messages(messages, operation=operation, max_tokens=max_tokens)
            payload = json.loads(messages[1]["content"])
            truncated = operation.startswith("evidence_map") and len(payload["units"]) > 2
            return {"content": '{"units":[' if truncated else raw,
                    "finish_reason": "length" if truncated else "stop", "refusal": None,
                    "usage": {"completion_tokens": 30}, "response_id": f"response_{len(self.requests)}",
                    "protocol": response_format, "response_error": None}

    bank = records("One fact.", "Two facts.", "Three facts.", "Four facts.")
    result = make_selector(TruncatedBackend()).select("Why?", bank, list(bank))
    requests = result.artifact["requests"]
    length_failures = [r for r in requests if r.get("failure_category") == "output_truncated"]
    assert length_failures
    assert all(r["response_metadata"]["finish_reason"] == "length" for r in length_failures)
    assert all(r["response_metadata"]["response_id"] for r in length_failures)
    assert all(r["operation"] == "evidence_map" for r in length_failures)
    assert result.costs["evidence_json_repairs"] == 0
    assert result.diagnostics["evidence_mapped_candidates"] == len(bank)
    assert result.selected_ids == tuple(bank)


def test_same_source_can_support_two_requirements_but_coverage_repairs_wrong_alias_locally():
    requirement2 = {**REQUIREMENT, "id": "r2", "description": "later learning experience"}
    bank = records("Before I struggled; later the new method helped.")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        for row in value["units"]:
            if row["assessments"]:
                row["assessments"].append({**row["assessments"][0], "requirement_id": "r2"})
        return value

    def choose(payload, turn):
        groups = payload["allowed_evidence_by_requirement"]
        ids = payload["candidate_ids"]
        result = selection(ids, [f for f in payload["evidence_ledger"] if f["requirement_id"] == "r1"])
        result["coverage"][0]["explanation"] = "This validated r1 row must remain unchanged"
        row2 = {"requirement_id": "r2", "status": "covered", "kind": "explicit",
                "explanation": "Later source under its own requirement", "evidence_ids": groups["r2"]}
        if turn == 1:
            row2["evidence_ids"] = groups["r1"]  # Existing production failure: wrong requirement's alias.
            result["coverage"].append(row2)
        else:
            assert payload["repair_scope"]["requirement_ids"] == ["r2"]
            assert payload["repair_scope"]["selected_ids"] == ids
            assert "different requirement" in payload["validation_feedback"]
            assert "allowed=" in payload["validation_feedback"]
            result["coverage"] = [row2]
        return result

    backend = ScriptedBackend(plan_response=lambda payload: {"requirements": [REQUIREMENT, requirement2]},
                              map_response=mapping, select_response=choose)
    result = make_selector(backend).select("What changed?", bank, list(bank))
    assert backend.selection_count == 2
    assert result.costs["evidence_json_repairs"] == 1
    assert result.coverage[0]["explanation"] == "This validated r1 row must remain unchanged"
    assert [row["status"] for row in result.coverage] == ["covered", "covered"]
    assert result.coverage[0]["evidence_ids"] != result.coverage[1]["evidence_ids"]
    assert all(alias.startswith("r2_e") for alias in result.coverage[1]["cited_aliases"])


def test_truncated_ledger_cannot_cite_a_persistent_fact_omitted_from_actual_input():
    bank = records(*["source " * 30 + str(index) for index in range(14)])
    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=1800, input_token_budget=2200)
    selector = make_selector(settings=settings)
    result = selector.select("Why?", bank, list(bank))
    audit = result.artifact["selection_inputs"][-1]
    assert audit["dropped_evidence_ids"]
    forged = selection(result.selected_ids, [])
    forged["coverage"][0].update(status="covered", evidence_ids=[audit["dropped_evidence_ids"][0]])
    with pytest.raises(EvidenceValidationError, match="invisible evidence"):
        selector._validate_selection(forged)


def test_forced_sentence_splits_cannot_turn_one_partial_premise_into_covered_inference():
    bank = records("I did not " + "enjoy " * 25 + "the earlier approach.")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        for row in value["units"]:
            for assessment in row["assessments"]:
                assessment["relation"] = "partial"
        return value

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"][0]["kind"] = "inference"
        return value

    selector = make_selector(ScriptedBackend(map_response=mapping, select_response=choose),
                             replace(EvidenceSelectionConfig(), max_quote_chars=40, max_json_repairs=0,
                                     allow_unassessed_coverage=False))
    with pytest.raises(EvidenceValidationError, match="supporting evidence"):
        selector.select("Why?", bank, list(bank))
    assert len(selector.mappings) > 2


def test_empty_span_cannot_be_promoted_to_verified_support():
    record = Memory("empty", "", 0, "source")
    selector = make_selector()
    selector.requirements = (dict(REQUIREMENT),)
    units = selector._make_units("Why?", record)
    response = {"units": [{"unit_id": units[0]["unit_id"], "irrelevance_reason": "", "assessments": [{
        "requirement_id": "r1", "claim": "Invented support", "relation": "support", "kind": "explicit",
        "time_scope": "unknown", "span_ids": [units[0]["span_id"]],
    }]}]}
    with pytest.raises(EvidenceValidationError):
        selector._validate_map(response, units)


def test_real_but_unseen_span_and_cross_memory_span_are_rejected():
    selector = make_selector()
    selector.requirements = (dict(REQUIREMENT),)
    one = Memory("one", "Earlier fact. A later fact.", 0, "source1")
    two = Memory("two", "An unrelated person's source.", 0, "source2")
    units = selector._make_units("Why?", one)
    other_units = selector._make_units("Why?", two)
    response = ScriptedBackend.map_all({"units": units})
    response["units"][0]["assessments"][0]["span_ids"].append(other_units[0]["span_id"])
    with pytest.raises(EvidenceValidationError, match="visible source IDs"):
        selector._validate_map(response, units)
    response["units"].extend(ScriptedBackend.map_all({"units": other_units})["units"])
    with pytest.raises(EvidenceValidationError, match="same memory"):
        selector._validate_map(response, units + other_units)


def test_per_request_repair_limit_does_not_consume_whole_global_allowance():
    backend = ScriptedBackend(plan_response=lambda payload: "{broken")
    selector = make_selector(backend, replace(EvidenceSelectionConfig(), max_json_repairs=6,
                                               max_repairs_per_request=2))
    with pytest.raises(EvidenceValidationError):
        selector.plan("Why?")
    assert selector.costs["evidence_json_repairs"] == 2
    assert selector.costs["evidence_llm_calls"] == 3
    assert [operation for operation, _, _ in backend.requests] == [
        "evidence_plan", "evidence_plan_repair", "evidence_plan_repair",
    ]
    for _, messages, _ in backend.requests[1:]:
        payload = json.loads(messages[1]["content"])
        assert "validation_feedback" in payload
        assert "{broken" not in messages[1]["content"]


def test_completed_source_status_survives_later_transport_failure():
    from bridgetree.evidence_selection import MAP_PROMPT

    bank = records("First authenticated source.", "Second authenticated source.")
    sizing = make_selector()
    sizing.requirements = (REQUIREMENT,)
    first = sizing._make_units("Why?", next(iter(bank.values())))
    batch_limit = sizing._tokens(sizing._messages(MAP_PROMPT, sizing._map_payload("Why?", first)))
    calls = 0

    def mapping(payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("fixture transport failure")
        return ScriptedBackend.map_all(payload)

    selector = make_selector(ScriptedBackend(map_response=mapping),
                             replace(EvidenceSelectionConfig(), map_batch_token_budget=batch_limit + 10))
    with pytest.raises(RuntimeError, match="fixture transport"):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert partial["fully_mapped_ids"] == [next(iter(bank))]
    assert partial["mappings"]
    assert partial["exposures"][0]["status"] == "mapped"
    assert partial["exposures"][-1]["status"] == "requested_but_not_validated"
