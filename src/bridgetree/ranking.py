from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Iterable, List, Sequence

from .clients import RerankerClient, RerankItem
from .personamem import PersonaMemExample, parse_options
from .types import Memory

DEFAULT_FINAL_RERANK_INSTRUCTION = (
    "Rank past user interactions by how useful they are for selecting the best personalized answer. "
    "Prioritize explicit user preferences, constraints, experiences, and the latest state when preferences evolve. "
    "A passage that is merely topically related but cannot distinguish the answer choices should rank low."
)
DEFAULT_PATH_FILTER_INSTRUCTION = (
    "Rank candidate interactions by whether they add distinct, independently usable personal evidence beyond "
    "the anchor for answering the current request. Avoid anchor paraphrases and merely topical passages."
)


def _option_text(value: str) -> str:
    return re.sub(r"^\s*[\(\[]?[A-Za-z][\)\]\.:-]\s*", "", value).strip()


def _formatted_options(example: PersonaMemExample) -> str:
    options = parse_options(example.all_options)
    return "\n".join(
        f"{chr(ord('A') + index)}. {_option_text(option)}" if index < 26 else f"{index + 1}. {_option_text(option)}"
        for index, option in enumerate(options)
    )


def build_personamem_rank_query(
    example: PersonaMemExample,
    *,
    instruction: str = DEFAULT_FINAL_RERANK_INSTRUCTION,
    use_answer_options: bool = True,
) -> str:
    """Build the shared task query without ever exposing the gold answer field."""
    sections = [instruction.strip(), f"Current request:\n{example.query}"]
    if use_answer_options:
        sections.append(f"Candidate answers:\n{_formatted_options(example)}")
    return "\n\n".join(sections)


def format_memory_document(
    memory: Memory,
    max_timestamp: float,
    *,
    include_time_metadata: bool = True,
) -> str:
    if not include_time_metadata:
        return memory.text
    roles = memory.metadata.get("roles", ())
    role_text = ", ".join(str(role) for role in roles) if roles else "unknown"
    current = int(memory.timestamp) if float(memory.timestamp).is_integer() else memory.timestamp
    maximum = int(max_timestamp) if float(max_timestamp).is_integer() else max_timestamp
    return (
        f"[Interaction index: {current} / {maximum}]\n"
        f"[Roles: {role_text}]\n"
        f"{memory.text}"
    )


def build_bridge_embedding_text(query: str, anchor: Memory) -> str:
    return (
        f"Current request:\n{query}\n\n"
        f"Already retrieved anchor interaction:\n{anchor.text}\n\n"
        "Retrieve another past interaction that supplies distinct, complementary personal evidence for the request. "
        "Avoid paraphrases of the anchor and passages that are only topically related."
    )


def build_path_filter_query(
    example: PersonaMemExample,
    *,
    instruction: str = DEFAULT_PATH_FILTER_INSTRUCTION,
    use_answer_options: bool = True,
) -> str:
    sections = [instruction.strip(), f"Current request:\n{example.query}"]
    if use_answer_options:
        sections.append(f"Candidate answers:\n{_formatted_options(example)}")
    return "\n\n".join(sections)


def format_path_document(
    anchor: Memory,
    candidate: Memory,
    max_timestamp: float,
    *,
    include_time_metadata: bool = True,
) -> str:
    return (
        "Anchor interaction:\n"
        f"{format_memory_document(anchor, max_timestamp, include_time_metadata=include_time_metadata)}\n\n"
        "Candidate interaction:\n"
        f"{format_memory_document(candidate, max_timestamp, include_time_metadata=include_time_metadata)}"
    )


def stable_union(*groups: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value not in seen:
                seen.add(value)
                result.append(value)
    return result


class RerankCache:
    """Content-addressed, order-sensitive cache of complete reranker rankings."""

    def __init__(self, root: str | Path, *, endpoint: str, model: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.endpoint = endpoint
        self.model = model

    def key_for(self, query: str, documents: Sequence[str]) -> str:
        payload = json.dumps(
            {
                "schema": 1,
                "endpoint": self.endpoint,
                "model": self.model,
                "query": query,
                "documents": list(documents),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path(self, query: str, documents: Sequence[str]) -> Path:
        return self.root / f"{self.key_for(query, documents)}.json"

    def get(self, query: str, documents: Sequence[str]) -> List[RerankItem] | None:
        path = self._path(query, documents)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = [RerankItem(index=int(item["index"]), score=float(item["score"])) for item in raw["items"]]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        expected = set(range(len(documents)))
        if len(items) != len(documents) or {item.index for item in items} != expected:
            return None
        return sorted(items, key=lambda item: (-item.score, item.index))

    def put(self, query: str, documents: Sequence[str], items: Sequence[RerankItem]) -> None:
        expected = set(range(len(documents)))
        if len(items) != len(documents) or {item.index for item in items} != expected:
            raise ValueError("rerank cache requires one result for every document")
        path = self._path(query, documents)
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        payload = {
            "items": [
                {"index": item.index, "score": item.score}
                for item in sorted(items, key=lambda item: (-item.score, item.index))
            ]
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    def rerank_all(
        self,
        client: RerankerClient,
        query: str,
        documents: Sequence[str],
    ) -> tuple[List[RerankItem], bool, float]:
        if not documents:
            return [], True, 0.0
        cached = self.get(query, documents)
        if cached is not None:
            return cached, True, 0.0
        started = time.perf_counter()
        method = getattr(client, "rerank_all", None)
        items = method(query, documents) if callable(method) else client.rerank(query, documents, len(documents))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        ranked = sorted(items, key=lambda item: (-item.score, item.index))
        self.put(query, documents, ranked)
        return ranked, False, elapsed_ms
