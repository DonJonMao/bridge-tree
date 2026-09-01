import numpy as np

from bridgetree.math_utils import logdet_marginal, logdet_value, path_conditioned_innovation, posterior_error


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
