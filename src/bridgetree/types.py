from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Memory:
    memory_id: str
    text: str
    timestamp: float
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TreeNode:
    memory: Memory
    vector: np.ndarray
    parent_id: Optional[str]
    depth: int
    direct_score: float
    reachability: float
    innovation: np.ndarray
    bridge_lift: float
    discovery_order: int

    def public_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory.memory_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "direct_score": self.direct_score,
            "reachability": self.reachability,
            "bridge_lift": self.bridge_lift,
            "innovation_norm_sq": float(np.dot(self.innovation, self.innovation)),
            "discovery_order": self.discovery_order,
        }


@dataclass
class Branch:
    branch_id: str
    member_ids: Tuple[str, ...]
    probe: np.ndarray
    path_upper_bound: float
    marginal_upper_bound: float
    radius_radians: float
    depth: int
    creation_order: int

    def public_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "member_ids": list(self.member_ids),
            "path_upper_bound": self.path_upper_bound,
            "marginal_upper_bound": self.marginal_upper_bound,
            "radius_radians": self.radius_radians,
            "depth": self.depth,
            "creation_order": self.creation_order,
        }


@dataclass(frozen=True)
class SelectionStep:
    step: int
    memory_id: str
    discovered_best_margin: float
    unseen_upper_bound: float
    epsilon: float
    certified: bool


@dataclass
class RetrievalResult:
    query: str
    selected: List[Memory]
    selected_in_greedy_order: List[str]
    nodes: Dict[str, TreeNode]
    edges: List[Tuple[Optional[str], str]]
    all_branches: List[Branch]
    remaining_branches: List[Branch]
    selection_steps: List[SelectionStep]
    ann_calls: int
    visited_nodes: int
    budget_frozen: bool
    cluster_radii: List[float]
    cluster_stabilities: List[float]

    @property
    def certified(self) -> bool:
        return bool(self.selection_steps) and all(step.certified for step in self.selection_steps)

    @property
    def posterior_error(self) -> float:
        k = len(self.selection_steps)
        if k == 0:
            return 0.0
        return float(sum(((1.0 - 1.0 / k) ** (k - step.step)) * step.epsilon for step in self.selection_steps))

    def to_dict(self, include_text: bool = True) -> Dict[str, Any]:
        selected = []
        for memory in self.selected:
            item = asdict(memory)
            if not include_text:
                item.pop("text", None)
            selected.append(item)
        return {
            "query": self.query,
            "selected": selected,
            "selected_in_greedy_order": self.selected_in_greedy_order,
            "nodes": [node.public_dict() for node in self.nodes.values()],
            "edges": self.edges,
            "all_branches": [branch.public_dict() for branch in self.all_branches],
            "remaining_branches": [branch.public_dict() for branch in self.remaining_branches],
            "selection_steps": [asdict(step) for step in self.selection_steps],
            "ann_calls": self.ann_calls,
            "visited_nodes": self.visited_nodes,
            "budget_frozen": self.budget_frozen,
            "certified": self.certified,
            "posterior_error": self.posterior_error,
            "cluster_radii": self.cluster_radii,
            "cluster_stabilities": self.cluster_stabilities,
        }
