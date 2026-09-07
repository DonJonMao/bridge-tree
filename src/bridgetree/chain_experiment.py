"""Fixed full-run planning and denominator-safe outcome bookkeeping."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_CHAIN_METHODS = (
    "dense", "dense_rerank", "rfmem", "semantic_s2", "chain_h1_no_closure",
    "chain_h2_no_closure", "chain_full", "chain_no_join", "chain_dense_pool",
)


@dataclass(frozen=True)
class ChainTask:
    dataset_revision: str
    split: str
    persona_id: str
    question_id: str
    method_id: str
    config_hash: str

    @property
    def key(self) -> tuple[str, ...]:
        return (self.dataset_revision, self.split, self.persona_id,
                self.question_id, self.method_id, self.config_hash)


@dataclass(frozen=True)
class Outcome:
    task: ChainTask
    status: str
    correct: bool | None = None
    prediction: str | None = None
    error: str | None = None


def build_full_plan(queries: Iterable[Mapping[str, object]], *, dataset_revision: str,
                    config_hash: str, methods: Sequence[str] = DEFAULT_CHAIN_METHODS) -> list[ChainTask]:
    """Freeze all task keys before execution, preserving input split/persona order."""
    result: list[ChainTask] = []
    for query in queries:
        split = str(query.get("split", "confirmation"))
        persona = str(query["persona_id"])
        question = str(query["question_id"])
        result.extend(ChainTask(dataset_revision, split, persona, question, method, config_hash)
                      for method in methods)
    return result


def write_plan(path: str | Path, tasks: Sequence[ChainTask]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(asdict(task), ensure_ascii=False, sort_keys=True) + "\n")


def summarize_outcomes(tasks: Sequence[ChainTask], outcomes: Sequence[Outcome]) -> dict[str, object]:
    expected = len(tasks)
    by_key = {outcome.task.key: outcome for outcome in outcomes}
    completed = [item for item in by_key.values() if item.status in {"success", "error"}]
    correct = sum(1 for item in completed if item.correct is True)
    failed = sum(1 for item in completed if item.status == "error")
    return {
        "expected_tasks": expected,
        "completed_tasks": len(completed),
        "pending_tasks": max(0, expected - len(completed)),
        "correct": correct,
        "failed": failed,
        "coverage": len(completed) / expected if expected else 1.0,
        "completed_accuracy": correct / len(completed) if completed else None,
        "final_accuracy": correct / expected if expected and len(completed) == expected else None,
    }


def write_metrics(path: str | Path, rows: Sequence[Mapping[str, object]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
