import numpy as np

from bridgetree.baselines import cluster_prf, dense_retrieval, rfmem, rfmem_recollection, rfmem_route


def test_rfmem_router_matches_published_thresholds():
    assert rfmem_route([0.8, 0.7, 0.6])[0] == "fast"
    assert rfmem_route([0.1, 0.2, 0.3])[0] == "slow"


def test_required_vector_baselines_run_deterministically():
    ids = [f"m{i}" for i in range(8)]
    vectors = np.eye(8)
    query = np.array([1.0, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2])
    dense = dense_retrieval(ids, vectors, query, 3)
    recollection = rfmem_recollection(ids, vectors, query, 3, threshold=0.0)
    routed = rfmem(ids, vectors, query, 3)
    prf = cluster_prf(ids, vectors, query, 3)
    assert dense.selected_ids == dense_retrieval(ids, vectors, query, 3).selected_ids
    assert len(recollection.selected_ids) <= 3
    assert len(routed.selected_ids) <= 3
    assert len(prf.selected_ids) == 3
