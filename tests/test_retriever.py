from dataclasses import replace

import numpy as np

from bridgetree.config import RetrievalConfig
from bridgetree.math_utils import logdet_marginal
from bridgetree.retriever import BridgeTreeRetriever
from bridgetree.types import Memory


def _memories(count):
    return [Memory(f"m{i}", f"memory {i}", float(i), f"source:{i}") for i in range(count)]


def test_tree_edges_always_point_to_real_memories_and_probes_are_not_nodes():
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.8, 0.6, 0.0],
            [0.1, 0.99, 0.0],
            [0.0, 0.8, 0.6],
            [0.0, 0.1, 0.99],
        ]
    )
    config = RetrievalConfig(first_hop_width=2, branch_width=2, context_size=3, search_budget=5)
    result = BridgeTreeRetriever(config).retrieve("query", np.array([1.0, 0.0, 0.0]), _memories(5), vectors)
    assert all(child in result.nodes for _parent, child in result.edges)
    assert all(parent is None or parent in result.nodes for parent, _child in result.edges)
    assert not any(branch.branch_id in result.nodes for branch in result.all_branches)
    for node in result.nodes.values():
        if node.parent_id is not None:
            assert node.reachability <= result.nodes[node.parent_id].reachability + 1e-12


def test_path_innovation_is_norm_bounded_and_marginal_bound_holds():
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(14, 6))
    query = rng.normal(size=6)
    config = RetrievalConfig(first_hop_width=4, branch_width=3, context_size=4, search_budget=12)
    result = BridgeTreeRetriever(config).retrieve("query", query, _memories(14), vectors)
    for node in result.nodes.values():
        assert float(node.innovation @ node.innovation) <= node.reachability**2 + 1e-10
    selected_features = []
    for memory_id in result.selected_in_greedy_order:
        node = result.nodes[memory_id]
        assert logdet_marginal(node.innovation, selected_features) <= np.log1p(node.reachability**2) + 1e-10
        selected_features.append(node.innovation)


def test_full_visit_clears_unknown_bound_and_certifies_each_selection():
    vectors = np.eye(5)
    config = RetrievalConfig(
        first_hop_width=5,
        branch_width=2,
        context_size=3,
        search_budget=5,
        stop_mode="certificate_or_budget",
    )
    result = BridgeTreeRetriever(config).retrieve("query", np.ones(5), _memories(5), vectors)
    assert result.certified
    assert all(step.unseen_upper_bound == 0.0 and step.epsilon == 0.0 for step in result.selection_steps)


def test_budget_freeze_records_nonnegative_gaps_and_weighted_total():
    rng = np.random.default_rng(11)
    vectors = rng.normal(size=(12, 5))
    config = RetrievalConfig(first_hop_width=3, branch_width=2, context_size=3, search_budget=3)
    result = BridgeTreeRetriever(config).retrieve("query", rng.normal(size=5), _memories(12), vectors)
    assert result.budget_frozen
    assert all(step.epsilon >= 0.0 for step in result.selection_steps)
    assert result.posterior_error >= 0.0
    assert result.visited_nodes == 3


def test_output_context_is_chronological_not_greedy_order():
    vectors = np.eye(4)
    memories = _memories(4)
    config = RetrievalConfig(first_hop_width=4, branch_width=2, context_size=3, search_budget=4)
    result = BridgeTreeRetriever(config).retrieve("query", np.array([0.2, 0.9, 0.8, 1.0]), memories, vectors)
    assert [memory.timestamp for memory in result.selected] == sorted(memory.timestamp for memory in result.selected)


def test_branch_upper_bounds_every_discovered_descendant_and_bridge_lift_is_real():
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.05, 0.9987],
            [-0.3, 0.9539],
            [-0.7, 0.7141],
            [0.4, -0.9165],
        ]
    )
    config = RetrievalConfig(first_hop_width=2, branch_width=2, context_size=4, search_budget=6)
    result = BridgeTreeRetriever(config).retrieve("query", np.array([1.0, 0.0]), _memories(6), vectors)
    assert any(node.bridge_lift > 0.0 for node in result.nodes.values())
    for branch in result.all_branches:
        for node in result.nodes.values():
            current = node.parent_id
            while current is not None:
                if current in branch.member_ids:
                    assert node.reachability <= branch.path_upper_bound + 1e-12
                    break
                current = result.nodes[current].parent_id
    for step in result.selection_steps:
        if step.certified:
            assert step.discovered_best_margin + config.tie_tolerance >= step.unseen_upper_bound
        else:
            assert np.isclose(step.epsilon, max(0.0, step.unseen_upper_bound - step.discovered_best_margin))


def test_depth_two_discovers_the_synthetic_bridge_and_first_arrival_is_reproducible():
    vectors = np.asarray(
        [
            [0.8, 0.6],  # m1: direct first hop
            [0.0, 1.0],  # m2: weak direct score, strong m1 edge
            [0.7, -0.714],
        ]
    )
    query = np.asarray([1.0, 0.0])
    depth_one = RetrievalConfig(initial_width=1, branch_width=1, context_size=1, search_budget=3, max_depth=1)
    depth_two = RetrievalConfig(initial_width=1, branch_width=1, context_size=1, search_budget=3, max_depth=2)
    shallow = BridgeTreeRetriever(depth_one).retrieve("q", query, _memories(3), vectors)
    deep_first = BridgeTreeRetriever(depth_two).retrieve("q", query, _memories(3), vectors)
    deep_second = BridgeTreeRetriever(depth_two).retrieve("q", query, _memories(3), vectors)
    assert "m1" not in shallow.nodes
    assert "m1" in deep_first.nodes
    assert deep_first.edges == deep_second.edges
    assert deep_first.first_arrival_semantics == "deterministic_first_arrival"
    assert len({child for _parent, child in deep_first.edges}) == len(deep_first.edges)


def test_core_path_certificate_and_full_are_runtime_combinations_of_one_implementation():
    rng = np.random.default_rng(101)
    vectors = rng.normal(size=(12, 6))
    query = rng.normal(size=6)
    core = RetrievalConfig(
        initial_width=4,
        branch_width=2,
        context_size=3,
        search_budget=9,
        max_depth=2,
        cluster_mode="fixed",
        feature_mode="rho",
        selection_mode="rho_logdet",
        stop_mode="budget",
    )
    path = replace(core, feature_mode="path_conditioned", selection_mode="path_logdet")
    certificate = replace(path, stop_mode="certificate_or_budget")
    full = replace(certificate, cluster_mode="effective_rank", max_depth=3)
    results = [
        BridgeTreeRetriever(config).retrieve("q", query, _memories(12), vectors)
        for config in (core, path, certificate, full)
    ]
    assert all(type(result) is type(results[0]) for result in results)
    assert set(results[0].nodes) == set(results[1].nodes)
    assert results[0].edges == results[1].edges
    assert any(
        not np.allclose(results[0].nodes[memory_id].innovation, results[1].nodes[memory_id].innovation)
        for memory_id in results[0].nodes
        if results[0].nodes[memory_id].depth > 1
    )
    assert results[2].cost.ann_calls_core <= results[1].cost.ann_calls_core
    assert results[3].first_arrival_semantics == "deterministic_first_arrival"
