import csv
import json

import pytest

from bridgetree.personamem import iter_examples, messages_to_memories, prepare_split


def test_message_segmentation_preserves_source_indices_and_system_persona():
    messages = [
        {"role": "system", "content": "persona"},
        {"role": "user", "content": "I like tea"},
        {"role": "assistant", "content": "noted"},
        {"role": "user", "content": "I now prefer coffee"},
    ]
    memories = messages_to_memories(messages, "q1", include_system_persona=True)
    assert len(memories) == 3
    assert memories[0].metadata["roles"] == ["system"]
    assert memories[1].metadata["roles"] == ["user", "assistant"]
    assert memories[1].metadata["source_message_indices"] == [1, 2]
    assert memories[2].timestamp > memories[1].timestamp
    user_only = messages_to_memories(
        messages,
        "q1",
        include_system_persona=False,
        memory_granularity="user_only",
    )
    assert [memory.metadata["roles"] for memory in user_only] == [["user"], ["user"]]


def test_prepare_and_iter_respect_end_index(tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir()
    context_id = "ctx"
    messages = [
        {"role": "user", "content": "past"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "future leakage"},
    ]
    with (raw / "shared_contexts_32k.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({context_id: messages}) + "\n")
    fields = [
        "persona_id",
        "question_id",
        "question_type",
        "topic",
        "context_length_in_tokens",
        "context_length_in_letters",
        "distance_to_ref_in_blocks",
        "distance_to_ref_in_tokens",
        "num_irrelevant_tokens",
        "distance_to_ref_proportion_in_context",
        "user_question_or_message",
        "correct_answer",
        "all_options",
        "shared_context_id",
        "end_index_in_shared_context",
    ]
    row = {field: "0" for field in fields}
    row.update(
        {
            "question_id": "q",
            "question_type": "recall",
            "topic": "x",
            "user_question_or_message": "question",
            "correct_answer": "(a)",
            "all_options": "['(a) yes']",
            "shared_context_id": context_id,
            "end_index_in_shared_context": "2",
        }
    )
    with (raw / "questions_32k.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    manifest = prepare_split(raw, processed, "32k")
    example = next(iter_examples(raw / "questions_32k.csv", raw / "shared_contexts_32k.jsonl"))
    assert manifest["questions"] == 1
    assert len(example.messages) == 2
    assert all("future" not in message["content"] for message in example.messages)

    with pytest.raises(ValueError, match="source checksum mismatch"):
        prepare_split(raw, processed, "32k", verify_pinned_source=True)
