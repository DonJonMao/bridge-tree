from __future__ import annotations

import ast
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Sequence

from .types import Memory

PERSONAMEM_REPO = "bowen-upenn/PersonaMem-v1"
PERSONAMEM_REVISION = "fd7c30f071d5c2ee2a211506783be222d7b6002e"


@dataclass(frozen=True)
class PersonaMemExample:
    persona_id: str
    question_id: str
    question_type: str
    topic: str
    query: str
    correct_answer: str
    all_options: str
    shared_context_id: str
    end_index: int
    messages: List[Dict[str, str]]


def load_shared_contexts(path: str | Path) -> Dict[str, List[Dict[str, str]]]:
    contexts: Dict[str, List[Dict[str, str]]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"context line {line_number} is not an object")
            for context_id, messages in item.items():
                if context_id in contexts:
                    raise ValueError(f"duplicate shared_context_id: {context_id}")
                contexts[str(context_id)] = list(messages)
    return contexts


def iter_examples(question_path: str | Path, context_path: str | Path) -> Iterator[PersonaMemExample]:
    contexts = load_shared_contexts(context_path)
    with Path(question_path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            context_id = row["shared_context_id"]
            end_index = int(row["end_index_in_shared_context"])
            if context_id not in contexts:
                raise KeyError(f"missing shared context: {context_id}")
            messages = contexts[context_id][:end_index]
            yield PersonaMemExample(
                persona_id=row["persona_id"],
                question_id=row["question_id"],
                question_type=row["question_type"],
                topic=row["topic"],
                query=row["user_question_or_message"],
                correct_answer=row["correct_answer"],
                all_options=row["all_options"],
                shared_context_id=context_id,
                end_index=end_index,
                messages=messages,
            )


def messages_to_memories(
    messages: Sequence[Mapping[str, Any]],
    source_prefix: str,
    include_system_persona: bool = True,
) -> List[Memory]:
    """Convert PersonaMem messages into independent, traceable memory turns.

    Consecutive messages with the same role are merged; a user turn and its
    following assistant response form one memory, matching the official
    RF-Mem PersonaMem preprocessing while retaining source indices.
    """
    normalized: List[Dict[str, Any]] = []
    for index, message in enumerate(messages):
        role = str(message.get("role", "unknown")).strip().lower()
        content = str(message.get("content", "")).strip()
        if not content or (role == "system" and not include_system_persona):
            continue
        if normalized and normalized[-1]["role"] == role:
            normalized[-1]["content"] += "\n\n" + content
            normalized[-1]["indices"].append(index)
        else:
            normalized.append({"role": role, "content": content, "indices": [index]})

    memories: List[Memory] = []
    cursor = 0
    memory_index = 0
    while cursor < len(normalized):
        current = normalized[cursor]
        roles = [current["role"]]
        indices = list(current["indices"])
        parts = [f"{current['role'].capitalize()}:\n{current['content']}"]
        if current["role"] == "user" and cursor + 1 < len(normalized) and normalized[cursor + 1]["role"] == "assistant":
            following = normalized[cursor + 1]
            roles.append("assistant")
            indices.extend(following["indices"])
            parts.append(f"Assistant:\n{following['content']}")
            cursor += 2
        else:
            cursor += 1
        memory_id = f"{source_prefix}:m{memory_index:05d}"
        memories.append(
            Memory(
                memory_id=memory_id,
                text="\n\n".join(parts),
                timestamp=float(max(indices)),
                source_id=f"{source_prefix}:{min(indices)}-{max(indices)}",
                metadata={"roles": roles, "source_message_indices": indices},
            )
        )
        memory_index += 1
    return memories


def parse_options(raw: str) -> List[str]:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return [raw]
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_split(raw_dir: str | Path, processed_dir: str | Path, split: str) -> Dict[str, Any]:
    raw_root = Path(raw_dir)
    output_root = Path(processed_dir) / split
    output_root.mkdir(parents=True, exist_ok=True)
    questions = raw_root / f"questions_{split}.csv"
    contexts = raw_root / f"shared_contexts_{split}.jsonl"
    if not questions.exists() or not contexts.exists():
        raise FileNotFoundError(f"missing PersonaMem {split} files in {raw_root}")

    context_map = load_shared_contexts(contexts)
    context_output = output_root / "contexts.jsonl"
    with context_output.open("w", encoding="utf-8") as handle:
        for context_id in sorted(context_map):
            record = {"shared_context_id": context_id, "messages": context_map[context_id]}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    query_count = 0
    persona_ids = set()
    query_output = output_root / "queries.jsonl"
    with (
        questions.open("r", encoding="utf-8", newline="") as source,
        query_output.open("w", encoding="utf-8") as target,
    ):
        for row in csv.DictReader(source):
            record = dict(row)
            record["end_index_in_shared_context"] = int(record["end_index_in_shared_context"])
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
            query_count += 1
            persona_ids.add(row["persona_id"])

    manifest = {
        "dataset": PERSONAMEM_REPO,
        "revision": PERSONAMEM_REVISION,
        "split": split,
        "questions": query_count,
        "personas": len(persona_ids),
        "shared_contexts": len(context_map),
        "source_sha256": {questions.name: file_sha256(questions), contexts.name: file_sha256(contexts)},
        "outputs": {context_output.name: file_sha256(context_output), query_output.name: file_sha256(query_output)},
    }
    manifest_path = output_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest
