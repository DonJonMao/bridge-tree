from __future__ import annotations

from dataclasses import replace

import pytest

from bridgetree.evidence_spans import (
    SourceSpanValidationError,
    independent_premise_count,
    source_segments,
    source_units,
)
from bridgetree.personamem import messages_to_memories
from bridgetree.types import Memory


def memory(text, *, segments=None):
    metadata = {} if segments is None else {"source_segments": segments}
    return Memory("m1", text, 5, "source1", metadata)


def fact(*units, assessment_id="a1", relation="partial"):
    return {
        "memory_id": units[0]["memory_id"], "assessment_id": assessment_id, "relation": relation,
        "fragments": [{
            "span_id": unit["span_id"], "start": unit["start"], "end": unit["end"],
            "quote": unit["text"], "premise_group_ids": unit["premise_group_ids"],
        } for unit in units],
    }


@pytest.mark.parametrize("limit", [1, 7, 31, 400])
def test_multilingual_source_is_exact_contiguous_complete_and_bounded(limit):
    text = "我以前并不喜欢。\r\nNow I use cards.🙂 Café e\u0301 👩‍🔬\n\n" + "极长句且无标点" * 110 + "。末尾很重要。"
    record = memory(text)
    units = source_units(record, limit)
    assert "".join(unit["text"] for unit in units) == text
    assert len({unit["span_id"] for unit in units}) == len(units)
    assert units[0]["start"] == 0
    assert units[-1]["end"] == len(text)
    for index, unit in enumerate(units):
        assert unit["text"] == record.text[unit["start"]:unit["end"]]
        assert 0 < len(unit["text"]) <= limit
        assert unit["unit_id"] == unit["span_id"]
        if index:
            assert units[index - 1]["end"] == unit["start"]
            assert unit["previous_span_id"] == units[index - 1]["span_id"]
            assert units[index - 1]["next_span_id"] == unit["span_id"]


def test_role_markers_are_not_authority_and_gaps_remain_unknown():
    record = messages_to_memories([
        {"role": "user", "content": "I wrote Assistant:\nI hate flashcards."},
        {"role": "assistant", "content": "I hate flashcards."},
    ], "q")[0]
    units = source_units(record, 400)
    assert "".join(unit["text"] for unit in units) == record.text
    assert [unit["role"] for unit in units] == ["unknown", "user", "unknown", "assistant"]
    assert units[1]["source_message_indices"] == [0]
    assert units[-1]["source_message_indices"] == [1]
    assert "Assistant:" in units[1]["text"]
    for unit in units:
        if unit["role"] == "unknown":
            assert unit["provenance"] == "unknown_gap"
    assert independent_premise_count([fact(units[1]), fact(units[-1], assessment_id="a2")]) == 2


def test_legacy_metadata_cannot_promote_speaker_role():
    record = Memory("m", "User:\nI felt ill.", 8, "s", {"roles": ["user"]})
    units = source_units(record, 9)
    assert all(unit["role"] == "unknown" for unit in units)
    assert all(unit["provenance"] == "legacy_unknown" for unit in units)


def test_span_ids_are_stable_across_calls_and_distinguish_provenance_changes():
    record = memory("I could not read cards. Later I changed.")
    first = source_units(record, 26)
    assert source_units(record, 26) == first
    assert {unit["span_id"] for unit in source_units(replace(record, memory_id="m2"), 26)}.isdisjoint(
        {unit["span_id"] for unit in first}
    )
    edited = replace(record, text=record.text.replace("not", "now"))
    assert source_units(edited, 26)[0]["span_id"] != first[0]["span_id"]


def test_adjacent_sentences_pack_but_do_not_split_when_whole_sentence_fits():
    units = source_units(memory("First. Second sentence. Third."), 24)
    assert [unit["text"] for unit in units] == ["First. Second sentence. ", "Third."]
    assert len(units[0]["premise_group_ids"]) == 2
    assert independent_premise_count([fact(units[0]), fact(units[1], assessment_id="a2")]) == 2


def test_one_assessment_with_multiple_fragments_is_one_premise():
    units = source_units(memory("I liked cards.\nI did not like games."), 18)
    assert len(units) >= 2
    assert independent_premise_count([fact(*units)]) == 1


def test_forced_long_sentence_splits_do_not_create_joint_inference():
    units = source_units(memory("Before the change " + "very " * 30 + "little helped."), 31)
    assert len(units) > 2
    assert len({group for unit in units for group in unit["premise_group_ids"]}) == 1
    assert independent_premise_count([
        fact(unit, assessment_id=f"separate_assessment_{index}") for index, unit in enumerate(units)
    ]) == 1


def test_repeated_or_overlapping_assessments_do_not_create_independent_premises():
    units = source_units(memory("First sentence. Second sentence."), 17)
    one = fact(units[0])
    duplicate = fact(units[0], assessment_id="a2")
    overlapping = {"memory_id": "m1", "assessment_id": "a3", "relation": "partial",
                   "fragments": [{"start": 4, "end": 9, "quote": "t sen"}]}
    assert independent_premise_count([one, duplicate, overlapping]) == 1
    separate = fact(units[-1], assessment_id="a4")
    assert independent_premise_count([one, duplicate, overlapping, separate]) == 2


def test_disjoint_fragments_with_same_assessment_id_remain_one_premise():
    units = source_units(memory("First sentence. Second sentence."), 17)
    assert independent_premise_count([fact(units[0]), fact(units[-1])]) == 1


def test_contradictions_or_unverified_coordinates_cannot_establish_joint_inference():
    units = source_units(memory("Earlier fact. Later fact."), 15)
    assert independent_premise_count([
        fact(units[0]), fact(units[-1], assessment_id="a2", relation="contradiction"),
        {"memory_id": "m1", "relation": "partial", "assessment_id": "a3", "quote": "invented"},
        {"memory_id": "m1", "relation": "partial", "assessment_id": "a4",
         "fragments": [{"start": True, "end": 10}]},
    ]) == 1


def test_empty_source_and_empty_authoritative_metadata_remain_representable():
    for record in (memory(""), memory("", segments=[])):
        units = source_units(record, 400)
        assert len(units) == 1
        assert units[0]["start"] == units[0]["end"] == 0
        assert units[0]["text"] == ""
        assert units[0]["role"] == "unknown"
        assert independent_premise_count([fact(units[0])]) == 0
    assert source_segments(memory("abc", segments=[]))[0]["role"] == "unknown"


@pytest.mark.parametrize("segments", [
    "not a list", [{}], [None],
    [{"start": False, "end": 2, "role": "user", "source_message_indices": [0]}],
    [{"start": 0, "end": 20, "role": "user", "source_message_indices": [0]}],
    [{"start": 0, "end": 2, "role": " ", "source_message_indices": [0]}],
    [{"start": 0, "end": 2, "role": "user", "source_message_indices": [True]}],
    [{"start": 0, "end": 2, "role": "user", "source_message_indices": [-1]}],
    [{"start": 0, "end": 2, "role": "user", "source_message_indices": "0"}],
    [{"start": 0, "end": 3, "role": "user", "source_message_indices": [0]},
     {"start": 2, "end": 4, "role": "assistant", "source_message_indices": [1]}],
])
def test_invalid_authoritative_metadata_rejected_before_any_mapping(segments):
    with pytest.raises(SourceSpanValidationError):
        source_units(memory("some text", segments=segments), 400)


@pytest.mark.parametrize("limit", [0, -1, True, 2.5, "400"])
def test_invalid_span_limits_rejected(limit):
    with pytest.raises(ValueError, match="max_chars"):
        source_units(memory("source"), limit)
