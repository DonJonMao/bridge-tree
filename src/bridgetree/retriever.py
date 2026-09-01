from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .clustering import cluster_siblings
from .config import RetrievalConfig
from .index import ExactInnerProductIndex, build_index
from .math_utils import logdet_marginal, nonnegative_cosine, normalize, normalize_rows, path_conditioned_innovation
from .types import Branch, Memory, RetrievalResult, SelectionStep, TreeNode


@dataclass(frozen=True)
class AlgorithmOptions:
    cluster_mode: str = "effective_rank"  # effective_rank | none
    frontier_mode: str = "best_first"  # best_first | bfs
    selection_mode: str = "logdet"  # logdet | reachability
    feature_mode: str = "path_conditioned"  # path_conditioned | rho_weighted
    reachability_mode: str = "bottleneck"  # bottleneck | direct
    stopping_mode: str = "certificate"  # certificate | budget_only | fixed_depth
    max_depth: int = 3

    def validate(self) -> None:
        allowed = {
            "cluster_mode": (self.cluster_mode, {"effective_rank", "none"}),
            "frontier_mode": (self.frontier_mode, {"best_first", "bfs"}),
            "selection_mode": (self.selection_mode, {"logdet", "reachability"}),
            "feature_mode": (self.feature_mode, {"path_conditioned", "rho_weighted"}),
            "reachability_mode": (self.reachability_mode, {"bottleneck", "direct"}),
            "stopping_mode": (self.stopping_mode, {"certificate", "budget_only", "fixed_depth"}),
        }
        for name, (value, choices) in allowed.items():
            if value not in choices:
                raise ValueError(f"{name} must be one of {sorted(choices)}")


class BridgeTreeRetriever:
    """Algorithm 1 from the BridgeTree design, including its certificates."""

    def __init__(self, config: RetrievalConfig, options: AlgorithmOptions | None = None):
        config.validate()
        self.config = config
        self.options = options or AlgorithmOptions()
        self.options.validate()

    def retrieve(
        self,
        query: str,
        query_vector: np.ndarray,
        memories: Sequence[Memory],
        memory_vectors: np.ndarray,
    ) -> RetrievalResult:
        if not memories:
            return RetrievalResult(query, [], [], {}, [], [], [], [], 0, 0, False, [], [])
        if len(memories) != len(memory_vectors):
            raise ValueError("memories and memory_vectors must have equal length")

        query_vector = normalize(query_vector)
        memory_vectors = normalize_rows(memory_vectors)
        ids = [memory.memory_id for memory in memories]
        if len(set(ids)) != len(ids):
            raise ValueError("memory ids must be unique")
        memory_by_id = {memory.memory_id: memory for memory in memories}
        index = build_index(self.config.index_backend, ids, memory_vectors)
        direct_scores = {memory_id: nonnegative_cosine(query_vector, index.vector(memory_id)) for memory_id in ids}

        first_width = min(self.config.first_hop_width, self.config.search_budget, len(memories))
        first_hits = index.search(query_vector, first_width)
        nodes: Dict[str, TreeNode] = {}
        edges: List[Tuple[Optional[str], str]] = []
        discovery_order = 0
        for memory_id, _score in first_hits:
            reachability = direct_scores[memory_id]
            vector = index.vector(memory_id)
            innovation = reachability * vector
            nodes[memory_id] = TreeNode(
                memory=memory_by_id[memory_id],
                vector=vector,
                parent_id=None,
                depth=1,
                direct_score=direct_scores[memory_id],
                reachability=reachability,
                innovation=innovation,
                bridge_lift=0.0,
                discovery_order=discovery_order,
            )
            discovery_order += 1
            edges.append((None, memory_id))

        frontier: List[Tuple[Tuple[float, ...], str, Branch]] = []
        all_branches: List[Branch] = []
        branch_counter = 0
        cluster_radii: List[float] = []

        def push_sibling_branches(sibling_ids: Sequence[str], depth: int) -> None:
            nonlocal branch_counter
            if not sibling_ids:
                return
            ordered = sorted(sibling_ids)
            sibling_vectors = np.vstack([nodes[memory_id].vector for memory_id in ordered])
            reaches = [nodes[memory_id].reachability for memory_id in ordered]
            clusters = cluster_siblings(
                sibling_vectors,
                reaches,
                disable_compression=self.options.cluster_mode == "none",
            )
            for cluster in clusters:
                member_ids = tuple(ordered[position] for position in cluster.member_positions)
                path_upper = max(nodes[memory_id].reachability for memory_id in member_ids)
                branch = Branch(
                    branch_id=f"b{branch_counter:08d}",
                    member_ids=member_ids,
                    probe=cluster.probe,
                    path_upper_bound=path_upper,
                    marginal_upper_bound=float(np.log1p(path_upper**2)),
                    radius_radians=cluster.radius_radians,
                    depth=depth,
                    creation_order=branch_counter,
                )
                branch_counter += 1
                cluster_radii.append(cluster.radius_radians)
                all_branches.append(branch)
                if self.options.frontier_mode == "best_first":
                    priority = (-branch.path_upper_bound, float(branch.creation_order))
                else:
                    priority = (float(branch.depth), float(branch.creation_order))
                heapq.heappush(frontier, (priority, branch.branch_id, branch))

        push_sibling_branches(list(nodes), depth=1)
        selected_ids: List[str] = []
        selection_steps: List[SelectionStep] = []
        ann_calls = 1
        frozen = False
        budget_frozen = False

        while len(selected_ids) < min(self.config.context_size, len(memories)):
            available = [memory_id for memory_id in nodes if memory_id not in selected_ids]
            if not available:
                if len(nodes) >= min(self.config.search_budget, len(memories)):
                    budget_frozen = len(nodes) < len(memories)
                    break
                if frontier and not frozen:
                    made_ann_call = self._expand_one(
                        frontier,
                        index,
                        memory_by_id,
                        direct_scores,
                        nodes,
                        edges,
                        push_sibling_branches,
                        discovery_order,
                    )
                    ann_calls += int(made_ann_call)
                    discovery_order = len(nodes)
                    continue
                break

            selected_features = [nodes[memory_id].innovation for memory_id in selected_ids]
            margins = {memory_id: self._selection_score(nodes[memory_id], selected_features) for memory_id in available}
            best_id = min(available, key=lambda memory_id: (-margins[memory_id], memory_id))
            best_margin = margins[best_id]
            # A queued probe has no unknown descendants after the entire finite
            # memory bank has been visited; its formal path bound then applies
            # to an empty set and must not create a spurious posterior gap.
            if len(nodes) == len(memories):
                frontier.clear()
            unseen_upper = max((item[2].marginal_upper_bound for item in frontier), default=0.0)

            certificate_allowed = (
                self.options.stopping_mode == "certificate"
                and self.options.reachability_mode == "bottleneck"
                and self.options.selection_mode == "logdet"
            )
            certified = certificate_allowed and best_margin + self.config.tie_tolerance >= unseen_upper

            if certified:
                selected_ids.append(best_id)
                selection_steps.append(SelectionStep(len(selected_ids), best_id, best_margin, unseen_upper, 0.0, True))
                continue

            budget_reached = len(nodes) >= min(self.config.search_budget, len(memories))
            fixed_depth_done = self.options.stopping_mode == "fixed_depth" and not any(
                item[2].depth < self.options.max_depth for item in frontier
            )
            if frozen or budget_reached or fixed_depth_done or not frontier:
                frozen = True
                budget_frozen = budget_frozen or budget_reached
                epsilon = max(0.0, unseen_upper - best_margin)
                selected_ids.append(best_id)
                selection_steps.append(
                    SelectionStep(len(selected_ids), best_id, best_margin, unseen_upper, epsilon, False)
                )
                continue

            made_ann_call = self._expand_one(
                frontier,
                index,
                memory_by_id,
                direct_scores,
                nodes,
                edges,
                push_sibling_branches,
                discovery_order,
            )
            ann_calls += int(made_ann_call)
            discovery_order = len(nodes)

        chronological_ids = sorted(
            selected_ids,
            key=lambda memory_id: (nodes[memory_id].memory.timestamp, memory_id),
        )
        remaining = [item[2] for item in sorted(frontier)]
        # The metric is diagnostic only and does not issue extra ANN calls.
        from .metrics import branch_ranking_stability

        cluster_stabilities = []
        for branch in all_branches:
            audit_candidates = [memory_id for memory_id, _score in index.search(branch.probe, min(32, len(memories)))]
            cluster_stabilities.append(branch_ranking_stability(branch, index, audit_candidates))
        return RetrievalResult(
            query=query,
            selected=[memory_by_id[memory_id] for memory_id in chronological_ids],
            selected_in_greedy_order=selected_ids,
            nodes=nodes,
            edges=edges,
            all_branches=all_branches,
            remaining_branches=remaining,
            selection_steps=selection_steps,
            ann_calls=ann_calls,
            visited_nodes=len(nodes),
            budget_frozen=budget_frozen,
            cluster_radii=cluster_radii,
            cluster_stabilities=cluster_stabilities,
        )

    def _selection_score(self, node: TreeNode, selected_features: Sequence[np.ndarray]) -> float:
        if self.options.selection_mode == "reachability":
            return node.reachability
        return logdet_marginal(node.innovation, selected_features)

    def _expand_one(
        self,
        frontier: List[Tuple[Tuple[float, ...], str, Branch]],
        index: ExactInnerProductIndex,
        memory_by_id: Mapping[str, Memory],
        direct_scores: Mapping[str, float],
        nodes: Dict[str, TreeNode],
        edges: List[Tuple[Optional[str], str]],
        push_sibling_branches,
        discovery_order: int,
    ) -> bool:
        _priority, _branch_id, branch = heapq.heappop(frontier)
        if self.options.stopping_mode == "fixed_depth" and branch.depth >= self.options.max_depth:
            return False
        capacity = min(self.config.branch_width, self.config.search_budget - len(nodes))
        if capacity <= 0:
            return False
        candidates = index.search(branch.probe, capacity, exclude=nodes)
        children_by_parent: Dict[str, List[str]] = {}
        for offset, (candidate_id, _probe_score) in enumerate(candidates):
            parent_id = min(
                branch.member_ids,
                key=lambda memory_id: (
                    -min(
                        nodes[memory_id].reachability,
                        nonnegative_cosine(nodes[memory_id].vector, index.vector(candidate_id)),
                    ),
                    memory_id,
                ),
            )
            edge_similarity = nonnegative_cosine(nodes[parent_id].vector, index.vector(candidate_id))
            if self.options.reachability_mode == "bottleneck":
                reachability = min(nodes[parent_id].reachability, edge_similarity)
            else:
                reachability = direct_scores[candidate_id]
            ancestor_vectors = []
            current: Optional[str] = parent_id
            while current is not None:
                ancestor = nodes[current]
                ancestor_vectors.append(ancestor.reachability * ancestor.vector)
                current = ancestor.parent_id
            ancestor_vectors.reverse()
            vector = index.vector(candidate_id)
            if self.options.feature_mode == "path_conditioned":
                innovation = path_conditioned_innovation(vector, reachability, ancestor_vectors)
            else:
                innovation = reachability * vector
            nodes[candidate_id] = TreeNode(
                memory=memory_by_id[candidate_id],
                vector=vector,
                parent_id=parent_id,
                depth=nodes[parent_id].depth + 1,
                direct_score=direct_scores[candidate_id],
                reachability=reachability,
                innovation=innovation,
                bridge_lift=max(0.0, reachability - direct_scores[candidate_id]),
                discovery_order=discovery_order + offset,
            )
            edges.append((parent_id, candidate_id))
            children_by_parent.setdefault(parent_id, []).append(candidate_id)
        for child_ids in children_by_parent.values():
            push_sibling_branches(child_ids, depth=nodes[child_ids[0]].depth)
        return True
