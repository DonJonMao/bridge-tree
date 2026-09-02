import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from bridgetree.config import (
    AppConfig,
    EmbeddingConfig,
    EndpointConfig,
    GeneratorConfig,
    ModelsConfig,
    RetrievalConfig,
    RuntimeConfig,
)
from bridgetree.module_metrics import MODULE_NAMES, metric_value, module_metric_delta
from bridgetree.personamem import PersonaMemExample
from bridgetree.training import (
    SearchSpace,
    SplitProtocol,
    TrainingExperimentConfig,
    TrainingSchedule,
    run_training_experiment,
    split_examples_by_persona,
)


class DeterministicEmbedder:
    def _vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = np.asarray([byte / 127.5 - 1.0 for byte in digest[:8]], dtype=np.float64)
        return vector / np.linalg.norm(vector)

    def encode(self, texts):
        return np.asarray([self._vector(text) for text in texts], dtype=np.float64)

    def encode_query(self, text):
        return self._vector("query:" + text)


def _examples(count: int = 6) -> list[PersonaMemExample]:
    examples = []
    for index in range(count):
        question_id = f"q{index}"
        examples.append(
            PersonaMemExample(
                persona_id=f"p{index}",
                question_id=question_id,
                question_type="preference",
                topic="food",
                query=f"What does persona {index} prefer?",
                correct_answer="(a)",
                all_options="['(a)', '(b)']",
                shared_context_id=f"c{index}",
                end_index=7,
                messages=[
                    {"role": "system", "content": f"Persona profile {index}"},
                    {"role": "user", "content": f"I liked apples {index}."},
                    {"role": "assistant", "content": "Noted."},
                    {"role": "user", "content": f"I now prefer pears {index}."},
                    {"role": "assistant", "content": "I will remember."},
                    {"role": "user", "content": f"Avoid bananas {index}."},
                    {"role": "assistant", "content": "Understood."},
                ],
            )
        )
    return examples


def _app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        seed=7,
        retrieval=RetrievalConfig(first_hop_width=2, branch_width=2, context_size=2, search_budget=5),
        models=ModelsConfig(
            embedding=EmbeddingConfig(endpoint="unused", model="fake"),
            reranker=EndpointConfig(endpoint="unused"),
            generator=GeneratorConfig(endpoint="unused", model="unused"),
        ),
        runtime=RuntimeConfig(cache_dir=str(tmp_path / "cache"), output_dir=str(tmp_path / "runs")),
    )


def test_persona_split_is_deterministic_and_disjoint():
    examples = _examples(10)
    first = split_examples_by_persona(examples, SplitProtocol(), seed=19)
    second = split_examples_by_persona(list(reversed(examples)), SplitProtocol(), seed=19)

    assert first.train_personas == second.train_personas
    assert first.validation_personas == second.validation_personas
    assert first.test_personas == second.test_personas
    persona_sets = [set(first.train_personas), set(first.validation_personas), set(first.test_personas)]
    assert not persona_sets[0] & persona_sets[1]
    assert not persona_sets[0] & persona_sets[2]
    assert not persona_sets[1] & persona_sets[2]
    assert set.union(*persona_sets) == {example.persona_id for example in examples}


def test_internal_diagnostic_cannot_be_a_tuning_objective():
    with pytest.raises(ValueError, match="external outcome"):
        TrainingExperimentConfig(objective_metric="selection.logdet_value").validate()


def test_training_run_writes_periodic_and_decoupled_metrics(tmp_path):
    gold_path = tmp_path / "bridge_gold.jsonl"
    gold_path.write_text(
        "".join(
            json.dumps({"question_id": f"q{index}", "gold_memory_ids": [f"q{index}:m00001"]}) + "\n"
            for index in range(6)
        ),
        encoding="utf-8",
    )
    training_config = TrainingExperimentConfig(
        seed=11,
        schedule=TrainingSchedule(periodic_eval_every=2, periodic_eval_queries=1),
        search_space=SearchSpace(initial_width=(2,), branch_width=(2,), search_budget=(5,)),
        diagnostic_methods=("bridgetree", "ablation_no_cluster"),
        main_table_methods=("bridgetree", "ablation_no_cluster"),
        objective_metric="outcome.recall_at_k",
        bridge_gold_path=str(gold_path),
        output_dir=str(tmp_path / "training"),
    )
    summary = run_training_experiment(
        _app_config(tmp_path),
        training_config,
        DeterministicEmbedder(),
        examples=_examples(),
    )

    run_dir = Path(summary["run_dir"])
    assert summary["optimization_kind"] == "training_free_configuration_tuning"
    assert summary["selection_status"] == "selected_on_external_validation_outcome"
    assert summary["trial_count"] == 1
    assert (run_dir / "best_config.json").is_file()
    assert (run_dir / "final_summary.json").is_file()
    assert (run_dir / "metrics.csv").is_file()
    assert (run_dir / "module_effects.jsonl").is_file()
    assert all((run_dir / "modules" / f"{module}.jsonl").is_file() for module in MODULE_NAMES)

    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    phases = {event["phase"] for event in events}
    assert {"train_progress", "validation_probe", "validation", "test"} <= phases
    assert any(event["phase"] == "validation_probe" and event["step"] == 2 for event in events)
    assert any(event["phase"] == "test" and event["method"] == "ablation_no_cluster" for event in events)

    test_metrics = summary["test_metrics"]
    assert metric_value(test_metrics["bridgetree"], "selection.selected_count") > 0
    delta = module_metric_delta(test_metrics["bridgetree"], test_metrics["ablation_no_cluster"])
    assert set(delta) == set(MODULE_NAMES)


def test_tuning_without_external_outcome_does_not_select_or_read_test(tmp_path):
    config = TrainingExperimentConfig(
        seed=11,
        schedule=TrainingSchedule(periodic_eval_every=2, periodic_eval_queries=1),
        search_space=SearchSpace(initial_width=(2,), branch_width=(2,), search_budget=(5,)),
        diagnostic_methods=("bridgetree",),
        main_table_methods=("bridgetree",),
        output_dir=str(tmp_path / "training"),
    )
    summary = run_training_experiment(
        _app_config(tmp_path),
        config,
        DeterministicEmbedder(),
        examples=_examples(),
    )
    run_dir = Path(summary["run_dir"])
    assert summary["best_trial"] is None
    assert summary["test_metrics"] == {}
    assert not (run_dir / "best_config.json").exists()
    assert (run_dir / "pareto_frontier.json").is_file()
    phases = {json.loads(line)["phase"] for line in (run_dir / "events.jsonl").read_text().splitlines()}
    assert "validation_probe" in phases
    assert "validation" in phases
    assert "test" not in phases


def test_selected_tuning_generates_for_every_final_main_table_method(tmp_path, monkeypatch):
    calls = []

    def fake_answer(self, query, memories, answer_options=""):
        calls.append((query, tuple(memory.memory_id for memory in memories), answer_options))
        return "(a)"

    monkeypatch.setattr("bridgetree.training.GeneratorClient.answer", fake_answer)
    config = TrainingExperimentConfig(
        seed=11,
        schedule=TrainingSchedule(periodic_eval_every=2, periodic_eval_queries=1),
        search_space=SearchSpace(initial_width=(2,), branch_width=(2,), search_budget=(5,)),
        diagnostic_methods=("bridgetree", "ablation_no_cluster"),
        main_table_methods=("dense", "bridgetree"),
        validation_generate=True,
        final_generate=True,
        output_dir=str(tmp_path / "training"),
    )
    summary = run_training_experiment(
        _app_config(tmp_path),
        config,
        DeterministicEmbedder(),
        examples=_examples(),
    )
    for method in config.main_table_methods:
        assert metric_value(summary["test_metrics"][method], "outcome.answer_accuracy") == 1.0
        assert metric_value(summary["test_metrics"][method], "outcome.parse_failure_rate") == 0.0
    assert len(calls) >= len(config.main_table_methods)
