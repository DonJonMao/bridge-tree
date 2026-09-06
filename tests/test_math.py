import numpy as np

from bridgetree.math_utils import (
    factor_conditioned_innovation,
    logdet_marginal,
    logdet_value,
    path_conditioned_innovation,
    posterior_error,
)


def test_path_conditioned_feature_matches_eigendecomposition():
    vector = np.array([0.4, 0.8, 0.2])
    vector /= np.linalg.norm(vector)
    ancestors = [np.array([0.6, 0.0, 0.0]), np.array([0.1, 0.5, 0.0])]
    actual = path_conditioned_innovation(vector, 0.7, ancestors)
    matrix = np.eye(3) + sum(np.outer(item, item) for item in ancestors)
    values, basis = np.linalg.eigh(matrix)
    expected = basis @ np.diag(values**-0.5) @ basis.T @ (0.7 * vector)
    np.testing.assert_allclose(actual, expected, atol=1e-10)


def test_logdet_marginal_is_exact_difference():
    selected = [np.array([0.4, 0.1]), np.array([0.1, 0.5])]
    candidate = np.array([0.2, 0.7])
    expected = logdet_value(selected + [candidate]) - logdet_value(selected)
    assert np.isclose(logdet_marginal(candidate, selected), expected)


def test_posterior_error_uses_pdf_weighting():
    eps = [0.1, 0.2, 0.3]
    expected = (2 / 3) ** 2 * 0.1 + (2 / 3) * 0.2 + 0.3
    assert np.isclose(posterior_error(eps), expected)


def test_factor_conditioned_innovation_matches_dense_reference():
    rng = np.random.default_rng(89846)
    vector = rng.normal(size=7)
    ancestors = [rng.normal(size=7) for _ in range(4)]
    weights = rng.uniform(0.05, 0.9, size=4)
    actual = factor_conditioned_innovation(vector, 0.73, ancestors, weights)
    unit = [item / np.linalg.norm(item) for item in ancestors]
    B = np.column_stack(unit) * np.sqrt(weights)[None, :]
    dense = np.eye(7) + B @ B.T
    values, basis = np.linalg.eigh(dense)
    expected = np.sqrt(0.73) * basis @ np.diag(values ** -0.5) @ basis.T @ (vector / np.linalg.norm(vector))
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)
