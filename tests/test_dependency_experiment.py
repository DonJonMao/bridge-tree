from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from bridgetree.clients import RerankItem
from bridgetree.dependency_config import (
    DependencyConfig,
    DependencyExecutionConfig,
    DependencyRunConfig,
    load_dependency_config,
)
from bridgetree.dependency_experiment import (
    DependencyTask,
    DependencyTaskExecutor,
    PointwiseProtocolMismatch,
    RunIdentityMismatch,
    preflight_dependency_run,
    run_dependency_experiment,
)
from bridgetree.personamem import PersonaMemExample


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _vector(text):
        value = np.full(12, 0.01, dtype=np.float64)
        for word in text.lower().split():
            position = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % len(value)
            value[position] += 1.0
        return value / np.linalg.norm(value)

    def encode(self, texts):
        self.calls.append({"kind": "documents", "texts": tuple(texts)})
        return np.asarray([self._vector(text) for text in texts])

    def encode_query(self, text, instruction=None):
        self.calls.append({"kind": "query", "text": text, "instruction": instruction})
        return self._vector(text)


class FakeReranker:
    score_space = "unit_interval"
    score_contract = "pointwise"
    model_fingerprint = "deterministic-fake-reranker-v1"

    def __init__(self):
        self.calls = []

    @staticmethod
    def score(document):
        # A deterministic pointwise value, independent of batch composition
        # and order.  Its mild nonlinear hash interactions exercise search.
        digest = int(hashlib.sha256(document.encode()).hexdigest()[:10], 16)
        return 0.05 + 0.90 * (digest % 10000) / 10000.0

    def rerank_all(self, query, documents):
        self.calls.append({"query": query, "documents": tuple(documents)})
        # Deliberately shuffled: the set scorer must restore response indices.
        return [
            RerankItem(index, self.score(document))
            for index, document in reversed(list(enumerate(documents)))
        ]


class BatchDependentReranker(FakeReranker):
    """Invalid pointwise service whose scores change with batch size."""

    model_fingerprint = "batch-dependent-fake-reranker-v1"

    def rerank_all(self, query, documents):
        self.calls.append({"query": query, "documents": tuple(documents)})
        batch_offset = 0.01 * len(documents)
        return [
            RerankItem(index, min(self.score(document) + batch_offset, 0.999))
            for index, document in reversed(list(enumerate(documents)))
        ]


class FailDuringSearchReranker(FakeReranker):
    """Pass the probe and three search batches, then fail during search."""

    model_fingerprint = "search-failure-fake-reranker-v1"

    def rerank_all(self, query, documents):
        self.calls.append({"query": query, "documents": tuple(documents)})
        if len(self.calls) == 9:
            raise ValueError("synthetic reranker failure during dependency search")
        return [
            RerankItem(index, self.score(document))
            for index, document in reversed(list(enumerate(documents)))
        ]


class CardinalityReranker(FakeReranker):
    """Pointwise scorer with a positive marginal for every added memory."""

    model_fingerprint = "cardinality-fake-reranker-v1"

    @staticmethod
    def score(document):
        return 0.10 + 0.15 * document.count("[Memory ")


class FakeGenerator:
    def __init__(self, *, error=None, fail_count=0):
        self.calls = []
        self.error = error
        self.fail_count = fail_count

    def answer_plan(self, plan):
        self.calls.append(copy.deepcopy(plan.public_dict()))
        if len(self.calls) <= self.fail_count:
            raise self.error
        return "(a) Deterministic fake answer."


def example(question_id="q1", *, gold="(a)", options='["(a) Library", "(b) Club"]'):
    return PersonaMemExample(
        persona_id="persona",
        question_id=question_id,
        question_type="preference",
        topic="work",
        query="Where can I work quietly?",
        correct_answer=gold,
        all_options=options,
        shared_context_id="context",
        end_index=4,
        messages=[
            {"role": "user", "content": "I prefer quiet places."},
            {"role": "assistant", "content": "A library may suit you."},
            {"role": "user", "content": "I also need a large desk."},
            {"role": "assistant", "content": "Libraries usually provide desks."},
        ],
    )


def extended_example():
    item = example()
    return replace(
        item,
        end_index=8,
        messages=[
            *item.messages,
            {"role": "user", "content": "I need natural daylight."},
            {"role": "assistant", "content": "Choose a desk near a window."},
            {"role": "user", "content": "I avoid crowded rooms."},
            {"role": "assistant", "content": "Visit outside peak hours."},
        ],
    )


def fake_config(tmp_path, methods=("dense", "dense_rerank", "activation")):
    base = load_dependency_config("configs/chain_full.yaml")
    app = replace(
        base.app,
        runtime=replace(base.runtime, cache_dir=str(tmp_path / "cache")),
    )
    return DependencyRunConfig(
        app=app,
        dependency=DependencyConfig(
            initial_width=2,
            initial_expansion_width=1,
            proposal_width=1,
            max_ann_calls=5,
            max_scored_sets=32,
            max_selection_sets=32,
            pair_rescue_width=2,
            reranker_batch_size=8,
            reranker_max_input_tokens=8192,
        ),
        execution=DependencyExecutionConfig(
            methods=methods,
            log_every_questions=100,
            evaluate_every_questions=100,
            heartbeat_seconds=0.05,
        ),
    )


def test_full_data_preflight_freezes_2945_tasks_without_model_calls(tmp_path):
    result = preflight_dependency_run("configs/chain_full.yaml", tmp_path / "full")

    assert result["status"] == "preflight_complete"
    assert result["dataset"]["questions"] == 589
    assert result["expected_tasks"] == 2945
    assert result["model_calls"] == 0
    assert result["inference_complete"] is False
    assert result["summary"]["pending_tasks"] == 2945
    assert len((tmp_path / "full" / "planned_tasks.jsonl").read_text().splitlines()) == 2945
    assert not (tmp_path / "full" / "service_probe.json").exists()
    completion = json.loads((tmp_path / "full" / "completion.json").read_text())
    assert completion["complete"] is False
    assert completion["inference_complete"] is False
    assert json.loads(
        (tmp_path / "full" / "reports" / "seen_report.json").read_text()
    )["status"] == "not_defined"


def test_all_methods_execute_write_real_artifacts_and_successful_resume_is_zero_call(tmp_path):
    methods = (
        "dense",
        "dense_rerank",
        "activation",
        "context_marginal",
        "activation_fixed_pool",
        "activation_no_pairs",
        "activation_singleton_selection",
    )
    config = fake_config(tmp_path, methods)
    embedder, reranker, generator = FakeEmbedder(), FakeReranker(), FakeGenerator()
    run_dir = tmp_path / "run"

    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=embedder,
        reranker=reranker,
        generator=generator,
    )

    assert result["status"] == "completed"
    assert result["summary"]["successful_tasks"] == len(methods)
    assert len(generator.calls) == len(methods)
    outcome_paths = list((run_dir / "outcomes").glob("*.json"))
    assert len(outcome_paths) == len(methods)
    for path in outcome_paths:
        costs = json.loads(path.read_text())["costs"]
        assert "adapter_invocations" in costs
        assert "adapter_requests" not in costs
        assert "memory_embedding_adapter_invocations" in costs
        assert "memory_embedding_adapter_requests" not in costs
    assert len((run_dir / "predictions.jsonl").read_text().splitlines()) == len(methods)
    assert (run_dir / "failures.jsonl").read_text() == ""
    assert (run_dir / "modules" / "activation.jsonl").stat().st_size > 0
    assert (run_dir / "modules" / "selection.jsonl").stat().st_size > 0
    assert len(list((run_dir / "candidate_pool").glob("*.json"))) == len(methods)
    assert json.loads((run_dir / "service_probe.json").read_text())["status"] == "passed"
    # Full visible-bank document vectors are shared by all seven task methods.
    assert sum(call["kind"] == "documents" for call in embedder.calls) == 1

    counts = (len(embedder.calls), len(reranker.calls), len(generator.calls))
    resumed = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=embedder,
        reranker=reranker,
        generator=generator,
    )
    assert resumed["resume_noop"] is True
    assert resumed["model_calls_this_attempt"] == 0
    assert resumed["tasks_attempted_this_attempt"] == 0
    assert counts == (len(embedder.calls), len(reranker.calls), len(generator.calls))


def test_effectiveness_events_are_concrete_safe_and_periodic(tmp_path, capsys):
    base = fake_config(tmp_path, ("dense", "activation"))
    config = DependencyRunConfig(
        app=base.app,
        dependency=base.dependency,
        execution=replace(
            base.execution,
            log_every_questions=100,
            evaluate_every_questions=1,
        ),
    )
    run_dir = tmp_path / "effectiveness"
    secret_gold = "GOLD_VALUE_MUST_NOT_REACH_EFFECTIVENESS_LOGS"

    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[example(gold=secret_gold)],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed"
    stdout = capsys.readouterr().out
    effectiveness_rows = [
        json.loads(line)
        for line in (run_dir / "modules" / "effectiveness.jsonl")
        .read_text()
        .splitlines()
    ]
    task_rows = [
        row for row in effectiveness_rows if row["event"] == "module_effectiveness"
    ]
    metric_rows = [
        row for row in effectiveness_rows if row["event"] == "method_metrics"
    ]
    assert len(task_rows) == 2
    assert len(metric_rows) == 2
    assert '"event": "service_probe_passed"' in stdout
    assert stdout.count('"event": "module_effectiveness"') == 2
    assert stdout.count('"event": "method_metrics"') == 2
    assert secret_gold not in stdout
    assert secret_gold not in (run_dir / "modules" / "effectiveness.jsonl").read_text()

    by_method = {row["method_id"]: row for row in task_rows}
    dense = by_method["dense"]
    activation = by_method["activation"]
    assert dense["authoritative_at_write"] is True
    assert dense["retrieval"]["visible_memory_count"] == 2
    assert dense["retrieval"]["proposal_edges_are_dependency_claims"] is False
    assert dense["scoring"]["logical_unique_sets_charged_total"] == 0
    assert dense["dependency_search"]["enabled"] is False
    assert dense["selection"]["mode"] == "baseline_rank_order"
    assert activation["dependency_search"]["enabled"] is True
    assert activation["dependency_search"]["interaction_measurement_count"] > 0
    assert "not causal proof" in activation["dependency_search"]["interpretation"]
    assert activation["selection"]["mode"] == "dynamic_bundle_marginal"
    assert activation["generation_evaluation"]["generator_calls"] == 1
    assert activation["cost_accounting"][
        "shared_question_embedding_cost_is_method_order_dependent"
    ] is True

    first_methods = {row["method_id"]: row for row in metric_rows[0]["methods"]}
    assert first_methods["dense"]["final_accuracy"] is not None
    assert first_methods["activation"]["final_accuracy"] is None
    assert all(
        row["final_accuracy"] is not None for row in metric_rows[-1]["methods"]
    )
    train_log = (run_dir / "train.log").read_text()
    events_log = (run_dir / "events.jsonl").read_text()
    assert train_log.count('"event": "module_effectiveness"') == 2
    assert events_log.count('"event": "module_effectiveness"') == 2
    assert secret_gold not in train_log
    current_rows = [
        json.loads(line)
        for line in (run_dir / "modules" / "effectiveness.current.jsonl")
        .read_text()
        .splitlines()
    ]
    assert len(current_rows) == 2
    assert all(row["authoritative_current"] is True for row in current_rows)


def test_gold_and_options_do_not_change_set_cache_identity_and_gold_never_reaches_services(tmp_path):
    config = fake_config(tmp_path, ("activation",))
    task = DependencyTask(
        "synthetic",
        "32k",
        "persona",
        "q1",
        "activation",
        config.config_hash(),
        "data-that-may-contain-gold",
        "source",
        "not_defined",
    )
    base = example(gold="(a)")
    changed = example(gold="(b)", options='["(a) Reading room", "(b) Dance club"]')
    first_executor = DependencyTaskExecutor(
        config,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
        cache_dir=tmp_path / "cache-a",
    )
    second_executor = DependencyTaskExecutor(
        config,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
        cache_dir=tmp_path / "cache-b",
    )
    first_records = {m.memory_id: m for m in first_executor.visible_memories(base)}
    second_records = {m.memory_id: m for m in second_executor.visible_memories(changed)}
    assert first_executor._scorer(task, base, first_records).namespace_hash == second_executor._scorer(
        task, changed, second_records
    ).namespace_hash

    metadata_a = replace(
        base,
        metadata={
            "time": {"observed_start": 3, "gold_answer": "(a)"},
            "correct_answer": "(a)",
            "diagnostic_label": "private-a",
        },
    )
    metadata_b = replace(
        base,
        metadata={
            "time": {"observed_start": 3, "gold_answer": "(b)"},
            "correct_answer": "(b)",
            "diagnostic_label": "private-b",
        },
    )
    metadata_later = replace(
        metadata_b,
        metadata={"time": {"observed_start": 4}, "correct_answer": "(b)"},
    )
    metadata_hash_a = first_executor._scorer(
        task, metadata_a, first_records
    ).namespace_hash
    metadata_hash_b = first_executor._scorer(
        task, metadata_b, first_records
    ).namespace_hash
    metadata_hash_later = first_executor._scorer(
        task, metadata_later, first_records
    ).namespace_hash
    assert metadata_hash_a == metadata_hash_b
    assert metadata_hash_a != metadata_hash_later

    # Holding public options fixed while changing only gold makes every model
    # request byte-for-byte identical; only post-generation evaluation differs.
    gold_b = example(gold="(b)")
    services = []
    results = []
    for index, item in enumerate((base, gold_b)):
        embedder, reranker, generator = FakeEmbedder(), FakeReranker(), FakeGenerator()
        executor = DependencyTaskExecutor(
            config,
            embedder=embedder,
            reranker=reranker,
            generator=generator,
            cache_dir=tmp_path / f"isolated-{index}",
        )
        results.append(executor.execute(task, item))
        services.append((embedder.calls, reranker.calls, generator.calls))
    assert _semantic_requests(services[0]) == _semantic_requests(services[1])
    assert results[0]["correct"] is True
    assert results[1]["correct"] is False


def _semantic_requests(service_calls):
    # Convert tuples/dataclasses to a stable JSON value for a strict request
    # comparison without relying on object identities.
    return json.loads(json.dumps(service_calls, sort_keys=True, default=str))


def test_failure_denominator_append_only_history_and_retry(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "retry"
    failed_generator = FakeGenerator(error=ValueError("invalid fake answer service"), fail_count=1)
    first = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=failed_generator,
    )
    assert first["status"] == "completed_with_failures"
    assert first["summary"]["failed_tasks"] == 1
    assert first["summary"]["expected_tasks"] == 1
    assert first["summary"]["final_accuracy"] == 0.0
    assert len((run_dir / "failures.jsonl").read_text().splitlines()) == 1
    assert (run_dir / "predictions.jsonl").read_text() == ""
    failed_outcome = json.loads(next((run_dir / "outcomes").glob("*.json")).read_text())
    assert (
        failed_outcome["costs"]["adapter_invocations"][
            "generator_adapter_invocations"
        ]
        == 1
    )
    assert failed_outcome["costs"]["elapsed_ms"] > 0
    assert (
        failed_outcome["costs"]["elapsed_ms_scope"]
        == "complete_failed_task_attempt"
    )
    partial_pool = json.loads(next((run_dir / "candidate_pool").glob("*.json")).read_text())
    assert partial_pool["task_status"] == "failed_after_partial_execution"
    assert (run_dir / "modules" / "proposal.jsonl").stat().st_size > 0

    good_generator = FakeGenerator()
    second = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=good_generator,
    )
    assert second["status"] == "completed"
    assert second["summary"]["successful_tasks"] == 1
    outcome = json.loads(next((run_dir / "outcomes").glob("*.json")).read_text())
    assert outcome["attempt"] == 2
    assert len((run_dir / "failures.jsonl").read_text().splitlines()) == 1
    assert len((run_dir / "predictions.jsonl").read_text().splitlines()) == 1
    assert len((run_dir / "service_probes.jsonl").read_text().splitlines()) == 2
    effectiveness = [
        json.loads(line)
        for line in (run_dir / "modules" / "effectiveness.jsonl")
        .read_text()
        .splitlines()
        if '"event": "module_effectiveness"' in line
    ]
    assert [(row["attempt"], row["status"]) for row in effectiveness] == [
        (1, "error"),
        (2, "success"),
    ]
    authoritative = json.loads(
        next((run_dir / "outcomes").glob("*.json")).read_text()
    )["diagnostics"]["module_effectiveness"]
    assert authoritative["attempt"] == 2
    assert authoritative["status"] == "success"
    current = [
        json.loads(line)
        for line in (run_dir / "modules" / "effectiveness.current.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [(row["attempt"], row["status"]) for row in current] == [
        (2, "success")
    ]


def test_inconsistent_pointwise_probe_persists_full_measurement_history(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "bad-probe"

    with pytest.raises(PointwiseProtocolMismatch):
        run_dependency_experiment(
            config,
            run_dir,
            examples=[example()],
            embedder=FakeEmbedder(),
            reranker=BatchDependentReranker(),
            generator=FakeGenerator(),
        )
    with pytest.raises(PointwiseProtocolMismatch):
        run_dependency_experiment(
            config,
            run_dir,
            resume=True,
            examples=[example()],
            embedder=FakeEmbedder(),
            reranker=BatchDependentReranker(),
            generator=FakeGenerator(),
        )

    latest = json.loads((run_dir / "service_probe.json").read_text())
    history = [
        json.loads(line)
        for line in (run_dir / "service_probes.jsonl").read_text().splitlines()
    ]
    assert len(history) == 2
    assert latest == history[-1]
    assert [record["attempt"] for record in history] == [1, 2]
    for record in history:
        assert record["status"] == "failed"
        assert record["consistent"] is False
        assert record["rtol"] == pytest.approx(1e-5)
        assert record["atol"] == pytest.approx(1e-6)
        assert record["compared_values"] == 6
        assert record["max_absolute_deviation"] > record["atol"]
        assert record["max_relative_deviation"] > record["rtol"]
        assert record["reranker_adapter_requests"] == 5


def test_probe_history_is_durable_before_latest_snapshot(monkeypatch, tmp_path):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "probe-history-order"
    original_atomic_json = experiment_module._atomic_json
    interrupted = False

    def interrupt_latest_probe(path, value):
        nonlocal interrupted
        if path.name == "service_probe.json" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic latest-probe snapshot interruption")
        return original_atomic_json(path, value)

    monkeypatch.setattr(experiment_module, "_atomic_json", interrupt_latest_probe)
    first = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    assert first["status"] == "interrupted"
    first_history = [
        json.loads(line)
        for line in (run_dir / "service_probes.jsonl").read_text().splitlines()
    ]
    assert len(first_history) == 1
    assert first_history[0]["status"] == "passed"
    assert not (run_dir / "service_probe.json").exists()

    monkeypatch.undo()
    second = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    assert second["status"] == "completed"
    history = [
        json.loads(line)
        for line in (run_dir / "service_probes.jsonl").read_text().splitlines()
    ]
    assert [record["execution_attempt"] for record in history] == [1, 2]
    assert json.loads((run_dir / "service_probe.json").read_text()) == history[-1]


def test_search_reranker_failure_retains_proposal_and_scoring_checkpoints(tmp_path):
    base_config = fake_config(tmp_path, ("activation",))
    config = DependencyRunConfig(
        app=base_config.app,
        dependency=replace(
            base_config.dependency,
            initial_width=4,
            initial_expansion_width=1,
            max_ann_calls=12,
        ),
        execution=base_config.execution,
    )
    item = extended_example()
    run_dir = tmp_path / "search-failure"
    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[item],
        embedder=FakeEmbedder(),
        reranker=FailDuringSearchReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed_with_failures"
    outcome = json.loads(next((run_dir / "outcomes").glob("*.json")).read_text())
    assert outcome["error_type"] == "ValueError"
    assert outcome["costs"]["scored_sets"] > 0
    assert outcome["costs"]["reranker_adapter_requests"] == 4
    assert (
        outcome["costs"]["adapter_invocations"][
            "reranker_adapter_invocations"
        ]
        == 4
    )

    candidate = json.loads(next((run_dir / "candidate_pool").glob("*.json")).read_text())
    assert candidate["task_status"] == "failed_after_partial_execution"
    assert candidate["checkpoint_stage"] == "dependency_search"
    assert candidate["retrieval"]["proposal_batches"]
    assert candidate["search"]["partial"] is True
    assert candidate["search"]["activations"]
    assert candidate["search"]["states"]
    proposal_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "proposal.jsonl").read_text().splitlines()
    ]
    activation_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "activation.jsonl").read_text().splitlines()
    ]
    state_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "state.jsonl").read_text().splitlines()
    ]
    scoring_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "scoring.jsonl").read_text().splitlines()
    ]
    cost_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "cost.jsonl").read_text().splitlines()
    ]
    assert proposal_events
    assert scoring_events
    assert activation_events
    assert state_events
    checkpoint_cost = next(
        record for record in cost_events if record["event"] == "task_cost_checkpoint"
    )
    assert checkpoint_cost["checkpoint_stage"] == "dependency_search"
    assert checkpoint_cost["scored_sets"] > 0


def test_selection_failure_retains_completed_rounds(monkeypatch, tmp_path):
    from bridgetree.dependency_search import DynamicBundleSelector

    base_config = fake_config(tmp_path, ("activation",))
    config = DependencyRunConfig(
        app=base_config.app,
        dependency=replace(
            base_config.dependency,
            initial_width=4,
            initial_expansion_width=1,
        ),
        execution=base_config.execution,
    )
    original_feasible = DynamicBundleSelector._feasible

    def fail_after_completed_round(self, ids):
        progress = self._partial_progress
        if progress is not None and progress["rounds"]:
            raise ValueError("synthetic selection failure after a completed round")
        return original_feasible(self, ids)

    monkeypatch.setattr(DynamicBundleSelector, "_feasible", fail_after_completed_round)
    run_dir = tmp_path / "selection-failure"
    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[extended_example()],
        embedder=FakeEmbedder(),
        reranker=CardinalityReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed_with_failures"
    outcome = json.loads(next((run_dir / "outcomes").glob("*.json")).read_text())
    assert outcome["error_type"] == "ValueError"
    candidate = json.loads(next((run_dir / "candidate_pool").glob("*.json")).read_text())
    partial_selection = candidate["selection"]
    assert candidate["checkpoint_stage"] == "bundle_selection"
    assert partial_selection["partial"] is True
    assert partial_selection["selected_ids"]
    assert len(partial_selection["rounds"]) == 1
    assert partial_selection["rounds"][0]["complete"] is True
    assert partial_selection["steps"]
    assert partial_selection["stop"]["reason"] == "execution_error"

    selection_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "selection.jsonl").read_text().splitlines()
    ]
    stop_events = [
        json.loads(line)
        for line in (run_dir / "modules" / "stop.jsonl").read_text().splitlines()
    ]
    assert any(record.get("accepted") is True for record in selection_events)
    assert selection_events[-1]["reason"] == "execution_error"
    assert any(record.get("reason") == "execution_error" for record in stop_events)


@pytest.mark.parametrize("failure_site", ("executor", "heartbeat"))
def test_initialization_failure_finalizes_attempt_and_can_resume(
    monkeypatch, tmp_path, failure_site
):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / f"initialization-{failure_site}"
    message = f"synthetic {failure_site} initialization failure"
    if failure_site == "executor":

        class BrokenExecutor:
            def __init__(self, *args, **kwargs):
                raise RuntimeError(message)

        monkeypatch.setattr(experiment_module, "DependencyTaskExecutor", BrokenExecutor)
    else:

        def broken_start(self):
            raise RuntimeError(message)

        monkeypatch.setattr(experiment_module._Heartbeat, "start", broken_start)

    with pytest.raises(RuntimeError, match=message):
        run_dependency_experiment(
            config,
            run_dir,
            examples=[example()],
            embedder=FakeEmbedder(),
            reranker=FakeReranker(),
            generator=FakeGenerator(),
        )

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    completion = json.loads((run_dir / "completion.json").read_text())
    failures = [
        json.loads(line) for line in (run_dir / "failures.jsonl").read_text().splitlines()
    ]
    assert manifest["status"] == "interrupted"
    assert manifest["last_attempt"]["stop_reason"] == "execution_initialization_failure"
    assert completion["status"] == "interrupted"
    assert completion["inference_complete"] is False
    assert completion["pending_tasks"] == 1
    assert len(failures) == 1
    assert failures[0]["event"] == "execution_initialization_failure"
    assert failures[0]["error"] == message
    assert not list((run_dir / "outcomes").glob("*.json"))
    assert (run_dir / "service_probes.jsonl").read_text() == ""

    monkeypatch.undo()
    resumed = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    assert resumed["status"] == "completed"
    assert resumed["summary"]["successful_tasks"] == 1
    assert json.loads((run_dir / "run_manifest.json").read_text())[
        "execution_attempts"
    ] == 2


def test_transport_outage_stops_after_current_failure_and_leaves_rest_pending(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "outage"
    generator = FakeGenerator(error=ConnectionError("service unavailable"), fail_count=10)
    first = run_dependency_experiment(
        config,
        run_dir,
        examples=[example("q1"), example("q2")],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=generator,
    )
    assert first["status"] == "interrupted"
    assert first["summary"]["failed_tasks"] == 1
    assert first["summary"]["pending_tasks"] == 1
    assert len(generator.calls) == 1
    assert len(list((run_dir / "outcomes").glob("*.json"))) == 1

    resumed = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example("q1"), example("q2")],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    assert resumed["status"] == "completed"
    assert resumed["summary"]["successful_tasks"] == 2
    assert len((run_dir / "failures.jsonl").read_text().splitlines()) == 1
    assert len((run_dir / "predictions.jsonl").read_text().splitlines()) == 2


def test_keyboard_interrupt_finalizes_resumable_attempt(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "operator-interrupt"

    interrupted = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(error=KeyboardInterrupt(), fail_count=1),
    )

    assert interrupted["status"] == "interrupted"
    assert interrupted["stop_reason"] == "execution_interrupted"
    assert interrupted["summary"]["pending_tasks"] == 1
    assert interrupted["summary"]["failed_tasks"] == 0
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    completion = json.loads((run_dir / "completion.json").read_text())
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text())
    failures = [
        json.loads(line) for line in (run_dir / "failures.jsonl").read_text().splitlines()
    ]
    assert manifest["status"] == "interrupted"
    assert manifest["last_attempt"]["stop_reason"] == "execution_interrupted"
    assert completion["status"] == "interrupted"
    assert completion["inference_complete"] is False
    assert heartbeat["active"] is False
    assert failures[-1]["event"] == "execution_interrupted"
    assert failures[-1]["stage"] == "task_execution"
    assert failures[-1]["task_id"]
    assert not list((run_dir / "outcomes").glob("*.json"))
    partial_pool = json.loads(next((run_dir / "candidate_pool").glob("*.json")).read_text())
    assert partial_pool["task_status"] == "interrupted_after_partial_execution"

    resumed = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    assert resumed["status"] == "completed"
    assert resumed["summary"]["successful_tasks"] == 1


def test_interrupt_after_atomic_outcome_reloads_authoritative_coverage(
    monkeypatch, tmp_path
):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "outcome-commit-interrupt"
    original_append_jsonl = experiment_module._append_jsonl
    interrupted = False

    def interrupt_task_success(path, row):
        nonlocal interrupted
        if row.get("event") == "task_success" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic post-outcome interruption")
        return original_append_jsonl(path, row)

    monkeypatch.setattr(experiment_module, "_append_jsonl", interrupt_task_success)
    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed"
    assert result["summary"]["successful_tasks"] == 1
    assert result["summary"]["pending_tasks"] == 0
    assert json.loads((run_dir / "completion.json").read_text())["status"] == "completed"
    assert json.loads((run_dir / "run_manifest.json").read_text())["status"] == "completed"
    interruptions = [
        json.loads(line)
        for line in (run_dir / "failures.jsonl").read_text().splitlines()
    ]
    assert interruptions[-1]["authoritative_outcome_status"] == "success"


def test_resume_recovers_an_empty_preexecution_run_directory(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "empty-started-run"
    run_dir.mkdir()

    result = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed"
    assert result["summary"]["successful_tasks"] == 1
    preparation = json.loads((run_dir / "preparation_identity.json").read_text())
    assert preparation["status"] == "prepared"


def test_outer_interrupt_after_prepare_completes_zero_call_preflight(monkeypatch, tmp_path):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "preflight-outer-interrupt"
    original_prepare = experiment_module._prepare_run
    interrupted = False

    def interrupt_once(*args, **kwargs):
        nonlocal interrupted
        prepared = original_prepare(*args, **kwargs)
        if not interrupted and not kwargs.get("resume", False):
            interrupted = True
            raise KeyboardInterrupt("synthetic post-prepare interruption")
        return prepared

    monkeypatch.setattr(experiment_module, "_prepare_run", interrupt_once)
    result = run_dependency_experiment(
        config,
        run_dir,
        preflight_only=True,
        examples=[example()],
    )

    assert result["status"] == "preflight_complete"
    assert result["model_calls"] == 0
    assert result["inference_complete"] is False
    assert result["recovered_after_interruption"] is True
    assert json.loads((run_dir / "run_manifest.json").read_text())["status"] == (
        "preflight_complete"
    )


def test_outer_interrupt_during_terminal_manifest_write_recovers_completion(
    monkeypatch, tmp_path
):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "terminal-outer-interrupt"
    original_finalize = experiment_module._finalize_manifest
    interrupted = False

    def interrupt_once(prepared, **kwargs):
        nonlocal interrupted
        if kwargs.get("status") == "completed" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic terminal manifest interruption")
        return original_finalize(prepared, **kwargs)

    monkeypatch.setattr(experiment_module, "_finalize_manifest", interrupt_once)
    result = run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )

    assert result["status"] == "completed"
    assert result["recovered_after_interruption"] is True
    assert result["summary"]["successful_tasks"] == 1
    assert json.loads((run_dir / "completion.json").read_text())["status"] == "completed"
    assert json.loads((run_dir / "run_manifest.json").read_text())["status"] == "completed"


def test_outer_interrupt_during_successful_resume_view_remains_zero_call(
    monkeypatch, tmp_path
):
    import bridgetree.dependency_experiment as experiment_module

    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "resume-view-outer-interrupt"
    run_dependency_experiment(
        config,
        run_dir,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FakeGenerator(),
    )
    original_write_views = experiment_module._write_run_views
    interrupted = False

    def interrupt_once(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic successful-resume view interruption")
        return original_write_views(*args, **kwargs)

    monkeypatch.setattr(experiment_module, "_write_run_views", interrupt_once)
    embedder, reranker, generator = FakeEmbedder(), FakeReranker(), FakeGenerator()
    result = run_dependency_experiment(
        config,
        run_dir,
        resume=True,
        examples=[example()],
        embedder=embedder,
        reranker=reranker,
        generator=generator,
    )

    assert result["status"] == "completed"
    assert result["model_calls_this_attempt"] == 0
    assert result["resume_noop"] is True
    assert result["recovered_after_interruption"] is True
    assert not embedder.calls
    assert not reranker.calls
    assert not generator.calls


def test_resume_rejects_changed_data_and_config_before_services(tmp_path):
    config = fake_config(tmp_path, ("dense",))
    run_dir = tmp_path / "identity"
    preflight_dependency_run(config, run_dir, examples=[example()])

    with pytest.raises(RunIdentityMismatch, match="identity mismatch"):
        run_dependency_experiment(
            config,
            run_dir,
            examples=[example(gold="(b)")],
            embedder=FakeEmbedder(),
            reranker=FakeReranker(),
            generator=FakeGenerator(),
        )
    changed_config = fake_config(tmp_path, ("dense", "dense_rerank"))
    with pytest.raises(RunIdentityMismatch, match="identity mismatch"):
        run_dependency_experiment(
            changed_config,
            run_dir,
            examples=[example()],
            embedder=FakeEmbedder(),
            reranker=FakeReranker(),
            generator=FakeGenerator(),
        )
