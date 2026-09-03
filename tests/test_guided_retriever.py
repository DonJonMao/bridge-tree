from dataclasses import replace

import numpy as np
import pytest

from bridgetree.budget import CostTracker, SearchBudget
from bridgetree.clients import RerankItem
from bridgetree.config import (
    AppConfig,
    BridgeRerankConfig,
    EmbeddingConfig,
    GeneratorConfig,
    ModelsConfig,
    RerankerConfig,
    RetrievalConfig,
)
from bridgetree.guided_retriever import RerankerGuidedBridgeRetriever
from bridgetree.index import ExactInnerProductIndex
from bridgetree.personamem import PersonaMemExample
from bridgetree.types import Memory


class SemanticFakeReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, query, documents, top_n):
        self.calls.append((query, list(documents), top_n))
        scores = []
        for index, document in enumerate(documents):
            if "Candidate interaction:" in document:
                score = -0.2 if "m2 complementary" in document else -0.9
            elif "m2 complementary" in document:
                score = 1.0
            elif "m1 anchor" in document:
                score = 0.9
            elif "m3 topical noise" in document:
                score = 0.2
            else:
                score = 0.1
            scores.append(RerankItem(index, score))
        return sorted(scores, key=lambda item: (-item.score, item.index))[:top_n]


class BatchBridgeEmbedder:
    def __init__(self, vector):
        self.vector = np.asarray(vector, dtype=np.float64)
        self.calls = []

    def __call__(self, texts, *, instruction, purpose):
        self.calls.append((list(texts), instruction, purpose))
        return np.asarray([self.vector for _text in texts])


def _example():
    return PersonaMemExample(
        "p",
        "q",
        "preference",
        "activity",
        "Which activity fits me?",
        "(b)",
        "['(a) noise', '(b) complement']",
        "ctx",
        4,
        [],
    )


def _config(**bridge_changes):
    bridge = replace(
        BridgeRerankConfig(
            dense_pool_width=2,
            anchor_width=2,
            expand_branch_count=1,
            branch_overfetch_width=2,
            branch_keep_width=1,
        ),
        **bridge_changes,
    )
    return AppConfig(
        seed=42,
        retrieval=RetrievalConfig(
            initial_width=2,
            branch_width=2,
            context_size=2,
            search_budget=4,
            cluster_count=max(1, bridge.expand_branch_count),
            selection_mode="rho_logdet",
        ),
        models=ModelsConfig(
            embedding=EmbeddingConfig(endpoint="embedding"),
            reranker=RerankerConfig(endpoint="rerank"),
            generator=GeneratorConfig(endpoint="generator"),
        ),
        bridge_rerank=bridge,
    )


def _bank():
    memories = [
        Memory("m1", "m1 anchor", 1.0, "s1"),
        Memory("d1", "dense distractor", 2.0, "s2"),
        Memory("m2", "m2 complementary", 3.0, "s3"),
        Memory("m3", "m3 topical noise", 4.0, "s4"),
    ]
    vectors = np.asarray(
        [
            [1.0, 0.1, 0.0],
            [0.8, -0.6, 0.0],
            [0.0, 0.9, 0.435],
            [0.0, 1.0, 0.0],
        ]
    )
    return memories, vectors, np.asarray([1.0, 0.0, 0.0])


def _run(mode, **bridge_changes):
    config = _config(**bridge_changes)
    memories, vectors, query = _bank()
    embedder = BatchBridgeEmbedder([0.0, 1.0, 0.0])
    reranker = SemanticFakeReranker()
    tracker = CostTracker(SearchBudget(max_unique_nodes=4))
    selected_ids, _selected, pool = RerankerGuidedBridgeRetriever(config).retrieve(
        _example(),
        memories,
        query,
        vectors,
        embed_query_batch=embedder,
        reranker=reranker,
        rerank_cache=None,
        index=ExactInnerProductIndex([memory.memory_id for memory in memories], vectors),
        cost_tracker=tracker,
        mode=mode,
    )
    return selected_ids, pool, embedder, tracker


def test_guided_pathfilter_finds_complement_and_suppresses_topical_noise():
    selected_ids, pool, embedder, tracker = _run("bridgetree_guided_pathfilter")

    assert pool.dense_ids == ["m1", "d1"]
    assert set(pool.dense_ids) <= set(pool.candidate_ids)
    assert pool.bridge_raw_ids == ["m3", "m2"]
    assert pool.bridge_kept_ids == ["m2"]
    assert not set(pool.bridge_raw_ids) & set(pool.dense_ids)
    assert pool.parent_by_bridge_id["m2"] == "m1"
    assert selected_ids == ["m2", "m1"]
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0][0]) == 1
    assert tracker.rerank_calls == 3
    assert tracker.bridge_embedding_calls == 1


def test_guided_without_pathfilter_keeps_ann_top_n_without_a_threshold():
    selected_ids, pool, _embedder, tracker = _run("bridgetree_guided_rerank")

    assert pool.bridge_kept_ids == ["m3"]
    assert "m3" in selected_ids
    assert tracker.rerank_calls == 2


def test_pathfilter_method_honors_disabled_path_filter():
    selected_ids, pool, _embedder, tracker = _run(
        "bridgetree_guided_pathfilter",
        path_filter=False,
    )

    assert pool.bridge_kept_ids == ["m3"]
    assert "m3" in selected_ids
    assert tracker.rerank_calls == 2


def test_guided_rerank_rejects_certificate_stopping():
    config = _config()
    config = replace(config, retrieval=replace(config.retrieval, stop_mode="certificate_or_budget"))
    memories, vectors, query = _bank()

    with pytest.raises(ValueError, match="cannot use certificate_or_budget"):
        RerankerGuidedBridgeRetriever(config).retrieve(
            _example(),
            memories,
            query,
            vectors,
            embed_query_batch=BatchBridgeEmbedder([0.0, 1.0, 0.0]),
            reranker=SemanticFakeReranker(),
            rerank_cache=None,
            index=ExactInnerProductIndex([memory.memory_id for memory in memories], vectors),
            cost_tracker=CostTracker(SearchBudget(max_unique_nodes=4)),
            mode="bridgetree_guided_rerank",
        )


def test_two_branch_queries_are_encoded_in_one_batch():
    config = _config(
        dense_pool_width=4,
        anchor_width=4,
        expand_branch_count=2,
        branch_overfetch_width=1,
        branch_keep_width=1,
    )
    config = replace(config, retrieval=replace(config.retrieval, cluster_count=2))
    memories, vectors, query = _bank()
    extra_memories = [Memory("x1", "extra one", 5.0, "s5"), Memory("x2", "extra two", 6.0, "s6")]
    extra_vectors = np.asarray([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]])
    memories += extra_memories
    vectors = np.vstack([vectors, extra_vectors])
    embedder = BatchBridgeEmbedder([0.0, 0.0, 1.0])
    tracker = CostTracker(SearchBudget(max_unique_nodes=6))

    RerankerGuidedBridgeRetriever(config).retrieve(
        _example(),
        memories,
        query,
        vectors,
        embed_query_batch=embedder,
        reranker=SemanticFakeReranker(),
        rerank_cache=None,
        index=ExactInnerProductIndex([memory.memory_id for memory in memories], vectors),
        cost_tracker=tracker,
        mode="bridgetree_guided_rerank",
    )

    assert len(embedder.calls) == 1
    assert len(embedder.calls[0][0]) == 2
    assert tracker.bridge_embedding_calls == 1
    assert tracker.bridge_embedding_queries == 2
