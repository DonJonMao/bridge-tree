from __future__ import annotations

import heapq
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .budget import CostTracker, SearchBudget
from .clustering import cluster_siblings
from .config import RetrievalConfig
from .index import ExactInnerProductIndex, build_index
from .math_utils import logdet_marginal, nonnegative_cosine, normalize, normalize_rows, path_conditioned_innovation
from .types import Branch, Memory, RetrievalResult, SelectionStep, TreeNode


class BridgeTreeRetriever:
    """One deterministic first-arrival implementation controlled by runtime config."""

    def __init__(self, config: RetrievalConfig):
        config.validate()
        self.config = config

    def _anchor_reachability(self, reachability: float, direct_score: float) -> float:
        weight = self.config.root_anchor_weight
        return reachability * ((1.0 - weight) + weight * direct_score)

    def retrieve(
        self,
        query: str,
        query_vector: np.ndarray,
        memories: Sequence[Memory],
        memory_vectors: np.ndarray,
        *,
        index: ExactInnerProductIndex | None = None,
        budget: SearchBudget | None = None,
        cost_tracker: CostTracker | None = None,
        index_build_ms: float = 0.0,
        initial_hits: Sequence[Tuple[str, float]] | None = None,
        excluded_candidate_ids: Sequence[str] = (),
    ) -> RetrievalResult:
        if len(memories) != len(memory_vectors):
            raise ValueError("memories and memory_vectors must have equal length")
        search_budget = budget or SearchBudget.from_config(self.config)
        tracker = cost_tracker or CostTracker(search_budget)
        tracker.index_build_ms += index_build_ms
        if not memories:
            tracker.set_stop_reason("insufficient_candidates")
            return RetrievalResult(query, [], [], {}, [], [], [], [], tracker, False, [], [])

        query_vector = normalize(query_vector).astype(np.float32)
        memory_vectors = normalize_rows(memory_vectors).astype(np.float32)
        ids = [memory.memory_id for memory in memories]
        if len(set(ids)) != len(ids):
            raise ValueError("memory ids must be unique")
        memory_by_id = {memory.memory_id: memory for memory in memories}
        if index is None:
            index_started = time.perf_counter()
            index = build_index(
                self.config.index_backend,
                ids,
                memory_vectors,
                exclusion_margin=self.config.faiss_exclusion_margin,
            )
            tracker.index_build_ms += (time.perf_counter() - index_started) * 1000.0

        previous_core_ms = tracker.retrieval_core_ms
        core_started = time.perf_counter()
        direct_scores: Dict[str, float] = {}

        def direct_score(memory_id: str) -> float:
            if memory_id not in direct_scores:
                direct_scores[memory_id] = nonnegative_cosine(query_vector, index.vector(memory_id))
            return direct_scores[memory_id]

        first_width = min(self.config.initial_width, search_budget.max_unique_nodes, len(memories))
        if initial_hits is None:
            first_hits = tracker.search_core(index, query_vector, first_width)
        else:
            unknown = [memory_id for memory_id, _score in initial_hits if memory_id not in memory_by_id]
            if unknown:
                raise ValueError(f"initial_hits contain unknown memory ids: {unknown}")
            first_hits = list(initial_hits[:first_width])
            tracker.mark_visited(memory_id for memory_id, _score in initial_hits)
        nodes: Dict[str, TreeNode] = {}
        edges: List[Tuple[Optional[str], str]] = []
        for discovery_order, (memory_id, _score) in enumerate(first_hits):
            score = direct_score(memory_id)
            reachability = self._anchor_reachability(score, score)
            vector = index.vector(memory_id)
            unit_vector = np.asarray(vector, dtype=np.float64)
            unit_vector /= max(1.0, float(np.linalg.norm(unit_vector)))
            nodes[memory_id] = TreeNode(
                memory=memory_by_id[memory_id],
                vector=vector,
                parent_id=None,
                depth=1,
                direct_score=score,
                reachability=reachability,
                innovation=reachability * unit_vector,
                bridge_lift=0.0,
                discovery_order=discovery_order,
            )
            edges.append((None, memory_id))

        frontier: List[Tuple[Tuple[float, ...], str, Branch]] = []
        all_branches: List[Branch] = []
        cluster_radii: List[float] = []
        cluster_member_counts: List[int] = []
        branch_audit_candidates: Dict[str, List[str]] = {}
        branch_counter = 0
        clustering_ms = 0.0

        def push_sibling_branches(sibling_ids: Sequence[str], depth: int) -> None:
            nonlocal branch_counter, clustering_ms
            if not sibling_ids:
                return
            ordered = sorted(sibling_ids)
            sibling_vectors = np.vstack([nodes[memory_id].vector for memory_id in ordered])
            reaches = [nodes[memory_id].reachability for memory_id in ordered]
            clustering_started = time.perf_counter()
            clusters = cluster_siblings(
                sibling_vectors,
                reaches,
                mode=self.config.cluster_mode,
                fixed_count=self.config.cluster_count,
                max_clusters=self.config.max_clusters,
                min_cluster_size=self.config.min_cluster_size,
            )
            clustering_ms += (time.perf_counter() - clustering_started) * 1000.0
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
                cluster_member_counts.append(len(member_ids))
                all_branches.append(branch)
                if self.config.search_order == "best_first":
                    priority = (-branch.path_upper_bound, float(branch.creation_order))
                else:
                    priority = (float(branch.depth), float(branch.creation_order))
                heapq.heappush(frontier, (priority, branch.branch_id, branch))

        push_sibling_branches(list(nodes), depth=1)
        selected_ids: List[str] = []
        selection_steps: List[SelectionStep] = []
        frozen = False
        stopped_by_budget = False
        stopped_by_depth = False
        target_count = min(self.config.context_size, len(memories))

        while len(selected_ids) < target_count:
            available = [memory_id for memory_id in nodes if memory_id not in selected_ids]
            if not available:
                if frontier and not frozen:
                    expanded = self._expand_one(
                        frontier,
                        index,
                        query_vector,
                        memory_by_id,
                        direct_scores,
                        nodes,
                        edges,
                        push_sibling_branches,
                        len(nodes),
                        branch_audit_candidates,
                        search_budget,
                        tracker,
                        excluded_candidate_ids,
                    )
                    if expanded:
                        continue
                break

            selected_nodes = [nodes[memory_id] for memory_id in selected_ids]
            margins = {memory_id: self._selection_score(nodes[memory_id], selected_nodes) for memory_id in available}
            best_id = min(available, key=lambda memory_id: (-margins[memory_id], memory_id))
            best_margin = margins[best_id]
            if len(nodes) == len(memories):
                frontier.clear()
            unseen_upper = max((item[2].marginal_upper_bound for item in frontier), default=0.0)
            certificate_allowed = self.config.stop_mode == "certificate_or_budget" and self.config.selection_mode in {
                "rho_logdet",
                "path_logdet",
            }
            certified = certificate_allowed and best_margin + self.config.tie_tolerance >= unseen_upper
            if certified:
                selected_ids.append(best_id)
                selection_steps.append(SelectionStep(len(selected_ids), best_id, best_margin, unseen_upper, 0.0, True))
                continue

            node_budget_reached = len(nodes) >= min(search_budget.max_unique_nodes, len(memories))
            core_search_blocked = not tracker.can_search_core()
            expandable = any(item[2].depth < self.config.max_depth for item in frontier)
            if frozen or node_budget_reached or core_search_blocked or not expandable or not frontier:
                frozen = True
                stopped_by_budget = stopped_by_budget or (
                    len(nodes) < len(memories) and (node_budget_reached or core_search_blocked)
                )
                stopped_by_depth = stopped_by_depth or (bool(frontier) and not expandable)
                epsilon = max(0.0, unseen_upper - best_margin)
                selected_ids.append(best_id)
                selection_steps.append(
                    SelectionStep(len(selected_ids), best_id, best_margin, unseen_upper, epsilon, False)
                )
                continue

            self._expand_one(
                frontier,
                index,
                query_vector,
                memory_by_id,
                direct_scores,
                nodes,
                edges,
                push_sibling_branches,
                len(nodes),
                branch_audit_candidates,
                search_budget,
                tracker,
                excluded_candidate_ids,
            )

        tracker.retrieval_core_ms = previous_core_ms + (time.perf_counter() - core_started) * 1000.0
        if len(selected_ids) < target_count:
            tracker.set_stop_reason("insufficient_candidates")
        elif selection_steps and all(step.certified for step in selection_steps):
            tracker.set_stop_reason("certificate")
        elif stopped_by_budget:
            tracker.set_stop_reason("search_budget")
        elif stopped_by_depth:
            tracker.set_stop_reason("max_depth")
        else:
            tracker.set_stop_reason("frontier_empty")

        diagnostic_started = time.perf_counter()
        from .metrics import branch_ranking_stability

        cluster_stabilities = []
        if self.config.diagnostic_level == "light":
            for branch in all_branches:
                candidates = branch_audit_candidates.get(branch.branch_id)
                if candidates:
                    cluster_stabilities.append(branch_ranking_stability(branch, index, candidates))
        elif self.config.diagnostic_level == "full":
            for branch in all_branches:
                hits = tracker.search_diagnostic(index, branch.probe, min(32, len(memories)))
                cluster_stabilities.append(
                    branch_ranking_stability(branch, index, [memory_id for memory_id, _score in hits])
                )
        if self.config.diagnostic_level != "off":
            tracker.diagnostic_ms = (time.perf_counter() - diagnostic_started) * 1000.0

        chronological_ids = sorted(
            selected_ids,
            key=lambda memory_id: (nodes[memory_id].memory.timestamp, memory_id),
        )
        remaining = [item[2] for item in sorted(frontier)]
        return RetrievalResult(
            query=query,
            selected=[memory_by_id[memory_id] for memory_id in chronological_ids],
            selected_in_greedy_order=selected_ids,
            nodes=nodes,
            edges=edges,
            all_branches=all_branches,
            remaining_branches=remaining,
            selection_steps=selection_steps,
            cost_tracker=tracker,
            budget_frozen=stopped_by_budget,
            cluster_radii=cluster_radii,
            cluster_stabilities=cluster_stabilities,
            cluster_member_counts=cluster_member_counts,
            clustering_ms=clustering_ms,
        )

    def _selection_score(self, node: TreeNode, selected_nodes: Sequence[TreeNode]) -> float:
        if self.config.selection_mode == "rho_topk":
            return node.reachability
        if self.config.selection_mode == "mmr":
            redundancy = max(
                (nonnegative_cosine(node.vector, selected.vector) for selected in selected_nodes),
                default=0.0,
            )
            return self.config.mmr_lambda * node.reachability - (1.0 - self.config.mmr_lambda) * redundancy
        return logdet_marginal(node.innovation, [selected.innovation for selected in selected_nodes])

    def _expand_one(
        self,
        frontier: List[Tuple[Tuple[float, ...], str, Branch]],
        index: ExactInnerProductIndex,
        query_vector: np.ndarray,
        memory_by_id: Dict[str, Memory],
        direct_scores: Dict[str, float],
        nodes: Dict[str, TreeNode],
        edges: List[Tuple[Optional[str], str]],
        push_sibling_branches,
        discovery_order: int,
        branch_audit_candidates: Dict[str, List[str]],
        budget: SearchBudget,
        tracker: CostTracker,
        excluded_candidate_ids: Sequence[str],
    ) -> bool:
        _priority, _branch_id, branch = heapq.heappop(frontier)
        if branch.depth >= self.config.max_depth or not tracker.can_search_core():
            return False
        capacity = min(self.config.branch_width, budget.max_unique_nodes - len(nodes))
        if capacity <= 0:
            return False
        candidates = tracker.search_core(
            index,
            branch.probe,
            capacity,
            exclude=set(nodes) | set(excluded_candidate_ids),
        )
        branch_audit_candidates[branch.branch_id] = [memory_id for memory_id, _score in candidates]
        children_by_parent: Dict[str, List[str]] = {}
        for offset, (candidate_id, _probe_score) in enumerate(candidates):
            if candidate_id in nodes:
                continue
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
            raw_reachability = min(nodes[parent_id].reachability, edge_similarity)
            candidate_direct_score = direct_scores.setdefault(
                candidate_id,
                nonnegative_cosine(query_vector, index.vector(candidate_id)),
            )
            reachability = self._anchor_reachability(raw_reachability, candidate_direct_score)
            ancestor_vectors = []
            current: Optional[str] = parent_id
            while current is not None:
                ancestor = nodes[current]
                ancestor_vectors.append(ancestor.reachability * ancestor.vector)
                current = ancestor.parent_id
            ancestor_vectors.reverse()
            vector = index.vector(candidate_id)
            if self.config.feature_mode == "path_conditioned":
                innovation = path_conditioned_innovation(vector, reachability, ancestor_vectors)
            else:
                unit_vector = np.asarray(vector, dtype=np.float64)
                unit_vector /= max(1.0, float(np.linalg.norm(unit_vector)))
                innovation = reachability * unit_vector
            nodes[candidate_id] = TreeNode(
                memory=memory_by_id[candidate_id],
                vector=vector,
                parent_id=parent_id,
                depth=nodes[parent_id].depth + 1,
                direct_score=candidate_direct_score,
                reachability=reachability,
                innovation=innovation,
                bridge_lift=max(0.0, raw_reachability - candidate_direct_score),
                discovery_order=discovery_order + offset,
            )
            edges.append((parent_id, candidate_id))
            children_by_parent.setdefault(parent_id, []).append(candidate_id)
        for child_ids in children_by_parent.values():
            push_sibling_branches(child_ids, depth=nodes[child_ids[0]].depth)
        return bool(candidates)
