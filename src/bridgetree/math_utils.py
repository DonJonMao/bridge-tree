from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def normalize(vector: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(value))
    if norm <= eps:
        raise ValueError("cannot normalize a zero vector")
    return value / norm


def normalize_rows(matrix: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    value = np.asarray(matrix, dtype=np.float64)
    if value.ndim != 2:
        raise ValueError("expected a two-dimensional matrix")
    norms = np.linalg.norm(value, axis=1, keepdims=True)
    if np.any(norms <= eps):
        raise ValueError("embedding matrix contains a zero vector")
    return value / norms


def nonnegative_cosine(left: np.ndarray, right: np.ndarray) -> float:
    return max(0.0, float(np.clip(np.dot(left, right), -1.0, 1.0)))


def effective_rank(vectors: np.ndarray, eps: float = 1e-12) -> float:
    """Participation-ratio effective rank of the sibling Gram matrix."""
    if len(vectors) == 0:
        return 0.0
    value = np.asarray(vectors, dtype=np.float64)
    gram = np.dot(value, value.T)
    eigenvalues = np.maximum(np.linalg.eigvalsh(gram), 0.0)
    denominator = float(np.dot(eigenvalues, eigenvalues))
    if denominator <= eps:
        return 1.0
    return float(eigenvalues.sum() ** 2 / denominator)


def path_conditioned_innovation(
    vector: np.ndarray,
    reachability: float,
    ancestor_weighted_vectors: Sequence[np.ndarray],
) -> np.ndarray:
    """Compute (I + B_A B_A^T)^(-1/2) (rho * z) by a thin SVD.

    The implementation is Eq. (58) of the design and never forms a d-by-d
    inverse square root.
    """
    weighted = float(reachability) * np.asarray(vector, dtype=np.float64)
    if not ancestor_weighted_vectors:
        return weighted.copy()
    columns = np.column_stack([np.asarray(item, dtype=np.float64) for item in ancestor_weighted_vectors])
    u, singular, _ = np.linalg.svd(columns, full_matrices=False)
    projection = np.dot(u.T, weighted)
    factor = 1.0 / np.sqrt(1.0 + singular**2) - 1.0
    return weighted + np.dot(u, factor * projection)


def logdet_value(features: Iterable[np.ndarray]) -> float:
    rows = [np.asarray(feature, dtype=np.float64) for feature in features]
    if not rows:
        return 0.0
    phi = np.vstack(rows)
    sign, value = np.linalg.slogdet(np.eye(len(phi), dtype=np.float64) + np.dot(phi, phi.T))
    if sign <= 0:
        raise FloatingPointError("I + Phi Phi^T must be positive definite")
    return float(value)


def logdet_marginal(candidate: np.ndarray, selected_features: Sequence[np.ndarray]) -> float:
    """Exact Eq. (41), evaluated in k-space with the Woodbury identity."""
    phi = np.asarray(candidate, dtype=np.float64)
    norm_sq = float(np.dot(phi, phi))
    if not selected_features:
        return float(np.log1p(max(0.0, norm_sq)))
    selected = np.vstack([np.asarray(feature, dtype=np.float64) for feature in selected_features])
    cross = np.dot(selected, phi)
    small = np.eye(len(selected), dtype=np.float64) + np.dot(selected, selected.T)
    conditional_sq = norm_sq - float(np.dot(cross, np.linalg.solve(small, cross)))
    return float(np.log1p(max(0.0, conditional_sq)))


def posterior_error(epsilons: Sequence[float]) -> float:
    k = len(epsilons)
    if k == 0:
        return 0.0
    return float(sum(((1.0 - 1.0 / k) ** (k - j)) * eps for j, eps in enumerate(epsilons, start=1)))
