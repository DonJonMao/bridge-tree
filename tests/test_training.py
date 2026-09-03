import csv
import hashlib
import json
from dataclasses import replace
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
    load_config,
)
from bridgetree.module_metrics import MODULE_NAMES, metric_value, module_metric_delta
from bridgetree.personamem import PersonaMemExample
from bridgetree.run_audit import audit_tuning_run
from bridgetree.training import (
    EFFECT_FIRST_VALIDATION_METHODS,
    SearchSpace,
    SplitProtocol,
    TrainingEvaluator,
    TrainingExperimentConfig,
    TrainingMetricsWriter,
    _is_better,
    load_training_config,
    preflight_tuning,
    run_effect_first_validation,
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


def test_validation_point_estimate_beats_cost_even_when_paired_interval_overlaps():
    assert _is_better(
        0.70,
        (10.0, 100.0, 1000.0),
        0.66,
        (1.0, 10.0, 10.0),
        "max",
        [1.0, 0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0, 1.0],
    )
    assert not _is_better(
        0.69,
        (1.0, 1.0, 1.0),
        0.70,
        (10.0, 100.0, 1000.0),
        "max",
    )


def test_external_tuning_requires_strict_query_failure_handling():
    with pytest.raises(ValueError, match="fail_on_evaluation_error"):
        TrainingExperimentConfig(
            validation_generate=True,
            final_generate=True,
            fail_on_evaluation_error=False,
        ).validate()


def test_training_run_evaluates_each_trial_once_and_writes_decoupled_metrics(tmp_path):
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
    assert (run_dir / "progress.json").is_file()
    assert json.loads((run_dir / "run_status.json").read_text())["status"] == "completed"
    assert json.loads((run_dir / "progress.json").read_text())["status"] == "completed"
    assert not list(run_dir.glob("*.tmp"))
    assert (run_dir / "metrics.csv").is_file()
    assert (run_dir / "module_effects.jsonl").is_file()
    assert all((run_dir / "modules" / f"{module}.jsonl").is_file() for module in MODULE_NAMES)

    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    phases = {event["phase"] for event in events}
    assert phases == {"validation", "test"}
    assert not any(event["phase"] in {"train_progress", "validation_probe"} for event in events)
    assert any(event["phase"] == "test" and event["method"] == "ablation_no_cluster" for event in events)
    assert all(event["step"] == 0 for event in events)

    test_metrics = summary["test_metrics"]
    assert all(item["attempted_queries"] == item["successful_queries"] for item in test_metrics.values())
    assert all(item["failed_queries"] == 0 for item in test_metrics.values())
    assert metric_value(test_metrics["bridgetree"], "selection.selected_count") > 0
    delta = module_metric_delta(test_metrics["bridgetree"], test_metrics["ablation_no_cluster"])
    assert set(delta) == set(MODULE_NAMES)
    audit = audit_tuning_run(run_dir, raise_on_error=True)
    assert audit["status"] == "passed"
    assert audit["evidence"]["event_count"] == 4
    progress_path = run_dir / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress_path.write_text(json.dumps({**progress, "status": "running"}), encoding="utf-8")
    failed_audit = audit_tuning_run(run_dir)
    assert failed_audit["status"] == "failed"
    assert "progress.json is not completed" in failed_audit["errors"]


def test_tuning_without_external_outcome_does_not_select_or_read_test(tmp_path):
    config = TrainingExperimentConfig(
        seed=11,
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


def test_evaluate_set_reports_failures_without_changing_the_denominator(tmp_path, monkeypatch):
    writer = TrainingMetricsWriter(tmp_path / "metrics", keep_examples=False)
    evaluator = TrainingEvaluator(_app_config(tmp_path), DeterministicEmbedder(), writer, {})
    examples = _examples(3)

    def fake_evaluate_one(example, method, generate, context):
        if example.question_id == "q1":
            raise RuntimeError("injected failure")
        return {name: ({"answer_accuracy": 1.0} if name == "outcome" else {}) for name in MODULE_NAMES}

    monkeypatch.setattr(evaluator, "evaluate_one", fake_evaluate_one)
    summary = evaluator.evaluate_set(
        examples,
        "bridgetree",
        True,
        {"phase": "validation", "trial": 1, "step": 0},
        fail_on_error=False,
    )

    assert summary["attempted_queries"] == 3
    assert summary["successful_queries"] == 2
    assert summary["failed_queries"] == 1
    assert summary["failure_rate"] == pytest.approx(1 / 3)
    assert len((tmp_path / "metrics" / "failures.jsonl").read_text().splitlines()) == 1


def test_evaluate_set_aborts_formal_tuning_on_first_failed_query(tmp_path, monkeypatch):
    writer = TrainingMetricsWriter(tmp_path / "metrics", keep_examples=False)
    evaluator = TrainingEvaluator(_app_config(tmp_path), DeterministicEmbedder(), writer, {})

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(evaluator, "evaluate_one", fail)
    with pytest.raises(RuntimeError, match="formal tuning requires zero failed queries"):
        evaluator.evaluate_set(
            _examples(3),
            "bridgetree",
            True,
            {"phase": "validation", "trial": 1, "step": 0},
            fail_on_error=True,
        )
    assert len((tmp_path / "metrics" / "failures.jsonl").read_text().splitlines()) == 1
    status = json.loads((tmp_path / "metrics" / "run_status.json").read_text())
    assert status["status"] == "failed"
    assert status["failure_count"] == 1
    progress = json.loads((tmp_path / "metrics" / "progress.json").read_text())
    assert progress["status"] == "failed"
    assert progress["evaluation_index"] == 1


def test_full_32k_preflight_validates_complete_protocol_without_service_calls():
    report = preflight_tuning(
        load_config("configs/default.yaml"),
        load_training_config("configs/train.yaml"),
        check_services=False,
        require_full_32k=True,
    )

    assert report["status"] == "ready"
    assert report["data"]["split"] == "32k"
    assert report["data"]["questions"] == 589
    assert report["tuning"]["trial_count"] == 16
    assert report["tuning"]["objective_metric"] == "outcome.answer_accuracy"
    assert report["services"] == {"checked": False}


def test_full_32k_preflight_rejects_a_different_search_grid_before_starting():
    tuning = replace(
        load_training_config("configs/train.yaml"),
        search_space=SearchSpace(initial_width=(8, 12), branch_width=(4, 8), search_budget=(20, 44)),
    )
    with pytest.raises(ValueError, match="pinned 2x2x4 search space"):
        preflight_tuning(
            load_config("configs/default.yaml"),
            tuning,
            check_services=False,
            require_full_32k=True,
        )


def test_full_32k_preflight_checks_every_configured_service(monkeypatch):
    monkeypatch.setattr("bridgetree.training.GeneratorClient.answer", lambda *_args, **_kwargs: "(a)")
    monkeypatch.setattr("bridgetree.training.RerankerClient.rerank", lambda *_args, **_kwargs: [object()])

    report = preflight_tuning(
        load_config("configs/default.yaml"),
        load_training_config("configs/train.yaml"),
        embedder=DeterministicEmbedder(),
        check_services=True,
        require_full_32k=True,
    )

    assert report["services"] == {
        "checked": True,
        "embedding_dimension": 8,
        "generator_answer_parseable": True,
        "reranker_checked": True,
    }


def test_effect_first_matrix_reads_validation_only_and_writes_paired_artifacts(tmp_path, monkeypatch):
    from bridgetree.clients import RerankItem

    monkeypatch.setattr("bridgetree.training.GeneratorClient.answer", lambda *_args, **_kwargs: "(a)")

    def fake_rerank(_self, _query, documents, top_n):
        return [RerankItem(index, 1.0 - index / 100.0) for index in range(min(top_n, len(documents)))]

    monkeypatch.setattr("bridgetree.clients.RerankerClient.rerank", fake_rerank)
    result = run_effect_first_validation(
        _app_config(tmp_path),
        DeterministicEmbedder(),
        examples=_examples(34),
        output_dir=tmp_path / "effect",
        limit=5,
        generate=True,
    )

    run_dir = Path(result["run_dir"])
    assert result["status"] == "completed"
    assert result["partition"] == "persona_disjoint_validation"
    assert result["test_queries_read"] == 0
    assert result["validation_queries"] == 5
    assert tuple(result["methods"]) == EFFECT_FIRST_VALIDATION_METHODS
    assert result["selected_validation_accuracy"] == 1.0
    assert (run_dir / "effect_summary.json").is_file()
    assert (run_dir / "paired_results.json").is_file()
    result_rows = list(csv.DictReader((run_dir / "effect_results.csv").open(encoding="utf-8")))
    assert [row["method"] for row in result_rows] == list(EFFECT_FIRST_VALIDATION_METHODS)
    assert json.loads((run_dir / "run_status.json").read_text())["status"] == "completed"
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert len(events) == len(EFFECT_FIRST_VALIDATION_METHODS)
    assert {event["phase"] for event in events} == {"validation"}


def test_effect_first_failure_persists_terminal_failed_status(tmp_path, monkeypatch):
    def fail_rerank(*_args, **_kwargs):
        raise ConnectionError("injected reranker outage")

    monkeypatch.setattr("bridgetree.clients.RerankerClient.rerank", fail_rerank)
    output_root = tmp_path / "effect"

    with pytest.raises(RuntimeError, match="formal tuning requires zero failed queries"):
        run_effect_first_validation(
            _app_config(tmp_path),
            DeterministicEmbedder(),
            examples=_examples(),
            methods=("dense_rerank_20",),
            output_dir=output_root,
            generate=False,
        )

    run_dir = next(output_root.iterdir())
    assert json.loads((run_dir / "run_status.json").read_text())["status"] == "failed"
    assert json.loads((run_dir / "run_manifest.json").read_text())["status"] == "failed"
