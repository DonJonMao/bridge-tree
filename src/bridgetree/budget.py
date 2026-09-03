from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable

import numpy as np

from .config import RetrievalConfig

STOP_REASONS = {
    "frontier_empty",
    "max_depth",
    "search_budget",
    "certificate",
    "insufficient_candidates",
}


@dataclass(frozen=True)
class SearchBudget:
    max_unique_nodes: int
    max_ann_calls: int | None = None
    max_candidate_exposure: int | None = None

    @classmethod
    def from_config(cls, config: RetrievalConfig) -> "SearchBudget":
        return cls(config.search_budget, config.max_ann_calls, config.max_candidate_exposure)

    def validate(self) -> None:
        if self.max_unique_nodes <= 0:
            raise ValueError("max_unique_nodes must be positive")
        if self.max_ann_calls is not None and self.max_ann_calls <= 0:
            raise ValueError("max_ann_calls must be positive when set")
        if self.max_candidate_exposure is not None and self.max_candidate_exposure <= 0:
            raise ValueError("max_candidate_exposure must be positive when set")


@dataclass(frozen=True)
class CostSnapshot:
    ann_calls_core: int = 0
    ann_calls_diagnostic: int = 0
    candidates_returned: int = 0
    candidates_returned_diagnostic: int = 0
    unique_visited_nodes: int = 0
    index_build_ms: float = 0.0
    retrieval_core_ms: float = 0.0
    diagnostic_ms: float = 0.0
    rerank_calls: int = 0
    rerank_documents: int = 0
    rerank_ms: float = 0.0
    bridge_embedding_calls: int = 0
    bridge_embedding_queries: int = 0
    bridge_embedding_ms: float = 0.0
    generation_ms: float = 0.0
    final_context_count: int = 0
    final_context_tokens: int = 0
    stop_reason: str = "insufficient_candidates"
    duplicate_proposals: int = 0
    proposal_count: int = 0
    new_unique_candidates_per_ann: float = 0.0
    new_unique_candidates_by_ann: tuple[int, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostTracker:
    budget: SearchBudget
    ann_calls_core: int = 0
    ann_calls_diagnostic: int = 0
    candidates_returned: int = 0
    candidates_returned_diagnostic: int = 0
    index_build_ms: float = 0.0
    retrieval_core_ms: float = 0.0
    diagnostic_ms: float = 0.0
    rerank_calls: int = 0
    rerank_documents: int = 0
    rerank_ms: float = 0.0
    bridge_embedding_calls: int = 0
    bridge_embedding_queries: int = 0
    bridge_embedding_ms: float = 0.0
    generation_ms: float = 0.0
    final_context_count: int = 0
    final_context_tokens: int = 0
    stop_reason: str = "insufficient_candidates"
    duplicate_proposals: int = 0
    proposal_count: int = 0
    _visited: set[str] = field(default_factory=set)
    _expansion_yields: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.budget.validate()

    @property
    def remaining_ann_calls(self) -> int | None:
        if self.budget.max_ann_calls is None:
            return None
        return max(0, self.budget.max_ann_calls - self.ann_calls_core)

    @property
    def remaining_unique_nodes(self) -> int:
        return max(0, self.budget.max_unique_nodes - len(self._visited))

    @property
    def remaining_candidate_exposure(self) -> int | None:
        if self.budget.max_candidate_exposure is None:
            return None
        return max(0, self.budget.max_candidate_exposure - self.candidates_returned)

    @property
    def cost_unique_count(self) -> int:
        return len(self._visited)

    def can_search_core(self) -> bool:
        return (
            self.remaining_unique_nodes > 0
            and (self.remaining_ann_calls is None or self.remaining_ann_calls > 0)
            and (self.remaining_candidate_exposure is None or self.remaining_candidate_exposure > 0)
        )

    def search_core(self, index, query: np.ndarray, top_k: int, exclude: Iterable[str] = ()):
        if not self.can_search_core() or top_k <= 0:
            return []
        top_k = min(top_k, self.remaining_unique_nodes)
        if self.remaining_candidate_exposure is not None:
            top_k = min(top_k, self.remaining_candidate_exposure)
        if top_k <= 0:
            return []
        started = time.perf_counter()
        hits = index.search(
            query,
            top_k,
            exclude=exclude,
            max_backend_calls=self.remaining_ann_calls,
        )
        self.retrieval_core_ms += (time.perf_counter() - started) * 1000.0
        backend_calls = len(index.last_search_stats.backend_request_sizes)
        self.ann_calls_core += backend_calls
        self.candidates_returned += len(hits)
        ids = [memory_id for memory_id, _score in hits]
        duplicate_count = sum(memory_id in self._visited for memory_id in ids)
        new_ids = set(ids) - self._visited
        self.duplicate_proposals += duplicate_count
        self.proposal_count += len(ids)
        self._visited.update(ids)
        if backend_calls:
            self._expansion_yields.extend([len(new_ids)] + [0] * (backend_calls - 1))
        return hits

    def search_diagnostic(self, index, query: np.ndarray, top_k: int, exclude: Iterable[str] = ()):
        if top_k <= 0:
            return []
        started = time.perf_counter()
        hits = index.search(query, top_k, exclude=exclude)
        self.diagnostic_ms += (time.perf_counter() - started) * 1000.0
        self.ann_calls_diagnostic += len(index.last_search_stats.backend_request_sizes)
        self.candidates_returned_diagnostic += len(hits)
        return hits

    def mark_visited(self, ids: Iterable[str]) -> None:
        self._visited.update(ids)

    def record_rerank(self, document_count: int, elapsed_ms: float) -> None:
        if document_count < 0 or elapsed_ms < 0.0:
            raise ValueError("rerank cost values cannot be negative")
        self.rerank_calls += 1
        self.rerank_documents += document_count
        self.rerank_ms += elapsed_ms

    def record_bridge_embedding(self, query_count: int, elapsed_ms: float) -> None:
        if query_count < 0 or elapsed_ms < 0.0:
            raise ValueError("bridge embedding cost values cannot be negative")
        self.bridge_embedding_calls += 1
        self.bridge_embedding_queries += query_count
        self.bridge_embedding_ms += elapsed_ms

    def set_stop_reason(self, reason: str) -> None:
        if reason not in STOP_REASONS:
            raise ValueError(f"unsupported stop reason: {reason}")
        self.stop_reason = reason

    def snapshot(self) -> CostSnapshot:
        mean_yield = sum(self._expansion_yields) / len(self._expansion_yields) if self._expansion_yields else 0.0
        return CostSnapshot(
            ann_calls_core=self.ann_calls_core,
            ann_calls_diagnostic=self.ann_calls_diagnostic,
            candidates_returned=self.candidates_returned,
            candidates_returned_diagnostic=self.candidates_returned_diagnostic,
            unique_visited_nodes=len(self._visited),
            index_build_ms=self.index_build_ms,
            retrieval_core_ms=self.retrieval_core_ms,
            diagnostic_ms=self.diagnostic_ms,
            rerank_calls=self.rerank_calls,
            rerank_documents=self.rerank_documents,
            rerank_ms=self.rerank_ms,
            bridge_embedding_calls=self.bridge_embedding_calls,
            bridge_embedding_queries=self.bridge_embedding_queries,
            bridge_embedding_ms=self.bridge_embedding_ms,
            generation_ms=self.generation_ms,
            final_context_count=self.final_context_count,
            final_context_tokens=self.final_context_tokens,
            stop_reason=self.stop_reason,
            duplicate_proposals=self.duplicate_proposals,
            proposal_count=self.proposal_count,
            new_unique_candidates_per_ann=mean_yield,
            new_unique_candidates_by_ann=tuple(self._expansion_yields),
        )
