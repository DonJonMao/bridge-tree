from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np

from .math_utils import normalize, normalize_rows


class ExactInnerProductIndex:
    """Deterministic exact unit-vector index used by the proof-aligned path."""

    def __init__(self, ids: Sequence[str], vectors: np.ndarray):
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must have equal length")
        if len(set(ids)) != len(ids):
            raise ValueError("memory ids must be unique")
        self.ids = list(ids)
        self.vectors = normalize_rows(np.asarray(vectors, dtype=np.float64))
        self.position = {memory_id: index for index, memory_id in enumerate(self.ids)}

    def vector(self, memory_id: str) -> np.ndarray:
        return self.vectors[self.position[memory_id]]

    def search(
        self,
        query: np.ndarray,
        top_k: int,
        exclude: Iterable[str] = (),
    ) -> List[Tuple[str, float]]:
        if top_k <= 0:
            return []
        query_vector = normalize(query)
        excluded = set(exclude)
        scores = np.dot(self.vectors, query_vector)
        ranked = sorted(
            ((self.ids[index], float(score)) for index, score in enumerate(scores) if self.ids[index] not in excluded),
            key=lambda item: (-item[1], item[0]),
        )
        return ranked[:top_k]


class FaissInnerProductIndex(ExactInnerProductIndex):
    """FAISS-backed index with deterministic exact fallback for exclusions.

    IndexFlatIP is mathematically exact. For a large exclusion set the method
    asks FAISS for progressively more hits; ties are finally normalized by id.
    """

    def __init__(self, ids: Sequence[str], vectors: np.ndarray):
        super().__init__(ids, vectors)
        try:
            import faiss  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("faiss backend requested but faiss is not installed") from exc
        self._faiss = faiss.IndexFlatIP(self.vectors.shape[1])
        self._faiss.add(self.vectors.astype(np.float32))

    def search(self, query: np.ndarray, top_k: int, exclude: Iterable[str] = ()) -> List[Tuple[str, float]]:
        if top_k <= 0:
            return []
        excluded = set(exclude)
        # Retrieve the whole exact FlatIP ordering so an exclusion or a tie at
        # the requested cutoff cannot make the stable id tie-break incomplete.
        query_vector = normalize(query)
        scores, positions = self._faiss.search(query_vector.astype(np.float32)[None, :], len(self.ids))
        results = []
        for position, _score in zip(positions[0], scores[0]):
            if position < 0:
                continue
            memory_id = self.ids[int(position)]
            if memory_id not in excluded:
                # Recompute in float64 so exact and FAISS paths share scores.
                results.append((memory_id, float(np.dot(self.vectors[int(position)], query_vector))))
        return sorted(results, key=lambda item: (-item[1], item[0]))[:top_k]


def build_index(backend: str, ids: Sequence[str], vectors: np.ndarray) -> ExactInnerProductIndex:
    if backend == "exact":
        return ExactInnerProductIndex(ids, vectors)
    if backend == "faiss":
        return FaissInnerProductIndex(ids, vectors)
    raise ValueError(f"unknown index backend: {backend}")
