import numpy as np

from bridgetree.config import (
    AppConfig,
    EmbeddingConfig,
    EndpointConfig,
    GeneratorConfig,
    ModelsConfig,
    RetrievalConfig,
)
from bridgetree.experiment import METHODS, retrieve_method
from bridgetree.personamem import PersonaMemExample
from bridgetree.types import Memory


class FakeReranker:
    def rerank(self, query, documents, top_n):
        from bridgetree.clients import RerankItem

        return [RerankItem(index=index, score=1.0 - index / 100) for index in range(min(top_n, len(documents)))]


def test_every_required_method_runs_through_the_shared_interface():
    config = AppConfig(
        seed=42,
        retrieval=RetrievalConfig(first_hop_width=4, branch_width=3, context_size=3, search_budget=8),
        models=ModelsConfig(
            embedding=EmbeddingConfig(endpoint="embedding", model="e"),
            reranker=EndpointConfig(endpoint="rerank"),
            generator=GeneratorConfig(endpoint="chat", model="g"),
        ),
    )
    example = PersonaMemExample("p", "q", "type", "topic", "query", "(a)", "['(a)']", "ctx", 0, [])
    memories = [Memory(f"m{i}", f"memory {i}", float(i), f"s{i}") for i in range(9)]
    rng = np.random.default_rng(3)
    vectors = rng.normal(size=(9, 5))
    query = rng.normal(size=5)
    for method in METHODS:
        selected_ids, selected, diagnostics, _bridge = retrieve_method(
            method,
            config,
            example,
            memories,
            query,
            vectors,
            reranker=FakeReranker() if method == "dense_rerank" else None,
        )
        assert len(selected_ids) <= config.retrieval.context_size
        assert [memory.timestamp for memory in selected] == sorted(memory.timestamp for memory in selected)
        assert isinstance(diagnostics, dict)
