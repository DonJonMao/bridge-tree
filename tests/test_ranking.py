import json

from bridgetree.clients import RerankItem
from bridgetree.personamem import PersonaMemExample
from bridgetree.ranking import (
    RerankCache,
    build_path_filter_query,
    build_personamem_rank_query,
    format_memory_document,
    stable_union,
)
from bridgetree.types import Memory


def _example() -> PersonaMemExample:
    return PersonaMemExample(
        persona_id="p",
        question_id="q",
        question_type="preference",
        topic="drink",
        query="What should I drink?",
        correct_answer="(b)",
        all_options="['(a) tea', '(b) coffee']",
        shared_context_id="ctx",
        end_index=3,
        messages=[],
    )


def test_rank_query_contains_options_but_not_correct_answer_marker():
    query = build_personamem_rank_query(_example())

    assert "Current request:\nWhat should I drink?" in query
    assert "A. tea" in query
    assert "B. coffee" in query
    assert "(b)" not in query
    assert "correct_answer" not in query
    assert "Candidate answers" in build_path_filter_query(_example())


def test_memory_document_contains_numeric_time_metadata():
    memory = Memory(
        "m1",
        "User:\nI prefer coffee.",
        143.0,
        "source",
        {"roles": ["user", "assistant"]},
    )

    document = format_memory_document(memory, 181.0)

    assert "[Interaction index: 143 / 181]" in document
    assert "[Roles: user, assistant]" in document
    assert document.endswith("I prefer coffee.")
    assert format_memory_document(memory, 181.0, include_time_metadata=False) == memory.text


def test_rerank_cache_key_changes_with_instruction_or_document_order(tmp_path):
    cache = RerankCache(tmp_path, endpoint="rerank", model="model")

    assert cache.key_for("instruction one", ["a", "b"]) != cache.key_for("instruction two", ["a", "b"])
    assert cache.key_for("instruction one", ["a", "b"]) != cache.key_for("instruction one", ["b", "a"])

    items = [RerankItem(1, 0.9), RerankItem(0, 0.2)]
    cache.put("q", ["a", "b"], items)
    restored = cache.get("q", ["a", "b"])
    assert restored == items
    payload = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert len(payload["items"]) == 2


def test_rerank_cache_stores_full_ranking_independent_of_later_top_n(tmp_path):
    class Client:
        calls = 0

        def rerank_all(self, _query, documents):
            self.calls += 1
            return [RerankItem(index, float(index)) for index in reversed(range(len(documents)))]

    client = Client()
    cache = RerankCache(tmp_path, endpoint="rerank", model="model")

    first, first_hit, _elapsed = cache.rerank_all(client, "q", ["a", "b", "c"])
    second, second_hit, _elapsed = cache.rerank_all(client, "q", ["a", "b", "c"])

    assert not first_hit
    assert second_hit
    assert client.calls == 1
    assert first == second
    assert len(second) == 3


def test_stable_union_preserves_dense_order_and_deduplicates():
    assert stable_union(["d2", "d1"], ["d1", "b2", "b1"], ["b2"]) == ["d2", "d1", "b2", "b1"]
