import sys
from types import SimpleNamespace

import numpy as np

from bridgetree.baselines import cluster_prf, rfmem, rfmem_recollection
from bridgetree.budget import SearchBudget
from bridgetree.config import RetrievalConfig
from bridgetree.index import ExactInnerProductIndex, FaissInnerProductIndex
from bridgetree.retriever import BridgeTreeRetriever
from bridgetree.types import Memory


def _bank(count=20, dimension=8):
    rng = np.random.default_rng(123)
    ids = [f"m{index:03d}" for index in range(count)]
    vectors = rng.normal(size=(count, dimension))
    query = rng.normal(size=dimension)
    memories = [Memory(memory_id, memory_id, float(index), memory_id) for index, memory_id in enumerate(ids)]
    return ids, vectors, query, memories


def test_every_dynamic_method_obeys_the_same_ann_and_candidate_budget():
    ids, vectors, query, memories = _bank()
    budget = SearchBudget(max_unique_nodes=8, max_ann_calls=2, max_candidate_exposure=6)
    results = [
        rfmem_recollection(ids, vectors, query, 3, threshold=0.0, budget=budget),
        rfmem(ids, vectors, query, 3, budget=budget),
        cluster_prf(ids, vectors, query, 3, first_width=4, budget=budget),
    ]
    bridge_config = RetrievalConfig(
        initial_width=4,
        branch_width=2,
        context_size=3,
        search_budget=8,
        max_ann_calls=2,
        max_candidate_exposure=6,
    )
    bridge = BridgeTreeRetriever(bridge_config).retrieve("q", query, memories, vectors)
    costs = [result.cost for result in results] + [bridge.cost]
    assert all(cost.ann_calls_core <= 2 for cost in costs)
    assert all(cost.candidates_returned <= 6 for cost in costs)


def test_light_diagnostics_never_issue_an_extra_ann_call():
    _ids, vectors, query, memories = _bank(count=12)
    common = dict(initial_width=4, branch_width=2, context_size=3, search_budget=8)
    light = BridgeTreeRetriever(RetrievalConfig(**common, diagnostic_level="light")).retrieve(
        "q", query, memories, vectors
    )
    full = BridgeTreeRetriever(RetrievalConfig(**common, diagnostic_level="full")).retrieve(
        "q", query, memories, vectors
    )
    assert light.cost.ann_calls_diagnostic == 0
    assert full.cost.ann_calls_diagnostic > 0
    assert full.cost.diagnostic_ms >= 0.0


def test_exact_uses_float32_and_stable_tie_breaking():
    ids = ["z", "a", "b", "c"]
    vectors = np.asarray([[1, 0], [1, 0], [0.5, 0.5], [0, 1]], dtype=np.float64)
    index = ExactInnerProductIndex(ids, vectors)
    assert index.vectors.dtype == np.float32
    assert [memory_id for memory_id, _score in index.search(np.asarray([1, 0]), 2)] == ["a", "z"]


def test_faiss_matches_exact_without_requesting_the_full_bank(monkeypatch):
    class FakeFlatIP:
        def __init__(self, dimension):
            self.dimension = dimension
            self.vectors = None

        def add(self, vectors):
            self.vectors = vectors

        def search(self, queries, top_k):
            scores = queries @ self.vectors.T
            positions = np.argsort(-scores, axis=1, kind="stable")[:, :top_k]
            return np.take_along_axis(scores, positions, axis=1), positions

    monkeypatch.setitem(sys.modules, "faiss", SimpleNamespace(IndexFlatIP=FakeFlatIP))
    ids, vectors, query, _memories = _bank(count=100)
    exact = ExactInnerProductIndex(ids, vectors, exclusion_margin=5)
    faiss = FaissInnerProductIndex(ids, vectors, exclusion_margin=5)
    excluded = {"m000", "m001"}
    assert faiss.search(query, 3, exclude=excluded) == exact.search(query, 3, exclude=excluded)
    assert max(faiss.last_search_stats.backend_request_sizes) < len(ids)
