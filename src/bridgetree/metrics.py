from __future__ import annotations

import re
from itertools import combinations
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .index import ExactInnerProductIndex
from .math_utils import logdet_marginal, logdet_value
from .types import Branch, RetrievalResult, TreeNode

_OPTION_PATTERNS = (
    re.compile(r"\(([a-z])\)", re.IGNORECASE),
    re.compile(r"\boption\s*([a-z])\b", re.IGNORECASE),
    re.compile(r"选\s*([a-z])", re.IGNORECASE),
    re.compile(r"\banswer\s*(?:is|:)\s*([a-z])\b", re.IGNORECASE),
    re.compile(r"^\s*([a-z])(?:\s*$|[.):]\s*)", re.IGNORECASE),
)


def extract_option_label(text: str) -> str:
    for pattern in _OPTION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return f"({match.group(1).lower()})"
    return ""


def answer_accuracy(response: str, gold: str) -> float:
    return float(extract_option_label(response) == extract_option_label(gold) and bool(extract_option_label(gold)))


def answer_parse_failed(response: str) -> float:
    return float(not bool(extract_option_label(response)))


def recall_at_k(selected_ids: Sequence[str], gold_ids: Iterable[str], k: int) -> float:
    gold = set(gold_ids)
    if not gold:
        return 0.0
    return len(set(selected_ids[:k]) & gold) / len(gold)


def direct_ranks(query_vector: np.ndarray, ids: Sequence[str], vectors: np.ndarray) -> Dict[str, int]:
    index = ExactInnerProductIndex(ids, vectors)
    return {memory_id: rank for rank, (memory_id, _score) in enumerate(index.search(query_vector, len(ids)), start=1)}


def bridge_recall_at_k(
    selected_ids: Sequence[str],
    gold_ids: Iterable[str],
    ranks: Mapping[str, int],
    k: int,
) -> float | None:
    # Gold is externally annotated. Direct rank only partitions that gold set;
    # bridge lift is never used to define relevance.
    bridge_gold = {memory_id for memory_id in gold_ids if ranks.get(memory_id, 0) > k}
    return recall_at_k(selected_ids, bridge_gold, k) if bridge_gold else None


def greedy_ids(nodes: Mapping[str, TreeNode], feature_kind: str, k: int) -> List[str]:
    selected: List[str] = []
    selected_features: List[np.ndarray] = []
    while len(selected) < min(k, len(nodes)):
        available = [memory_id for memory_id in nodes if memory_id not in selected]
        features = {
            memory_id: (
                nodes[memory_id].innovation
                if feature_kind == "path_conditioned"
                else nodes[memory_id].reachability * nodes[memory_id].vector
            )
            for memory_id in available
        }
        best = min(
            available,
            key=lambda memory_id: (-logdet_marginal(features[memory_id], selected_features), memory_id),
        )
        selected.append(best)
        selected_features.append(features[best])
    return selected


def path_objective_advantage(result: RetrievalResult, k: int) -> float:
    """Internal fixed-candidate path objective advantage; never a tuning target."""
    path_ids = greedy_ids(result.nodes, "path_conditioned", k)
    rho_ids = greedy_ids(result.nodes, "rho_weighted", k)
    path_value = logdet_value([result.nodes[memory_id].innovation for memory_id in path_ids])
    rho_set_on_path_geometry = logdet_value([result.nodes[memory_id].innovation for memory_id in rho_ids])
    return float(path_value - rho_set_on_path_geometry)


def paired_bootstrap_interval(
    left: Sequence[float],
    right: Sequence[float],
    *,
    seed: int = 42,
    resamples: int = 2000,
    confidence: float = 0.95,
) -> Dict[str, float]:
    if len(left) != len(right) or not left:
        raise ValueError("paired bootstrap requires equally sized non-empty samples")
    if resamples <= 0 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid bootstrap settings")
    differences = np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)
    rng = np.random.default_rng(seed)
    sample_positions = rng.integers(0, len(differences), size=(resamples, len(differences)))
    estimates = differences[sample_positions].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return {
        "mean_difference": float(differences.mean()),
        "ci_low": float(np.quantile(estimates, alpha)),
        "ci_high": float(np.quantile(estimates, 1.0 - alpha)),
        "confidence": confidence,
        "resamples": float(resamples),
    }


def branch_ranking_stability(
    branch: Branch,
    index: ExactInnerProductIndex,
    candidate_ids: Sequence[str] | None = None,
) -> float:
    """Fraction of radius-qualified candidate pairs whose order is preserved.

    This directly operationalizes Lemma 3.2: only pairs whose member-distance
    gap exceeds 2*r_c enter the denominator.
    """
    candidates = list(candidate_ids or index.ids)
    if len(candidates) < 2:
        return 1.0
    candidate_vectors = {memory_id: index.vector(memory_id) for memory_id in candidates}
    probe_distances = {
        memory_id: float(np.arccos(np.clip(np.dot(branch.probe, vector), -1.0, 1.0)))
        for memory_id, vector in candidate_vectors.items()
    }
    stable = 0
    eligible = 0
    for member_id in branch.member_ids:
        member = index.vector(member_id)
        member_distances = {
            memory_id: float(np.arccos(np.clip(np.dot(member, vector), -1.0, 1.0)))
            for memory_id, vector in candidate_vectors.items()
        }
        for left, right in combinations(candidates, 2):
            member_gap = member_distances[left] - member_distances[right]
            if abs(member_gap) <= 2.0 * branch.radius_radians:
                continue
            eligible += 1
            probe_gap = probe_distances[left] - probe_distances[right]
            stable += int(member_gap * probe_gap >= 0.0)
    return stable / eligible if eligible else 1.0


def summarize_bridge_results(results: Sequence[RetrievalResult]) -> Dict[str, float]:
    if not results:
        return {
            "queries": 0,
            "certified_stop_rate": 0.0,
            "budget_truncation_rate": 0.0,
            "mean_posterior_error": 0.0,
            "mean_visited_nodes": 0.0,
            "mean_ann_calls": 0.0,
        }
    count = len(results)
    return {
        "queries": count,
        "certified_stop_rate": sum(result.certified for result in results) / count,
        "budget_truncation_rate": sum(result.budget_frozen for result in results) / count,
        "mean_posterior_error": sum(result.posterior_error for result in results) / count,
        "mean_visited_nodes": sum(result.visited_nodes for result in results) / count,
        "mean_ann_calls": sum(result.ann_calls for result in results) / count,
        "mean_cluster_radius_radians": (
            sum(sum(result.cluster_radii) for result in results)
            / max(1, sum(len(result.cluster_radii) for result in results))
        ),
        "mean_cluster_ranking_stability": (
            sum(sum(result.cluster_stabilities) for result in results)
            / max(1, sum(len(result.cluster_stabilities) for result in results))
        ),
    }
