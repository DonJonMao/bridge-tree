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
