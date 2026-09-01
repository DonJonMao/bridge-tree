from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import yaml

from .clients import Embedder, GeneratorClient
from .config import AppConfig, RetrievalConfig
from .experiment import ABLATION_OPTIONS, EmbeddingCache, load_bridge_gold, retrieve_method
from .metrics import answer_accuracy, bridge_recall_at_k, direct_ranks, recall_at_k
from .module_metrics import (
    MODULE_NAMES,
    aggregate_module_metrics,
    flatten_module_metrics,
    metric_value,
    module_metric_delta,
)
from .module_metrics import collect_module_metrics as collect_metrics
from .personamem import PersonaMemExample, iter_examples, messages_to_memories

DEFAULT_DIAGNOSTIC_METHODS = (
    "bridgetree",
    "ablation_no_cluster",
    "ablation_bfs",
    "ablation_fixed_depth",
    "ablation_topk",
    "ablation_rho_dpp",
    "ablation_direct_path",
)


@dataclass(frozen=True)
class SplitProtocol:
    train_ratio: float = 0.70
    validation_ratio: float = 0.15
    test_ratio: float = 0.15


@dataclass(frozen=True)
class TrainingSchedule:
    periodic_eval_every: int = 50
    periodic_eval_queries: int = 8
    max_train_queries: int | None = None
    max_validation_queries: int | None = None
    max_test_queries: int | None = None


@dataclass(frozen=True)
class SearchSpace:
    first_hop_width: tuple[int, ...] = (8, 12)
    branch_width: tuple[int, ...] = (4, 8)
    search_budget: tuple[int, ...] = (64,)


@dataclass(frozen=True)
class TrainingExperimentConfig:
    seed: int = 42
    split: SplitProtocol = field(default_factory=SplitProtocol)
    schedule: TrainingSchedule = field(default_factory=TrainingSchedule)
    search_space: SearchSpace = field(default_factory=SearchSpace)
    diagnostic_methods: tuple[str, ...] = DEFAULT_DIAGNOSTIC_METHODS
    objective_metric: str = "selection.logdet_value"
    objective_mode: str = "max"
    bridge_gold_path: str | None = None
    final_generate: bool = False
    keep_example_metrics: bool = True
    output_dir: str = "outputs/training"

    def validate(self) -> None:
        ratios = (self.split.train_ratio, self.split.validation_ratio, self.split.test_ratio)
        if any(value <= 0.0 for value in ratios) or abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError("train/validation/test ratios must be positive and sum to 1")
        if self.schedule.periodic_eval_every <= 0 or self.schedule.periodic_eval_queries <= 0:
            raise ValueError("periodic_eval_every and periodic_eval_queries must be positive")
        for name in ("max_train_queries", "max_validation_queries", "max_test_queries"):
            value = getattr(self.schedule, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when set")
        if (
            not self.search_space.first_hop_width
            or not self.search_space.branch_width
            or not self.search_space.search_budget
        ):
            raise ValueError("training search space cannot be empty")
        if any(value <= 0 for value in self.search_space.first_hop_width + self.search_space.branch_width):
            raise ValueError("search widths must be positive")
        if any(value <= 0 for value in self.search_space.search_budget):
            raise ValueError("search budgets must be positive")
        if min(self.search_space.search_budget) < max(self.search_space.first_hop_width):
            raise ValueError("every search budget must be >= every first-hop width")
        if not self.diagnostic_methods or self.diagnostic_methods[0] != "bridgetree":
            raise ValueError("diagnostic_methods must start with bridgetree")
        unsupported = set(self.diagnostic_methods) - set(ABLATION_OPTIONS)
        if unsupported:
            raise ValueError(f"training diagnostics require tree-producing methods; unsupported: {sorted(unsupported)}")
        if self.objective_mode not in {"max", "min"}:
            raise ValueError("objective_mode must be max or min")
        if "." not in self.objective_metric:
            raise ValueError("objective_metric must have the form module.metric")


@dataclass(frozen=True)
class ExampleSplits:
    train: tuple[PersonaMemExample, ...]
    validation: tuple[PersonaMemExample, ...]
    test: tuple[PersonaMemExample, ...]
    train_personas: tuple[str, ...]
    validation_personas: tuple[str, ...]
    test_personas: tuple[str, ...]


def _tuple_ints(value: Any, default: tuple[int, ...]) -> tuple[int, ...]:
    values = default if value is None else tuple(int(item) for item in value)
    return tuple(sorted(set(values)))


def load_training_config(path: str | Path) -> TrainingExperimentConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("training configuration root must be a mapping")
    split_raw = raw.get("split", {})
    schedule_raw = raw.get("schedule", {})
    search_raw = raw.get("search_space", {})
    config = TrainingExperimentConfig(
        seed=int(raw.get("seed", 42)),
        split=SplitProtocol(**split_raw),
        schedule=TrainingSchedule(**schedule_raw),
        search_space=SearchSpace(
            first_hop_width=_tuple_ints(search_raw.get("first_hop_width"), (8, 12)),
            branch_width=_tuple_ints(search_raw.get("branch_width"), (4, 8)),
            search_budget=_tuple_ints(search_raw.get("search_budget"), (64,)),
        ),
        diagnostic_methods=tuple(raw.get("diagnostic_methods", DEFAULT_DIAGNOSTIC_METHODS)),
        objective_metric=str(raw.get("objective_metric", "selection.logdet_value")),
        objective_mode=str(raw.get("objective_mode", "max")),
        bridge_gold_path=raw.get("bridge_gold_path"),
        final_generate=bool(raw.get("final_generate", False)),
        keep_example_metrics=bool(raw.get("keep_example_metrics", True)),
        output_dir=str(raw.get("output_dir", "outputs/training")),
    )
    config.validate()
    return config


def _stable_key(seed: int, namespace: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{namespace}:{value}".encode("utf-8")).hexdigest()


def split_examples_by_persona(
    examples: Sequence[PersonaMemExample], protocol: SplitProtocol, seed: int
) -> ExampleSplits:
    personas = sorted(
        {example.persona_id for example in examples}, key=lambda value: _stable_key(seed, "persona", value)
    )
    if len(personas) < 3:
        raise ValueError("persona-disjoint train/validation/test splitting requires at least 3 personas")
    train_count = max(1, int(round(len(personas) * protocol.train_ratio)))
    validation_count = max(1, int(round(len(personas) * protocol.validation_ratio)))
    if train_count + validation_count >= len(personas):
        train_count = max(1, len(personas) - validation_count - 1)
    test_count = len(personas) - train_count - validation_count
    if test_count < 1:
        validation_count = max(1, validation_count - (1 - test_count))
        test_count = len(personas) - train_count - validation_count
    train_personas = tuple(sorted(personas[:train_count]))
    validation_personas = tuple(sorted(personas[train_count : train_count + validation_count]))
    test_personas = tuple(sorted(personas[train_count + validation_count :]))
    persona_sets = (set(train_personas), set(validation_personas), set(test_personas))

    def select(persona_set: set[str], phase: str) -> tuple[PersonaMemExample, ...]:
        selected = [example for example in examples if example.persona_id in persona_set]
        return tuple(sorted(selected, key=lambda item: _stable_key(seed, phase, item.question_id)))

    return ExampleSplits(
        train=select(persona_sets[0], "train"),
        validation=select(persona_sets[1], "validation"),
        test=select(persona_sets[2], "test"),
        train_personas=train_personas,
        validation_personas=validation_personas,
        test_personas=test_personas,
    )


def _limited(examples: Sequence[PersonaMemExample], limit: int | None) -> tuple[PersonaMemExample, ...]:
    return tuple(examples[:limit]) if limit is not None else tuple(examples)


def build_retrieval_trials(base: RetrievalConfig, search_space: SearchSpace) -> list[RetrievalConfig]:
    trials = []
    for first_hop, branch_width, budget in product(
        search_space.first_hop_width,
        search_space.branch_width,
        search_space.search_budget,
    ):
        candidate = replace(
            base,
            first_hop_width=first_hop,
            branch_width=branch_width,
            search_budget=budget,
        )
        candidate.validate()
        trials.append(candidate)
    return trials


class TrainingMetricsWriter:
    def __init__(self, root: Path, keep_examples: bool):
        self.root = root
        self.keep_examples = keep_examples
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "modules").mkdir()
        self.event_id = 0
        with (self.root / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(
                ["event_id", "phase", "trial", "step", "method", "queries", "module", "metric", "value"]
            )

    def write_json(self, name: str, value: Any) -> None:
        with (self.root / name).open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    def write_example(self, context: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
        if not self.keep_examples:
            return
        with (self.root / "example_metrics.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**context, "modules": metrics}, ensure_ascii=False) + "\n")

    def write_event(
        self,
        phase: str,
        trial: int,
        step: int,
        method: str,
        summary: Mapping[str, Any],
        retrieval_config: RetrievalConfig,
    ) -> Dict[str, Any]:
        self.event_id += 1
        event = {
            "event_id": self.event_id,
            "timestamp": time.time(),
            "phase": phase,
            "trial": trial,
            "step": step,
            "method": method,
            "retrieval": asdict(retrieval_config),
            "metrics": summary,
        }
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        with (self.root / "metrics.csv").open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            for path, value in flatten_module_metrics(summary.get("modules", {})).items():
                module, metric = path.split(".", 1)
                writer.writerow(
                    [self.event_id, phase, trial, step, method, summary.get("queries", 0), module, metric, value]
                )
        for module in MODULE_NAMES:
            record = {
                "event_id": self.event_id,
                "phase": phase,
                "trial": trial,
                "step": step,
                "method": method,
                "queries": summary.get("queries", 0),
                "metrics": summary.get("modules", {}).get(module, {}),
            }
            with (self.root / "modules" / f"{module}.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        objective_preview = summary.get("modules", {}).get("selection", {}).get("logdet_value")
        print(
            f"[BridgeTree train] phase={phase} trial={trial} step={step} method={method} "
            f"queries={summary.get('queries', 0)} logdet={objective_preview}"
        )
        return event

    def write_comparison(self, context: Mapping[str, Any], value: Mapping[str, Any]) -> None:
        with (self.root / "module_effects.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**context, "full_minus_ablation": value}, ensure_ascii=False) + "\n")


class TrainingEvaluator:
    def __init__(
        self,
        app_config: AppConfig,
        embedder: Embedder,
        writer: TrainingMetricsWriter,
        bridge_gold: Mapping[str, Sequence[str]],
    ):
        self.app_config = app_config
        self.cache = EmbeddingCache(
            app_config.runtime.cache_dir,
            embedder,
            app_config.models.embedding.model,
        )
        self.writer = writer
        self.bridge_gold = bridge_gold
        self.generator = GeneratorClient(app_config.models.generator)

    def evaluate_one(
        self,
        example: PersonaMemExample,
        method: str,
        generate: bool,
        context: Mapping[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        total_started = time.perf_counter()
        segment_started = time.perf_counter()
        memories = messages_to_memories(
            example.messages,
            source_prefix=example.question_id,
            include_system_persona=self.app_config.data.include_system_persona,
        )
        segmentation_seconds = time.perf_counter() - segment_started
        if not memories:
            raise ValueError(f"example has no retrievable memories: {example.question_id}")

        query_started = time.perf_counter()
        query_vector = self.cache.encode_query(example.query)
        query_embedding_seconds = time.perf_counter() - query_started
        document_started = time.perf_counter()
        memory_vectors = self.cache.encode_documents([memory.text for memory in memories])
        document_embedding_seconds = time.perf_counter() - document_started
        retrieval_started = time.perf_counter()
        selected_ids, selected, _diagnostics, bridge_result = retrieve_method(
            method,
            self.app_config,
            example,
            memories,
            query_vector,
            memory_vectors,
        )
        retrieval_seconds = time.perf_counter() - retrieval_started
        if bridge_result is None:
            raise ValueError(f"module training requires a tree-producing method: {method}")

        response = ""
        generation_seconds = 0.0
        accuracy = None
        if generate:
            generation_started = time.perf_counter()
            response = self.generator.answer(example.query, selected, example.all_options)
            generation_seconds = time.perf_counter() - generation_started
            accuracy = answer_accuracy(response, example.correct_answer)

        recall = None
        bridge_recall = None
        gold_ids = self.bridge_gold.get(example.question_id, ())
        if gold_ids:
            ranks = direct_ranks(query_vector, [memory.memory_id for memory in memories], memory_vectors)
            recall = recall_at_k(selected_ids, gold_ids, self.app_config.retrieval.context_size)
            bridge_recall = bridge_recall_at_k(
                selected_ids,
                gold_ids,
                ranks,
                self.app_config.retrieval.context_size,
            )
        timings = {
            "segmentation_seconds": segmentation_seconds,
            "query_embedding_seconds": query_embedding_seconds,
            "document_embedding_seconds": document_embedding_seconds,
            "retrieval_seconds": retrieval_seconds,
            "generation_seconds": generation_seconds,
            "total_seconds": time.perf_counter() - total_started,
        }
        metrics = collect_metrics(
            bridge_result,
            query_vector,
            memory_vectors,
            self.app_config.retrieval,
            timings=timings,
            answer_accuracy_value=accuracy,
            recall_value=recall,
            bridge_recall_value=bridge_recall,
        )
        self.writer.write_example(
            {
                **context,
                "method": method,
                "persona_id": example.persona_id,
                "question_id": example.question_id,
                "selected_memory_ids": selected_ids,
                "response": response,
            },
            metrics,
        )
        return metrics

    def evaluate_set(
        self,
        examples: Sequence[PersonaMemExample],
        method: str,
        generate: bool,
        context: Mapping[str, Any],
    ) -> Dict[str, Any]:
        records = [self.evaluate_one(example, method, generate, context) for example in examples]
        return aggregate_module_metrics(records)


def _read_examples(app_config: AppConfig) -> list[PersonaMemExample]:
    raw_root = Path(app_config.data.raw_dir)
    question_path = raw_root / f"questions_{app_config.data.split}.csv"
    context_path = raw_root / f"shared_contexts_{app_config.data.split}.jsonl"
    if not question_path.exists() or not context_path.exists():
        raise FileNotFoundError("PersonaMem raw data is missing; run `bridgetree download-personamem` first")
    return list(iter_examples(question_path, context_path))


def _split_manifest(splits: ExampleSplits, seed: int) -> Dict[str, Any]:
    def describe(examples: Sequence[PersonaMemExample], personas: Sequence[str]) -> Dict[str, Any]:
        ids = [example.question_id for example in examples]
        return {
            "queries": len(ids),
            "personas": list(personas),
            "question_id_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
        }

    return {
        "seed": seed,
        "unit": "persona",
        "train": describe(splits.train, splits.train_personas),
        "validation": describe(splits.validation, splits.validation_personas),
        "test": describe(splits.test, splits.test_personas),
    }


def _is_better(
    score: float,
    cost: float,
    best_score: float | None,
    best_cost: float | None,
    mode: str,
) -> bool:
    if best_score is None:
        return True
    if (mode == "max" and score > best_score + 1e-12) or (mode == "min" and score < best_score - 1e-12):
        return True
    return abs(score - best_score) <= 1e-12 and (best_cost is None or cost < best_cost)


def run_training_experiment(
    app_config: AppConfig,
    training_config: TrainingExperimentConfig,
    embedder: Embedder,
    examples: Sequence[PersonaMemExample] | None = None,
    output_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Run training-free hyperparameter optimization with periodic validation.

    The routine never updates model weights. "Training" means selecting fixed
    BridgeTree resource/configuration parameters on train/validation personas.
    """
    training_config.validate()
    all_examples = list(examples) if examples is not None else _read_examples(app_config)
    splits = split_examples_by_persona(all_examples, training_config.split, training_config.seed)
    train_examples = _limited(splits.train, training_config.schedule.max_train_queries)
    validation_examples = _limited(splits.validation, training_config.schedule.max_validation_queries)
    test_examples = _limited(splits.test, training_config.schedule.max_test_queries)
    probe_examples = validation_examples[: training_config.schedule.periodic_eval_queries]
    if not train_examples or not validation_examples or not test_examples or not probe_examples:
        raise ValueError("training, validation, test, and periodic validation probe must all be non-empty")

    root = Path(output_dir or training_config.output_dir) / f"train_{time.time_ns()}"
    writer = TrainingMetricsWriter(root, training_config.keep_example_metrics)
    writer.write_json("training_config.json", asdict(training_config))
    writer.write_json("split_manifest.json", _split_manifest(splits, training_config.seed))
    bridge_gold = load_bridge_gold(training_config.bridge_gold_path)
    trials = build_retrieval_trials(app_config.retrieval, training_config.search_space)

    trial_summaries = []
    best_trial = None
    best_score = None
    best_cost = None
    best_app_config = None
    best_train_metrics = None
    best_validation_metrics = None

    for trial_index, retrieval_config in enumerate(trials, start=1):
        current_app = replace(app_config, retrieval=retrieval_config)
        evaluator = TrainingEvaluator(current_app, embedder, writer, bridge_gold)
        train_records: List[Mapping[str, Mapping[str, float]]] = []
        latest_probe_by_method: Dict[str, Any] = {}
        for step, example in enumerate(train_examples, start=1):
            train_records.append(
                evaluator.evaluate_one(
                    example,
                    "bridgetree",
                    False,
                    {"phase": "train", "trial": trial_index, "step": step},
                )
            )
            should_probe = step % training_config.schedule.periodic_eval_every == 0 or step == len(train_examples)
            if not should_probe:
                continue
            train_summary = aggregate_module_metrics(train_records)
            writer.write_event("train_progress", trial_index, step, "bridgetree", train_summary, retrieval_config)
            latest_probe_by_method = {}
            for method in training_config.diagnostic_methods:
                probe_summary = evaluator.evaluate_set(
                    probe_examples,
                    method,
                    False,
                    {"phase": "validation_probe", "trial": trial_index, "step": step},
                )
                latest_probe_by_method[method] = probe_summary
                writer.write_event(
                    "validation_probe",
                    trial_index,
                    step,
                    method,
                    probe_summary,
                    retrieval_config,
                )
            full_probe = latest_probe_by_method["bridgetree"]
            for method, probe_summary in latest_probe_by_method.items():
                if method == "bridgetree":
                    continue
                writer.write_comparison(
                    {"phase": "validation_probe", "trial": trial_index, "step": step, "ablation": method},
                    module_metric_delta(full_probe, probe_summary),
                )

        validation_by_method: Dict[str, Any] = {}
        for method in training_config.diagnostic_methods:
            validation_summary = evaluator.evaluate_set(
                validation_examples,
                method,
                False,
                {"phase": "validation", "trial": trial_index, "step": len(train_examples)},
            )
            validation_by_method[method] = validation_summary
            writer.write_event(
                "validation",
                trial_index,
                len(train_examples),
                method,
                validation_summary,
                retrieval_config,
            )
        objective = metric_value(validation_by_method["bridgetree"], training_config.objective_metric)
        cost = metric_value(validation_by_method["bridgetree"], "search.ann_calls")
        train_summary = aggregate_module_metrics(train_records)
        trial_summary = {
            "trial": trial_index,
            "retrieval": asdict(retrieval_config),
            "objective": objective,
            "objective_metric": training_config.objective_metric,
            "mean_ann_calls": cost,
            "train": train_summary,
            "validation": validation_by_method,
            "last_periodic_probe": latest_probe_by_method,
        }
        trial_summaries.append(trial_summary)
        if _is_better(objective, cost, best_score, best_cost, training_config.objective_mode):
            best_trial = trial_index
            best_score = objective
            best_cost = cost
            best_app_config = current_app
            best_train_metrics = train_summary
            best_validation_metrics = validation_by_method
        writer.write_json("trials.json", trial_summaries)

    if best_app_config is None or best_trial is None:
        raise RuntimeError("no valid training trial completed")
    final_evaluator = TrainingEvaluator(best_app_config, embedder, writer, bridge_gold)
    final_test_by_method: Dict[str, Any] = {}
    for method in training_config.diagnostic_methods:
        test_summary = final_evaluator.evaluate_set(
            test_examples,
            method,
            training_config.final_generate and method == "bridgetree",
            {"phase": "test", "trial": best_trial, "step": len(train_examples)},
        )
        final_test_by_method[method] = test_summary
        writer.write_event(
            "test",
            best_trial,
            len(train_examples),
            method,
            test_summary,
            best_app_config.retrieval,
        )

    full_test = final_test_by_method["bridgetree"]
    effects = {
        method: module_metric_delta(full_test, summary)
        for method, summary in final_test_by_method.items()
        if method != "bridgetree"
    }
    final_summary = {
        "optimization_kind": "training_free_hyperparameter_search",
        "run_dir": str(root),
        "best_trial": best_trial,
        "best_retrieval_config": asdict(best_app_config.retrieval),
        "objective_metric": training_config.objective_metric,
        "objective_mode": training_config.objective_mode,
        "best_validation_objective": best_score,
        "train_metrics": best_train_metrics,
        "validation_metrics": best_validation_metrics,
        "test_metrics": final_test_by_method,
        "test_module_effects_full_minus_ablation": effects,
        "trial_count": len(trials),
    }
    writer.write_json("final_summary.json", final_summary)
    writer.write_json("best_config.json", {"retrieval": asdict(best_app_config.retrieval)})
    return final_summary
