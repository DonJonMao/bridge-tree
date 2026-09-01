from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import List, Sequence

import numpy as np

from .math_utils import effective_rank, normalize


@dataclass(frozen=True)
class ClusterResult:
    member_positions: tuple[int, ...]
    probe: np.ndarray
    radius_radians: float


def _initial_centers(vectors: np.ndarray, count: int) -> np.ndarray:
    chosen = [0]
    while len(chosen) < count:
        similarity = np.dot(vectors, vectors[chosen].T)
        nearest_distance = 1.0 - np.max(similarity, axis=1)
        nearest_distance[chosen] = -1.0
        chosen.append(int(np.argmax(nearest_distance)))
    return vectors[chosen].copy()


def spherical_kmeans(vectors: np.ndarray, count: int, max_iterations: int = 100) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float64)
    if count < 1 or count > len(vectors):
        raise ValueError("cluster count must be in [1, number of vectors]")
    if count == 1:
        return np.zeros(len(vectors), dtype=np.int64)
    centers = _initial_centers(vectors, count)
    labels = np.full(len(vectors), -1, dtype=np.int64)
    for _ in range(max_iterations):
        new_labels = np.argmax(np.dot(vectors, centers.T), axis=1).astype(np.int64)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for cluster_index in range(count):
            positions = np.flatnonzero(labels == cluster_index)
            if len(positions) == 0:
                similarity = np.dot(vectors, centers.T)
                nearest_distance = 1.0 - np.max(similarity, axis=1)
                replacement = int(np.argmax(nearest_distance))
                labels[replacement] = cluster_index
                positions = np.asarray([replacement])
            summed = vectors[positions].sum(axis=0)
            if np.linalg.norm(summed) <= 1e-12:
                centers[cluster_index] = vectors[int(positions[0])]
            else:
                centers[cluster_index] = normalize(summed)
    return labels


def cluster_siblings(
    vectors: np.ndarray,
    reachabilities: Sequence[float],
    disable_compression: bool = False,
) -> List[ClusterResult]:
    vectors = np.asarray(vectors, dtype=np.float64)
    if len(vectors) == 0:
        return []
    count = len(vectors) if disable_compression else min(len(vectors), max(1, int(ceil(effective_rank(vectors)))))
    labels = spherical_kmeans(vectors, count)
    results: List[ClusterResult] = []
    weights = np.asarray(reachabilities, dtype=np.float64)
    for cluster_index in range(count):
        positions = np.flatnonzero(labels == cluster_index)
        cluster_vectors = vectors[positions]
        weighted_sum = (weights[positions, None] * cluster_vectors).sum(axis=0)
        if np.linalg.norm(weighted_sum) <= 1e-12:
            gram = np.dot(cluster_vectors, cluster_vectors.T)
            medoid_local = int(np.argmax(gram.sum(axis=1)))
            probe = cluster_vectors[medoid_local].copy()
        else:
            probe = normalize(weighted_sum)
        angles = np.arccos(np.clip(np.dot(cluster_vectors, probe), -1.0, 1.0))
        results.append(
            ClusterResult(
                member_positions=tuple(int(position) for position in positions),
                probe=probe,
                radius_radians=float(np.max(angles)),
            )
        )
    return results
