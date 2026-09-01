from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np

from .clustering import spherical_kmeans
from .index import ExactInnerProductIndex
from .math_utils import normalize, normalize_rows


@dataclass(frozen=True)
class BaselineResult:
    selected_ids: List[str]
    ann_calls: int
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def dense_retrieval(ids: Sequence[str], vectors: np.ndarray, query_vector: np.ndarray, top_k: int) -> BaselineResult:
    index = ExactInnerProductIndex(ids, vectors)
    hits = index.search(query_vector, top_k)
    return BaselineResult([memory_id for memory_id, _ in hits], ann_calls=1)


def _rf_entropy(scores: np.ndarray) -> float:
    scaled = 20.0 * scores
    probabilities = np.exp(scaled - scaled.max())
    probabilities /= probabilities.sum() + 1e-12
    # This intentionally matches the official RF-Mem implementation.
    return float(-(probabilities * np.log(probabilities + 1e-12)).mean())


def rfmem_route(scores: Sequence[float], entropy_threshold: float = 0.2) -> Tuple[str, Dict[str, Any]]:
    values = np.asarray(scores, dtype=np.float64)
    if len(values) == 0:
        return "slow", {"entropy": 0.0, "mean_score": 0.0, "rule": "no_hits"}
    mean_score = float(values.mean())
    entropy = _rf_entropy(np.sort(values)[::-1])
    if mean_score >= 0.60:
        mode, rule = "fast", "mean_high"
    elif mean_score <= 0.30:
        mode, rule = "slow", "mean_low"
    elif entropy < entropy_threshold:
        mode, rule = "fast", "low_entropy"
    else:
        mode, rule = "slow", "high_entropy"
    return mode, {"entropy": entropy, "mean_score": mean_score, "rule": rule}


@dataclass
class _RFBranch:
    query: np.ndarray
    score_sum: float
    hits: List[Tuple[str, float]]


def rfmem_recollection(
    ids: Sequence[str],
    vectors: np.ndarray,
    query_vector: np.ndarray,
    top_k: int,
    depth: int | None = None,
    beam_width: int = 4,
    fanout: int = 3,
    alpha: float = 0.8,
    threshold: float = 0.3,
    mmr_lambda: float = 0.95,
) -> BaselineResult:
    vectors = normalize_rows(vectors)
    index = ExactInnerProductIndex(ids, vectors)
    q0 = normalize(query_vector)
    beam = [_RFBranch(q0, 0.0, [])]
    seen: Set[str] = set()
    results: List[str] = []
    ann_calls = 0
    for level in range(depth or top_k):
        next_branches: List[_RFBranch] = []
        for branch in beam:
            ann_calls += 1
            raw = index.search(branch.query, min(len(ids), (beam_width + level) * fanout), exclude=seen)
            candidates = [(memory_id, score) for memory_id, score in raw if score >= threshold]
            if not candidates:
                continue
            candidate_vectors = np.vstack([index.vector(memory_id) for memory_id, _ in candidates])
            selected: List[Tuple[str, float]] = []
            for position, (memory_id, score) in enumerate(candidates):
                similarities = np.dot(candidate_vectors, candidate_vectors[position])
                max_similarity = max(
                    (float(value) for other, value in enumerate(similarities) if other != position), default=0.0
                )
                selected.append((memory_id, mmr_lambda * score - (1.0 - mmr_lambda) * max_similarity))
            count = min(beam_width, len(selected))
            labels = spherical_kmeans(candidate_vectors, count)
            for cluster_index in range(count):
                positions = np.flatnonzero(labels == cluster_index)
                group = [selected[int(position)] for position in positions]
                centroid = normalize(candidate_vectors[positions].mean(axis=0))
                next_query = normalize(alpha * branch.query + (1.0 - alpha) * centroid + q0)
                next_branches.append(_RFBranch(next_query, branch.score_sum + sum(score for _, score in group), group))
        if not next_branches:
            continue
        beam = sorted(
            next_branches,
            key=lambda branch: (-branch.score_sum, tuple(item[0] for item in branch.hits)),
        )[:beam_width]
        for branch in beam:
            for memory_id, _score in branch.hits:
                if memory_id not in seen:
                    seen.add(memory_id)
                    results.append(memory_id)
        if len(results) >= top_k:
            break
    return BaselineResult(results[:top_k], ann_calls=ann_calls)


def rfmem(
    ids: Sequence[str], vectors: np.ndarray, query_vector: np.ndarray, top_k: int, entropy_threshold: float = 0.2
) -> BaselineResult:
    index = ExactInnerProductIndex(ids, vectors)
    probe = index.search(query_vector, min(10, len(ids)))
    mode, diagnostics = rfmem_route([score for _, score in probe], entropy_threshold)
    if mode == "fast":
        hits = [(memory_id, score) for memory_id, score in index.search(query_vector, top_k) if score >= 0.3]
        return BaselineResult([memory_id for memory_id, _ in hits], 2, {**diagnostics, "route": mode})
    result = rfmem_recollection(ids, vectors, query_vector, top_k)
    return BaselineResult(result.selected_ids, result.ann_calls + 1, {**diagnostics, "route": mode})


def cluster_prf(
    ids: Sequence[str], vectors: np.ndarray, query_vector: np.ndarray, top_k: int, first_width: int = 12
) -> BaselineResult:
    """Cluster-based pseudo-relevance feedback without path semantics."""
    vectors = normalize_rows(vectors)
    index = ExactInnerProductIndex(ids, vectors)
    initial = index.search(query_vector, min(first_width, len(ids)))
    initial_ids = [memory_id for memory_id, _ in initial]
    initial_vectors = np.vstack([index.vector(memory_id) for memory_id in initial_ids])
    count = min(len(initial_ids), max(1, int(np.ceil(np.sqrt(len(initial_ids))))))
    labels = spherical_kmeans(initial_vectors, count)
    scores: Dict[str, float] = {memory_id: score for memory_id, score in initial}
    ann_calls = 1
    for cluster_index in range(count):
        positions = np.flatnonzero(labels == cluster_index)
        probe = normalize(initial_vectors[positions].mean(axis=0))
        ann_calls += 1
        for memory_id, score in index.search(probe, top_k, exclude=()):
            scores[memory_id] = max(scores.get(memory_id, -1.0), score)
    selected = sorted(scores, key=lambda memory_id: (-scores[memory_id], memory_id))[:top_k]
    return BaselineResult(selected, ann_calls)
