import csv
import hashlib
import json

import numpy as np

from bridgetree.config import (
    AppConfig,
    DataConfig,
    EmbeddingConfig,
    EndpointConfig,
    GeneratorConfig,
    ModelsConfig,
    RetrievalConfig,
    RuntimeConfig,
)
from bridgetree.experiment import METHODS, IndexCache, retrieve_method, run_personamem_experiment
from bridgetree.personamem import PersonaMemExample
from bridgetree.types import Memory


class FakeReranker:
    def rerank(self, query, documents, top_n):
        from bridgetree.clients import RerankItem

        return [RerankItem(index=index, score=1.0 - index / 100) for index in range(min(top_n, len(documents)))]


class FakeEmbedder:
    def _one(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        vector = np.asarray([value / 127.5 - 1.0 for value in digest[:8]])
        return vector / np.linalg.norm(vector)

    def encode(self, texts):
        return np.asarray([self._one(text) for text in texts])

    def encode_query(self, text):
        return self._one("query:" + text)


def test_index_cache_reuses_identical_context_cut_and_embedding_fingerprint():
    cache = IndexCache()
    ids = ["a", "b"]
    vectors = np.eye(2)
    first, _build_ms, first_hit = cache.get("ctx:2", "embed", "exact", ids, vectors, 4)
    second, second_build_ms, second_hit = cache.get("ctx:2", "embed", "exact", ["x", "y"], vectors, 4)
    assert not first_hit
    assert second_hit
    assert first is not second
    np.testing.assert_array_equal(first.vectors, second.vectors)
    assert second_build_ms == 0.0


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


def test_offline_run_saves_resolved_config_manifest_and_layered_metrics(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    messages = [
        {"role": "system", "content": "persona"},
        {"role": "user", "content": "likes tea"},
        {"role": "assistant", "content": "noted"},
        {"role": "user", "content": "now likes coffee"},
        {"role": "assistant", "content": "updated"},
    ]
    (raw / "shared_contexts_32k.jsonl").write_text(json.dumps({"ctx": messages}) + "\n", encoding="utf-8")
    with (raw / "questions_32k.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "persona_id",
            "question_id",
            "question_type",
            "topic",
            "user_question_or_message",
            "correct_answer",
            "all_options",
            "shared_context_id",
            "end_index_in_shared_context",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "persona_id": "p",
                "question_id": "q",
                "question_type": "preference",
                "topic": "drink",
                "user_question_or_message": "what is preferred?",
                "correct_answer": "(a)",
                "all_options": "['(a) coffee', '(b) tea']",
                "shared_context_id": "ctx",
                "end_index_in_shared_context": 5,
            }
        )
    config = AppConfig(
        seed=17,
        retrieval=RetrievalConfig(initial_width=2, branch_width=1, context_size=2, search_budget=3),
        models=ModelsConfig(
            embedding=EmbeddingConfig(endpoint="unused", model="fake"),
            reranker=EndpointConfig(endpoint="unused"),
            generator=GeneratorConfig(endpoint="unused", model="unused"),
        ),
        data=DataConfig(raw_dir=str(raw)),
        runtime=RuntimeConfig(cache_dir=str(tmp_path / "cache"), output_dir=str(tmp_path / "runs")),
    )
    result = run_personamem_experiment(config, "bridgetree", FakeEmbedder(), limit=1, generate=False)
    run_dir = tmp_path / "runs" / result["run_dir"].split("/")[-1]
    resolved = json.loads((run_dir / "resolved_config.json").read_text())
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    prediction = json.loads((run_dir / "predictions.jsonl").read_text())
    assert resolved["app_config_hash"] == config.config_hash()
    assert resolved["config"]["execution"]["generate"] is False
    assert manifest["seed"] == 17
    assert manifest["prompt_hash"]
    assert (run_dir / "failures.jsonl").read_text() == ""
    assert set(("outcome", "cost", "diagnostic")) <= set(prediction)
    assert prediction["cost"]["ann_calls_diagnostic"] == 0
    assert prediction["diagnostic"]["tree_semantics"] == "deterministic_first_arrival"
