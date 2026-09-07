from dataclasses import replace

import pytest

from bridgetree.clients import GenerationCache, build_context_plan
from bridgetree.config import GeneratorConfig, load_config
from bridgetree.experiment import run_semantic_matrix
from bridgetree.offline_validation import OfflineDeterministicEmbedder
from bridgetree.personamem import PersonaMemExample
from bridgetree.types import Memory


def _example(question_id: str) -> PersonaMemExample:
    return PersonaMemExample(
        persona_id="persona",
        question_id=question_id,
        question_type="preference",
        topic="test",
        query=f"query {question_id}",
        correct_answer="(a)",
        all_options="['(a)', '(b)']",
        shared_context_id=question_id,
        end_index=2,
        messages=(
            {"role": "user", "content": "memory one"},
            {"role": "assistant", "content": "memory two"},
        ),
    )


def test_real_personamem_matrix_requires_manifest_before_embedding(tmp_path):
    config = load_config("configs/default.yaml")
    config = replace(config, runtime=replace(config.runtime, output_dir=str(tmp_path)))

    class CountingEmbedder(OfflineDeterministicEmbedder):
        calls = 0

        def encode_query(self, text):
            self.calls += 1
            return super().encode_query(text)

    embedder = CountingEmbedder()
    with pytest.raises(ValueError, match="persisted protocol manifest"):
        run_semantic_matrix(
            config,
            embedder,
            examples=[_example("q")],
            rows="S0",
            baseline="none",
            output_dir=tmp_path,
        )
    assert embedder.calls == 0


def test_generation_cache_ignores_greedy_order_when_request_is_identical():
    class Client:
        def __init__(self):
            self.config = GeneratorConfig(
                endpoint="http://generator",
                model="model",
                max_tokens=8,
                context_token_budget=10_000,
            )
            self.calls = 0

        def answer_plan(self, _plan):
            self.calls += 1
            return "(a)"

    client = Client()
    cache = GenerationCache()
    memories = [Memory("a", "A", 1.0, "s"), Memory("b", "B", 2.0, "s")]
    first = build_context_plan(
        "q", memories, "['(a)', '(b)']", token_budget=10_000,
        selected_ids=["a", "b"], generator_config=client.config,
    )
    second = build_context_plan(
        "q", memories, "['(a)', '(b)']", token_budget=10_000,
        selected_ids=["b", "a"], generator_config=client.config,
    )
    assert cache.answer_plan(client, first) == ("(a)", False)
    assert cache.answer_plan(client, second) == ("(a)", True)
    assert client.calls == 1


def test_matrix_failures_remain_in_end_to_end_denominator(tmp_path, monkeypatch):
    import bridgetree.experiment as experiment

    config = load_config("configs/default.yaml")
    config = replace(
        config,
        runtime=replace(config.runtime, output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")),
    )

    class FailingOnceGenerator:
        calls = 0

        def __init__(self, generator_config):
            self.config = generator_config

        def answer_plan(self, _plan):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("injected generation failure")
            return "(a)"

        def answer(self, _query, _memories, _options=""):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("injected generation failure")
            return "(a)"

    monkeypatch.setattr(experiment, "GeneratorClient", FailingOnceGenerator)
    result = run_semantic_matrix(
        config,
        OfflineDeterministicEmbedder(),
        examples=[_example("q1"), _example("q2")],
        synthetic=True,
        rows="S0",
        baseline="none",
        generate=True,
        output_dir=tmp_path,
    )
    summary = result["summary"]["architectures"]["S0"]
    assert summary["queries"] == 2
    assert summary["failed_queries"] == 1
    assert summary["end_to_end_micro_accuracy"] == pytest.approx(0.5)
    assert summary["successful_response_accuracy"] == pytest.approx(1.0)
    assert summary["status"] == "incomplete"
