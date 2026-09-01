from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, Mapping, Sequence

import numpy as np

from .config import RetrievalConfig
from .math_utils import logdet_value
from .metrics import path_innovation_gain
from .types import RetrievalResult

MODULE_NAMES = (
    "encoding",
    "coarse_retrieval",
    "clustering",
    "path",
    "innovation",
    "selection",
    "search",
    "outcome",
    "timing",
)


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _max(values: Sequence[float]) -> float:
    return float(np.max(values)) if values else 0.0


def collect_module_metrics(
    result: RetrievalResult,
    query_vector: np.ndarray,
    memory_vectors: np.ndarray,
    config: RetrievalConfig,
    timings: Mapping[str, float] | None = None,
    answer_accuracy_value: float | None = None,
    recall_value: float | None = None,
    bridge_recall_value: float | None = None,
) -> Dict[str, Dict[str, float]]:
    """Collect independent, numeric diagnostics for every BridgeTree module."""
    query = np.asarray(query_vector, dtype=np.float64)
    memories = np.asarray(memory_vectors, dtype=np.float64)
    query_norm = float(np.linalg.norm(query))
    memory_norms = np.linalg.norm(memories, axis=1) if len(memories) else np.asarray([], dtype=np.float64)
    normalized_query = query / query_norm if query_norm > 0 else query
    normalized_memories = memories / np.maximum(memory_norms[:, None], 1e-12) if len(memories) else memories
    direct_scores = np.maximum(0.0, np.dot(normalized_memories, normalized_query)) if len(memories) else np.asarray([])
    ranked_direct = sorted((float(value) for value in direct_scores), reverse=True)
    first_hop_scores = ranked_direct[: min(config.first_hop_width, len(ranked_direct))]

    nodes = list(result.nodes.values())
    first_hop_nodes = [node for node in nodes if node.depth == 1]
    deep_nodes = [node for node in nodes if node.depth > 1]
    bridge_nodes = [node for node in deep_nodes if node.bridge_lift > 0.0]
    reaches = [node.reachability for node in nodes]
    bridge_lifts = [node.bridge_lift for node in deep_nodes]

    total_branch_members = sum(len(branch.member_ids) for branch in result.all_branches)
    branch_count = len(result.all_branches)
    direction_reduction = 1.0 - branch_count / total_branch_members if total_branch_members else 0.0

    retention = []
    for node in nodes:
        denominator = node.reachability**2
        if denominator > 1e-12:
            retention.append(float(np.dot(node.innovation, node.innovation) / denominator))
    selected_nodes = [result.nodes[memory_id] for memory_id in result.selected_in_greedy_order]
    selected_features = [node.innovation for node in selected_nodes]
    selection_margins = [step.discovered_best_margin for step in result.selection_steps]

    outcome: Dict[str, float] = {}
    if answer_accuracy_value is not None:
        outcome["answer_accuracy"] = float(answer_accuracy_value)
    if recall_value is not None:
        outcome["recall_at_k"] = float(recall_value)
    if bridge_recall_value is not None:
        outcome["bridge_recall_at_k"] = float(bridge_recall_value)

    timing_values = {name: float(value) for name, value in (timings or {}).items()}
    return {
        "encoding": {
            "memory_count": float(len(memories)),
            "embedding_dimension": float(memories.shape[1] if memories.ndim == 2 and len(memories) else len(query)),
            "query_norm": query_norm,
            "mean_memory_norm": _mean([float(value) for value in memory_norms]),
            "nonfinite_value_count": float(
                np.size(memories) - np.isfinite(memories).sum() + np.size(query) - np.isfinite(query).sum()
            ),
        },
        "coarse_retrieval": {
            "first_hop_count": float(len(first_hop_nodes)),
            "max_direct_similarity": _max(ranked_direct),
            "mean_first_hop_similarity": _mean(first_hop_scores),
            "min_first_hop_similarity": float(min(first_hop_scores)) if first_hop_scores else 0.0,
        },
        "clustering": {
            "probe_count": float(branch_count),
            "mean_members_per_probe": total_branch_members / branch_count if branch_count else 0.0,
            "direction_reduction_rate": direction_reduction,
            "mean_radius_radians": _mean(result.cluster_radii),
            "max_radius_radians": _max(result.cluster_radii),
            "ranking_stability_rate": _mean(result.cluster_stabilities),
        },
        "path": {
            "tree_node_count": float(len(nodes)),
            "real_edge_count": float(sum(parent is not None for parent, _child in result.edges)),
            "max_depth": float(max((node.depth for node in nodes), default=0)),
            "deep_node_rate": len(deep_nodes) / len(nodes) if nodes else 0.0,
            "bridge_node_rate": len(bridge_nodes) / len(deep_nodes) if deep_nodes else 0.0,
            "mean_reachability": _mean(reaches),
            "mean_bridge_lift": _mean(bridge_lifts),
            "max_bridge_lift": _max(bridge_lifts),
        },
        "innovation": {
            "mean_retention_ratio": _mean(retention),
            "min_retention_ratio": float(min(retention)) if retention else 0.0,
            "path_innovation_gain": path_innovation_gain(result, config.context_size),
        },
        "selection": {
            "selected_count": float(len(selected_nodes)),
            "logdet_value": logdet_value(selected_features),
            "mean_greedy_margin": _mean(selection_margins),
            "min_greedy_margin": float(min(selection_margins)) if selection_margins else 0.0,
        },
        "search": {
            "ann_calls": float(result.ann_calls),
            "visited_nodes": float(result.visited_nodes),
            "visited_budget_ratio": result.visited_nodes / config.search_budget,
            "certified_query": float(result.certified),
            "budget_frozen": float(result.budget_frozen),
            "posterior_error": float(result.posterior_error),
        },
        "outcome": outcome,
        "timing": timing_values,
    }


def flatten_module_metrics(metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
    return {f"{module}.{name}": float(value) for module, values in metrics.items() for name, value in values.items()}


def aggregate_module_metrics(records: Iterable[Mapping[str, Mapping[str, float]]]) -> Dict[str, Any]:
    sums: Dict[str, float] = defaultdict(float)
    observations: Dict[str, int] = defaultdict(int)
    queries = 0
    for record in records:
        queries += 1
        for name, value in flatten_module_metrics(record).items():
            if np.isfinite(value):
                sums[name] += float(value)
                observations[name] += 1
    modules: Dict[str, Dict[str, float]] = {name: {} for name in MODULE_NAMES}
    for path in sorted(sums):
        module, metric = path.split(".", 1)
        modules.setdefault(module, {})[metric] = sums[path] / observations[path]
    return {
        "queries": queries,
        "modules": modules,
        "observations": dict(sorted(observations.items())),
    }


def metric_value(summary: Mapping[str, Any], path: str) -> float:
    module, metric = path.split(".", 1)
    try:
        return float(summary["modules"][module][metric])
    except (KeyError, TypeError, ValueError) as exc:
        raise KeyError(f"metric is unavailable: {path}") from exc


def module_metric_delta(full: Mapping[str, Any], ablation: Mapping[str, Any]) -> Dict[str, Dict[str, float]]:
    full_flat = flatten_module_metrics(full.get("modules", {}))
    ablation_flat = flatten_module_metrics(ablation.get("modules", {}))
    delta: Dict[str, Dict[str, float]] = {name: {} for name in MODULE_NAMES}
    for path in sorted(set(full_flat) & set(ablation_flat)):
        module, metric = path.split(".", 1)
        delta.setdefault(module, {})[metric] = full_flat[path] - ablation_flat[path]
    return delta
