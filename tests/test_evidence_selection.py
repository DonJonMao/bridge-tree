from __future__ import annotations

import json
from dataclasses import replace

import pytest

from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.evidence_selection import (
    EvidenceCallBudgetExceeded,
    EvidenceInputBudgetExceeded,
    EvidenceSelectionInfeasible,
    EvidenceSelector,
    EvidenceValidationError,
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
                            "quote": unit["text"][-min(50, len(unit["text"])) :],
                        }
                    ],
                    "irrelevance_reason": "",
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
    memories = messages_to_memories(
        [
            {"role": "user", "content": "I wrote this:\n\nAssistant:\nI hate flashcards."},
            {"role": "assistant", "content": "Try drawing maps."},
        ],
        "q",
    )
    memory = memories[0]

    def mapping(payload):
        return {
            "units": [
                {
                    "unit_id": unit["unit_id"],
                    "assessments": [
                        {
                            "requirement_id": "r1",
                            "claim": "recorded words",
                            "kind": "explicit",
                            "relation": "support",
                            "time_scope": "unknown",
                            "quote": quote,
                        }
                        for quote in ("I hate flashcards.", "Try drawing maps.")
                    ],
                    "irrelevance_reason": "",
                }
                for unit in payload["units"]
            ]
        }

    result = make_selector(ScriptedBackend(map_response=mapping)).select(
        "Why change?", {memory.memory_id: memory}, [memory.memory_id]
    )
    assert [fact["role"] for fact in result.mappings] == ["user", "assistant"]
    for fact in result.mappings:
        for occurrence in fact["quote_occurrences"]:
            assert memory.text[occurrence["start"] : occurrence["end"]] == fact["quote"]
    for segment in memory.metadata["source_segments"]:
        assert memory.text[segment["start"] : segment["end"]]


def test_legacy_role_markers_do_not_claim_authoritative_user():
    memory = Memory("old", "User:\nI disliked cards.", 1, "source", {"roles": ["user"]})
    result = make_selector().select("Why change?", {"old": memory}, ["old"])
    assert result.mappings[0]["role"] == "unknown"


def test_repeated_quote_across_speakers_is_marked_ambiguous():
    memory = messages_to_memories(
        [{"role": "user", "content": "same phrase"}, {"role": "assistant", "content": "same phrase"}], "q"
    )[0]

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        value["units"][0]["assessments"][0]["quote"] = "same phrase"
        return value

    result = make_selector(ScriptedBackend(map_response=mapping)).select(
        "Why?", {memory.memory_id: memory}, [memory.memory_id]
    )
    fact = result.mappings[0]
    assert fact["role"] == "ambiguous"
    assert {item["role"] for item in fact["quote_occurrences"]} == {"user", "assistant"}


def test_complete_long_candidate_is_split_without_losing_tail():
    text = "earlier " * 1200 + "the final reason is deep learning"
    bank = records(text)
    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=900)
    result = make_selector(settings=settings).select("Why change?", bank, list(bank))
    ranges = [(e["start"], e["end"]) for e in result.artifact["exposures"]]
    assert len(ranges) > 1
    covered = set()
    for left, right in ranges:
        covered.update(range(left, right))
    memory = next(iter(bank.values()))
    assert covered == set(range(len(memory.text)))
    assert any("deep learning" in fact["quote"] for fact in result.mappings)
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


@pytest.mark.parametrize("corruption", ["bad_quote", "missing_unit", "fake_role", "unknown_requirement"])
def test_mapping_contract_failures_are_explicit_and_preserve_raw_response(corruption):
    bank = records("An authentic fact")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        if corruption == "bad_quote":
            value["units"][0]["assessments"][0]["quote"] = "invented sentence"
        elif corruption == "missing_unit":
            value["units"] = []
        elif corruption == "fake_role":
            value["units"][0]["assessments"][0]["role"] = "user"
        else:
            value["units"][0]["assessments"][0]["requirement_id"] = "wrong"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping), replace(EvidenceSelectionConfig(), max_json_repairs=0)
    )
    with pytest.raises(EvidenceValidationError):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert partial["requests"][-1]["raw_response"]
    assert partial["requests"][-1]["validation_status"] == "invalid"
    assert partial["diagnostics"]["evidence_unmapped_candidates"] == 1
    assert partial["selected_ids"] == []


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
        replace(EvidenceSelectionConfig(), max_json_repairs=0),
    )
    with pytest.raises(EvidenceValidationError, match="supporting evidence"):
        selector.select("Why?", bank, list(bank))


def test_format_repair_is_once_per_task_and_counts_against_call_budget():
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


def test_calls_exhausted_before_selection_is_failure_not_dense_fallback():
    bank = records("fact")
    selector = make_selector(settings=replace(EvidenceSelectionConfig(), max_llm_calls=2))
    with pytest.raises(EvidenceCallBudgetExceeded):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert partial["costs"]["evidence_llm_calls"] == 2
    assert partial["diagnostics"]["evidence_mapped_candidates"] == 1
    assert partial["selected_ids"] == []


def test_complete_ledger_over_budget_fails_without_top_k_slice():
    bank = records(*["word " * 30 + str(i) for i in range(14)])
    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=1400, input_token_budget=1800)
    backend = ScriptedBackend()
    selector = make_selector(backend, settings)
    with pytest.raises(EvidenceInputBudgetExceeded, match="no truncation"):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert partial["diagnostics"]["evidence_mapped_candidates"] == len(bank)
    assert len(partial["mappings"]) >= len(bank)
    assert not any(operation == "evidence_select" for operation, _, _ in backend.requests)


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


def test_a_later_map_failure_keeps_prior_complete_candidates_and_original_quote_offsets():
    bank = records(*[("words " * 100) + str(i) for i in range(3)])
    count = 0

    def mapping(payload):
        nonlocal count
        count += 1
        if count == 2:
            return "{broken"
        return ScriptedBackend.map_all(payload)

    settings = replace(EvidenceSelectionConfig(), map_batch_token_budget=850, max_json_repairs=0)
    selector = make_selector(ScriptedBackend(map_response=mapping), settings)
    with pytest.raises(EvidenceValidationError):
        selector.select("Why?", bank, list(bank))
    partial = selector.partial_public_dict()
    assert 0 < partial["diagnostics"]["evidence_mapped_candidates"] < len(bank)
    assert partial["mappings"]
    assert partial["exposures"][0]["status"] == "mapped"
    assert partial["exposures"][-1]["status"] == "requested_but_not_validated"
    assert partial["requests"][-1]["raw_response"] == "{broken"


def test_inference_is_not_promoted_to_explicit_coverage():
    bank = records("user recorded a past feeling")

    def mapping(payload):
        value = ScriptedBackend.map_all(payload)
        value["units"][0]["assessments"][0]["kind"] = "inference"
        return value

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"][0]["kind"] = "explicit"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping, select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0),
    )
    with pytest.raises(EvidenceValidationError, match="cannot become explicit"):
        selector.select("Why?", bank, list(bank))


def test_selection_cannot_cite_evidence_from_removed_memory():
    bank = records("one relevant fact", "another relevant fact")

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["selected_ids"] = value["selected_ids"][:1]
        return value

    selector = make_selector(
        ScriptedBackend(select_response=choose), replace(EvidenceSelectionConfig(), max_json_repairs=0)
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
            value["units"][0]["assessments"][0]["requirement_id"] = ["r1"]
        return value

    selector = make_selector(ScriptedBackend(map_response=mapping))
    result = selector.select("Why?", bank, list(bank))
    assert result.costs["evidence_json_repairs"] == 1
    assert result.stop_reason == "requirements_covered"


def test_one_global_json_repair_cannot_be_reused_by_later_stage():
    count = 0

    def planner(payload):
        nonlocal count
        count += 1
        return "{bad" if count == 1 else {"requirements": [REQUIREMENT]}

    bank = records("a source")
    selector = make_selector(ScriptedBackend(plan_response=planner, map_response=lambda payload: "{bad"))
    with pytest.raises(EvidenceValidationError):
        selector.select("Why?", bank, list(bank))
    assert selector.costs["evidence_json_repairs"] == 1
    assert selector.costs["evidence_llm_calls"] == 3


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
        (["partial", "partial"], "explicit", False),
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
            assessed["assessments"][0]["relation"] = relation_by_id[unit["memory_id"]]
        return value

    def choose(payload, turn):
        value = ScriptedBackend.select_all(payload)
        value["coverage"][0]["kind"] = kind
        value["coverage"][0]["explanation"] = "These distinct premises jointly connect the experience and the reason"
        return value

    selector = make_selector(
        ScriptedBackend(map_response=mapping, select_response=choose),
        replace(EvidenceSelectionConfig(), max_json_repairs=0),
    )
    if passes:
        result = selector.select("Why?", bank, list(bank))
        assert result.coverage[0]["coverage_basis"] == "joint_inference"
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
