import numpy as np

from bridgetree.clustering import cluster_siblings, spherical_kmeans
from bridgetree.math_utils import effective_rank


def test_effective_rank_collapses_parallel_directions():
    parallel = np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    assert np.isclose(effective_rank(parallel), 1.0)
    orthogonal = np.eye(3)
    assert np.isclose(effective_rank(orthogonal), 3.0)


def test_weighted_probe_and_radius_are_well_formed():
    vectors = np.array([[1.0, 0.0], [0.8, 0.6]])
    clusters = cluster_siblings(vectors, [0.9, 0.3])
    assert len(clusters) >= 1
    for cluster in clusters:
        assert np.isclose(np.linalg.norm(cluster.probe), 1.0)
        assert 0.0 <= cluster.radius_radians <= np.pi


def test_no_compression_produces_one_probe_per_memory():
    vectors = np.eye(3)
    clusters = cluster_siblings(vectors, [1.0, 0.8, 0.7], disable_compression=True)
    assert len(clusters) == 3
    assert all(len(cluster.member_positions) == 1 for cluster in clusters)


def test_empty_cluster_reseeding_uses_distinct_samples():
    vectors = np.asarray([[1.0, 0.0]] * 4)
    labels = spherical_kmeans(vectors, count=4, max_iterations=2)
    assert set(labels) == {0, 1, 2, 3}


def test_fixed_and_effective_rank_modes_honor_cluster_limits():
    vectors = np.eye(6)
    fixed = cluster_siblings(vectors, [1.0] * 6, mode="fixed", fixed_count=3)
    effective = cluster_siblings(vectors, [1.0] * 6, mode="effective_rank", max_clusters=2)
    assert len(fixed) == 3
    assert len(effective) == 2
    minimum = cluster_siblings(vectors, [1.0] * 6, mode="fixed", fixed_count=3, min_cluster_size=2)
    assert all(len(cluster.member_positions) >= 2 for cluster in minimum)
