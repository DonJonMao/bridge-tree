"""Independent checks for the semantic-path mathematical oracle.

This file intentionally imports only ``semantic_core_reference``.  It is run
from the ``reference`` directory as a small, dependency-light contract suite:

    PYTHONPATH=.. python -m pytest -q

The production package is not imported here, so failures cannot be hidden by
shared implementation details.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from semantic_core_reference import (
    FrozenDAG,
    angular_affinity,
    bounded_quality,
    greedy,
    information_atom,
    lazy_greedy,
    logdet_value,
    marginal,
    propagate,
    semantic_atom,
    thin_svd_shrink,
)


def _diamond() -> FrozenDAG:
    return FrozenDAG.build(
        ["r1", "r2", "x", "y", "t"],
        [("r1", "x"), ("r1", "y"), ("r2", "x"), ("r2", "y"), ("x", "t"), ("y", "t")],
        edge_weights={
            ("r1", "x"): 1.0,
            ("r1", "y"): 3.0,
            ("r2", "x"): 2.0,
            ("r2", "y"): 4.0,
            ("x", "t"): 1.0,
            ("y", "t"): 1.0,
        },
        root_mass={"r1": 0.4, "r2": 0.6},
        layers=[["r1", "r2"], ["x", "y"], ["t"]],
    )


def test_unit_and_logit_quality_contract() -> None:
    assert bounded_quality(0.0) == 0.0
    assert bounded_quality(1.0) == 1.0
    assert math.isclose(bounded_quality(0.0, "logit_difference"), 0.5)
    assert math.isclose(bounded_quality(2.0, "logit"), 1.0 / (1.0 + math.exp(-2.0)))


@pytest.mark.parametrize("value", [-1.0, 1.000001, float("nan"), float("inf")])
def test_quality_rejects_invalid_unit_values(value: float) -> None:
    with pytest.raises(ValueError):
        bounded_quality(value, "unit_interval")


def test_angular_affinity_has_expected_geometry() -> None:
    e1 = np.array([1.0, 0.0])
    e2 = np.array([0.0, 1.0])
    assert math.isclose(angular_affinity(e1, e1), 1.0)
    assert math.isclose(angular_affinity(e1, e2), 0.5)
    assert math.isclose(angular_affinity(e1, -e1), 0.0)


@pytest.mark.parametrize("left, right", [(np.zeros(2), np.ones(2)), (np.ones(2), np.ones(3))])
def test_angular_affinity_rejects_zero_or_mismatched_vectors(left: np.ndarray, right: np.ndarray) -> None:
    with pytest.raises(ValueError):
        angular_affinity(left, right)


def test_diamond_hash_is_canonical_under_input_shuffle() -> None:
    first = _diamond()
    shuffled = FrozenDAG.build(
        ["t", "y", "r2", "x", "r1"],
        [("y", "t"), ("r2", "y"), ("x", "t"), ("r1", "y"), ("r2", "x"), ("r1", "x")],
        edge_weights={
            ("r2", "y"): 4,
            ("r1", "x"): 1,
            ("x", "t"): 1,
            ("r1", "y"): 3,
            ("r2", "x"): 2,
            ("y", "t"): 1,
        },
        root_mass=[0.0, 0.0, 0.6, 0.0, 0.4],
        layers=[["r2", "r1"], ["y", "x"], ["t"]],
    )
    assert first.graph_hash == shuffled.graph_hash
    assert first.edges == shuffled.edges


def test_dag_rejects_cycles_and_unknown_edges() -> None:
    with pytest.raises(ValueError):
        FrozenDAG.build(["a", "b"], [("a", "b"), ("b", "a")])
    with pytest.raises(ValueError):
        FrozenDAG.build(["a", "b"], [("a", "c")])


def test_diamond_transition_rows_are_normalized() -> None:
    measure = propagate(_diamond())
    assert math.isclose(sum(measure.transition["r1"].values()), 1.0)
    assert math.isclose(sum(measure.transition["r2"].values()), 1.0)
    assert measure.transition["x"] == {"t": 1.0}


def test_diamond_access_mass_and_parent_posteriors() -> None:
    measure = propagate(_diamond())
    assert np.isclose(measure.h["r1"], 0.4)
    assert np.isclose(measure.h["r2"], 0.6)
    assert np.isclose(measure.h["x"], 0.3)
    assert np.isclose(measure.h["y"], 0.7)
    assert np.isclose(measure.h["t"], 1.0)
    assert np.isclose(measure.gamma["x"]["r1"], 1.0 / 3.0)
    assert np.isclose(measure.gamma["x"]["r2"], 2.0 / 3.0)
    assert np.isclose(measure.gamma["t"]["x"], 0.3)
    assert np.isclose(measure.gamma["t"]["y"], 0.7)


def test_diamond_terminal_mass_is_conserved_and_h_can_exceed_one() -> None:
    measure = propagate(_diamond())
    assert np.isclose(measure.termination_quality, 1.0)
    assert np.isclose(sum(measure.h.values()), 3.0)
    terminal_column = measure.w[:, measure.graph.memory_ids.index("t")]
    root_positions = [measure.graph.memory_ids.index(identifier) for identifier in ("r1", "r2")]
    assert np.isclose(terminal_column[root_positions].sum(), 1.0)


def test_nonroot_prior_mass_is_rejected() -> None:
    graph = FrozenDAG.build(["r", "t"], [("r", "t")], edge_weights={("r", "t"): 1}, root_mass={"r": 0.5, "t": 0.5})
    with pytest.raises(ValueError):
        propagate(graph)


def test_thin_svd_shrink_matches_explicit_inverse_sqrt() -> None:
    vector = np.array([0.3, 0.8, -0.2])
    ancestors = [np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 1.0])]
    weights = [0.4, 1.7]
    actual = thin_svd_shrink(vector, ancestors, weights)
    b = np.column_stack([math.sqrt(w) * a for w, a in zip(weights, ancestors)])
    scatter = b @ b.T
    eigenvalues, eigenvectors = np.linalg.eigh(np.eye(3) + scatter)
    expected = eigenvectors @ np.diag(1.0 / np.sqrt(eigenvalues)) @ eigenvectors.T @ vector
    assert np.allclose(actual, expected, atol=1e-10)


def test_thin_svd_is_order_invariant_and_has_identity_degenerate_case() -> None:
    vector = np.array([1.0, -2.0])
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert np.allclose(thin_svd_shrink(vector, []), vector)
    assert np.allclose(thin_svd_shrink(vector, [a, b]), thin_svd_shrink(vector, [b, a]))
    # A hard subtraction is a different operator and may erase the signal.
    assert not np.allclose(thin_svd_shrink(vector, [vector]), vector - vector)


def test_r1_path_degenerates_to_quality_scaled_unit_vector() -> None:
    vector = np.array([3.0, 4.0])
    feature = semantic_atom(0.25, vector)
    assert np.allclose(feature, 0.5 * vector / np.linalg.norm(vector))


def test_semantic_atom_is_psd_and_quality_bounded() -> None:
    feature = semantic_atom(0.81, np.array([1.0, 0.0]), [np.array([0.0, 1.0])])
    atom = information_atom(1.0, feature)
    eigenvalues = np.linalg.eigvalsh(atom.matrix if hasattr(atom, "matrix") else np.outer(atom, atom))
    assert np.min(eigenvalues) >= -1e-12
    with pytest.raises(ValueError):
        semantic_atom(1.1, np.ones(2))
    with pytest.raises(ValueError):
        semantic_atom(0.5, np.zeros(2))


def test_logdet_empty_and_additive_value() -> None:
    f1 = np.array([1.0, 0.0])
    f2 = np.array([0.0, 2.0])
    assert logdet_value([]) == 0.0
    expected = math.log(2.0) + math.log(5.0)
    assert np.isclose(logdet_value([f1, f2]), expected)


def test_marginal_equals_logdet_difference() -> None:
    selected = [np.array([1.0, 0.0]), np.array([0.2, 0.8])]
    candidate = np.array([0.3, -0.4])
    assert np.isclose(marginal(candidate, selected), logdet_value(selected + [candidate]) - logdet_value(selected))


def test_logdet_marginals_have_diminishing_returns() -> None:
    a = np.array([1.0, 0.0])
    b = np.array([0.7, 0.7])
    c = np.array([0.0, 1.0])
    assert marginal(c, [a, b]) <= marginal(c, [a]) + 1e-12


def test_eager_greedy_is_deterministic_and_uses_id_ties() -> None:
    atoms = {"z": np.array([1.0, 0.0]), "a": np.array([1.0, 0.0]), "m": np.array([0.0, 1.0])}
    selected, margins = greedy(atoms, k=2)
    assert selected == ["a", "m"]
    assert len(margins) == 2


def test_lazy_and_eager_ids_and_margins_match() -> None:
    atoms = {
        "a": np.array([1.0, 0.0]),
        "b": np.array([0.8, 0.2]),
        "c": np.array([0.0, 1.0]),
        "d": np.array([-0.2, 0.9]),
    }
    eager_ids, eager_margins = greedy(atoms, k=3)
    lazy_ids, lazy_margins, diagnostics = lazy_greedy(atoms, {key: 1.0 for key in atoms}, k=3)
    assert lazy_ids == eager_ids
    assert np.allclose(lazy_margins, eager_margins)
    assert diagnostics["complete"] is True


def test_lazy_upper_bounds_and_materialization_are_auditable() -> None:
    atoms = {"root": np.array([math.sqrt(0.1), 0.0]), "leaf": np.array([0.0, math.sqrt(0.9)])}
    selected, _margins, diagnostics = lazy_greedy(atoms, {"root": 0.2, "leaf": 0.9}, k=1)
    assert selected == ["leaf"]
    assert diagnostics["upper_bounds"]["leaf"] == math.log1p(0.9)
    assert diagnostics["materialized"] >= 1


def test_high_quality_leaf_can_defeat_low_quality_root() -> None:
    atoms = {
        "root": semantic_atom(0.1, np.array([1.0, 0.0])),
        "leaf": semantic_atom(0.95, np.array([0.0, 1.0])),
    }
    selected, _ = greedy(atoms, k=1)
    assert selected == ["leaf"]


def test_hard_difference_and_path_shuffle_are_distinguishable() -> None:
    candidate = np.array([1.0, 1.0]) / math.sqrt(2.0)
    ancestor = np.array([1.0, 1.0]) / math.sqrt(2.0)
    other = np.array([1.0, -1.0]) / math.sqrt(2.0)
    conditioned = thin_svd_shrink(candidate, [ancestor])
    assert np.linalg.norm(conditioned) > 0.0
    assert not np.allclose(conditioned, candidate - ancestor)
    assert np.allclose(
        thin_svd_shrink(candidate, [ancestor, other]),
        thin_svd_shrink(candidate, [other, ancestor]),
    )


@pytest.mark.parametrize("bad_k", [True, 1.5, "not-an-int"])
def test_selector_rejects_boolean_fractional_and_text_k(bad_k: object) -> None:
    with pytest.raises(ValueError):
        greedy({"a": np.ones(2)}, k=bad_k)  # type: ignore[arg-type]


def test_duplicate_ids_nan_dimension_and_weight_boundaries_fail() -> None:
    with pytest.raises(ValueError):
        greedy({1: np.ones(2), "1": np.ones(2)})
    with pytest.raises(ValueError):
        greedy({"a": np.array([np.nan, 0.0])})
    with pytest.raises(ValueError):
        marginal(np.ones(2), [np.ones(3)])
    with pytest.raises(ValueError):
        FrozenDAG.build(["a", "b"], [("a", "b")], edge_weights={("a", "b"): -1.0})
