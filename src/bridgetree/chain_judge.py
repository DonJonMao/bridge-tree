"""Contracts for the train-free BridgeTree-Chain semantic judge.

The module is deliberately backend agnostic.  A backend must return the two
labels from one prompt and one output position; callers cannot silently turn a
missing label into a probability.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class PublicQuery:
    dataset_revision: str
    persona_id: str
    question_id: str
    query: str
    public_options: str = ""
    shared_context_id: str = ""
    end_index: int | None = None
    visible_memories: tuple[str, ...] = ()
    time_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.query:
            raise ValueError("PublicQuery.query cannot be empty")
        object.__setattr__(self, "visible_memories", tuple(str(x) for x in self.visible_memories))
        object.__setattr__(self, "time_metadata", tuple((str(k), str(v)) for k, v in self.time_metadata))

    def identity(self) -> str:
        payload = {"dataset_revision": self.dataset_revision, "persona_id": self.persona_id,
                   "question_id": self.question_id, "query": self.query,
                   "public_options": self.public_options, "shared_context_id": self.shared_context_id,
                   "end_index": self.end_index, "visible_memories": list(self.visible_memories),
                   "time_metadata": list(self.time_metadata)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class JointScore:
    raw_difference: float
    log_u: float
    u: float
    input_hash: str
    sufficient_label: str = "A"
    insufficient_label: str = "B"

    @classmethod
    def from_logits(cls, sufficient: float, insufficient: float, *, input_hash: str,
                    sufficient_label: str = "A", insufficient_label: str = "B") -> "JointScore":
        if not math.isfinite(sufficient) or not math.isfinite(insufficient):
            raise ValueError("joint logits must be finite")
        d = float(sufficient) - float(insufficient)
        log_u = -math.log1p(math.exp(-d)) if d >= 0 else d - math.log1p(math.exp(d))
        return cls(d, log_u, math.exp(log_u), str(input_hash), sufficient_label, insufficient_label)


@dataclass(frozen=True)
class Claim:
    text: str
    source_ids: tuple[str, ...]
    input_hash: str


@dataclass(frozen=True)
class Verification:
    supported: bool
    reason: str = ""
    input_hash: str = ""


class JointJudge(Protocol):
    def score(self, query: PublicQuery, raw_ids: tuple[str, ...]) -> JointScore: ...
    def claim(self, query: PublicQuery, raw_ids: tuple[str, ...]) -> Claim: ...
    def verify(self, query: PublicQuery, fixed_claim: Claim, raw_ids: tuple[str, ...]) -> Verification: ...


def require_label_pair(response: Mapping[str, Any], *, sufficient_label: str = "A",
                       insufficient_label: str = "B") -> tuple[float, float]:
    """Extract two same-position label scores and fail closed if either is absent."""
    scores = response.get("logprobs", response.get("label_logprobs"))
    if not isinstance(scores, Mapping):
        raise ValueError("joint judge response must contain label logprobs")
    if sufficient_label not in scores or insufficient_label not in scores:
        raise ValueError("joint judge response must contain both configured labels")
    try:
        first, second = float(scores[sufficient_label]), float(scores[insufficient_label])
    except (TypeError, ValueError) as exc:
        raise ValueError("joint label logprobs must be numeric") from exc
    if not math.isfinite(first) or not math.isfinite(second):
        raise ValueError("joint label logprobs must be finite")
    return first, second


def judge_input_hash(query: PublicQuery, raw_ids: Sequence[str], records: Mapping[str, Any]) -> str:
    payload = {"query": query.identity(), "raw_ids": list(raw_ids),
               "records": [records.get(identifier) for identifier in raw_ids]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


JOINT_PROMPT = """Read the recorded evidence jointly to assess the ORIGINAL question.
A premise may make another record useful; evaluate that relation explicitly.
Respect speaker roles, entity identity, negation, and the time requested.
Do not invent personal facts. Same-topic text alone is not sufficient.
General reasoning may connect explicitly supported personal constraints.
Decide whether these records support a specific question-appropriate answer.
Output only A (sufficient) or B (insufficient)."""
