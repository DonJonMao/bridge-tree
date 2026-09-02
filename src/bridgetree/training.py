from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import yaml

from .budget import CostTracker, SearchBudget
from .clients import (
    Embedder,
    GeneratorClient,
    RerankerClient,
    context_token_count,
    fit_context_budget,
    generation_prompt_hash,
)
from .config import AppConfig, RetrievalConfig
from .experiment import ABLATION_OPTIONS, METHODS, EmbeddingCache, IndexCache, load_bridge_gold, retrieve_method
from .metrics import answer_accuracy, answer_parse_failed, bridge_recall_at_k, direct_ranks, recall_at_k
from .module_metrics import (
    MODULE_NAMES,
    aggregate_module_metrics,
    flatten_module_metrics,
    metric_value,
    module_metric_delta,
)
from .module_metrics import collect_module_metrics as collect_metrics
from .personamem import PERSONAMEM_REVISION, PersonaMemExample, iter_examples, messages_to_memories

DEFAULT_DIAGNOSTIC_METHODS = (
    "bridgetree",
    "ablation_no_cluster",
    "ablation_bfs",
    "ablation_fixed_depth",
    "ablation_topk",
    "ablation_rho_dpp",
    "ablation_direct_path",
)

DEFAULT_MAIN_TABLE_METHODS = (
    "dense",
    "dense_rerank",
    "rfmem_familiarity",
    "rfmem_recollection",
    "rfmem",
    "cluster_prf",
    "bridgetree",
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
    initial_width: tuple[int, ...] = (8, 12)
    branch_width: tuple[int, ...] = (4, 8)
    search_budget: tuple[int, ...] = (64,)


@dataclass(frozen=True)
class TrainingExperimentConfig:
    seed: int = 42
    split: SplitProtocol = field(default_factory=SplitProtocol)
    schedule: TrainingSchedule = field(default_factory=TrainingSchedule)
    search_space: SearchSpace = field(default_factory=SearchSpace)
    diagnostic_methods: tuple[str, ...] = DEFAULT_DIAGNOSTIC_METHODS
    main_table_methods: tuple[str, ...] = DEFAULT_MAIN_TABLE_METHODS
    objective_metric: str = "auto"
    objective_mode: str = "max"
    bridge_gold_path: str | None = None
    validation_generate: bool = False
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
            not self.search_space.initial_width
            or not self.search_space.branch_width
            or not self.search_space.search_budget
        ):
            raise ValueError("training search space cannot be empty")
        if any(value <= 0 for value in self.search_space.initial_width + self.search_space.branch_width):
            raise ValueError("search widths must be positive")
        if any(value <= 0 for value in self.search_space.search_budget):
            raise ValueError("search budgets must be positive")
        if min(self.search_space.search_budget) < max(self.search_space.initial_width):
            raise ValueError("every search budget must be >= every first-hop width")
        if not self.diagnostic_methods or self.diagnostic_methods[0] != "bridgetree":
            raise ValueError("diagnostic_methods must start with bridgetree")
        unsupported = set(self.diagnostic_methods) - set(ABLATION_OPTIONS)
        if unsupported:
            raise ValueError(f"training diagnostics require tree-producing methods; unsupported: {sorted(unsupported)}")
        unsupported_main = set(self.main_table_methods) - set(METHODS)
        if unsupported_main:
            raise ValueError(f"unsupported main-table methods: {sorted(unsupported_main)}")
        if not self.main_table_methods:
            raise ValueError("main_table_methods cannot be empty")
        if "bridgetree" not in self.main_table_methods:
            raise ValueError("main_table_methods must include bridgetree")
        if self.objective_mode not in {"max", "min"}:
            raise ValueError("objective_mode must be max or min")
        external_metrics = {
            "auto",
            "outcome.answer_accuracy",
            "outcome.recall_at_k",
            "outcome.bridge_recall_at_k",
        }
        if self.objective_metric not in external_metrics:
            raise ValueError("tuning objective must be auto or an external outcome metric")
        if self.objective_metric == "outcome.answer_accuracy" and not self.validation_generate:
            raise ValueError("answer-accuracy tuning requires validation_generate=true")
        if self.objective_metric in {"outcome.recall_at_k", "outcome.bridge_recall_at_k"} and not self.bridge_gold_path:
            raise ValueError("recall tuning requires bridge_gold_path")


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
    initial_width_raw = search_raw.get("initial_width", search_raw.get("first_hop_width"))
    config = TrainingExperimentConfig(
        seed=int(raw.get("seed", 42)),
        split=SplitProtocol(**split_raw),
        schedule=TrainingSchedule(**schedule_raw),
        search_space=SearchSpace(
            initial_width=_tuple_ints(initial_width_raw, (8, 12)),
            branch_width=_tuple_ints(search_raw.get("branch_width"), (4, 8)),
            search_budget=_tuple_ints(search_raw.get("search_budget"), (64,)),
        ),
        diagnostic_methods=tuple(raw.get("diagnostic_methods", DEFAULT_DIAGNOSTIC_METHODS)),
        main_table_methods=tuple(raw.get("main_table_methods", DEFAULT_MAIN_TABLE_METHODS)),
        objective_metric=str(raw.get("objective_metric", "auto")),
        objective_mode=str(raw.get("objective_mode", "max")),
        bridge_gold_path=raw.get("bridge_gold_path"),
        validation_generate=bool(raw.get("validation_generate", False)),
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
        search_space.initial_width,
        search_space.branch_width,
        search_space.search_budget,
    ):
        candidate = replace(
            base,
            initial_width=first_hop,
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
        outcome_preview = summary.get("modules", {}).get("outcome", {})
        cost_preview = summary.get("modules", {}).get("cost", {}).get("ann_calls_core")
        print(
            f"[BridgeTree tune] phase={phase} trial={trial} step={step} method={method} "
            f"queries={summary.get('queries', 0)} outcome={outcome_preview} ann_calls_core={cost_preview}"
        )
        return event

    def write_comparison(self, context: Mapping[str, Any], value: Mapping[str, Any]) -> None:
        with (self.root / "module_effects.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**context, "full_minus_ablation": value}, ensure_ascii=False) + "\n")

    def write_failure(self, context: Mapping[str, Any], exc: Exception) -> None:
        with (self.root / "failures.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        **context,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


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
        self.reranker = RerankerClient(app_config.models.reranker)
        self.index_cache = IndexCache()

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
            memory_granularity=self.app_config.data.memory_granularity,
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
        context_key = (
            f"{example.shared_context_id}:{example.end_index}:"
            f"{self.app_config.data.memory_granularity}:{self.app_config.data.include_system_persona}"
        )
        index, index_build_ms, _cache_hit = self.index_cache.get(
            context_key,
            self.cache.fingerprint,
            self.app_config.retrieval.index_backend,
            [memory.memory_id for memory in memories],
            memory_vectors,
            self.app_config.retrieval.faiss_exclusion_margin,
        )
        tracker = CostTracker(SearchBudget.from_config(self.app_config.retrieval))
        retrieval_started = time.perf_counter()
        selected_ids, selected, diagnostics, bridge_result = retrieve_method(
            method,
            self.app_config,
            example,
            memories,
            query_vector,
            memory_vectors,
            reranker=self.reranker if method == "dense_rerank" else None,
            index=index,
            budget=tracker.budget,
            cost_tracker=tracker,
            index_build_ms=index_build_ms,
        )
        retrieval_seconds = time.perf_counter() - retrieval_started
        tracker = diagnostics.pop("_cost_tracker")
        selected = fit_context_budget(selected, self.app_config.models.generator.context_token_budget)
        retained_ids = {memory.memory_id for memory in selected}
        selected_ids = [memory_id for memory_id in selected_ids if memory_id in retained_ids]
        tracker.final_context_count = len(selected)
        tracker.final_context_tokens = context_token_count(selected)

        response = ""
        generation_seconds = 0.0
        accuracy = None
        parse_failure = None
        if generate:
            generation_started = time.perf_counter()
            response = self.generator.answer(example.query, selected, example.all_options)
            generation_seconds = time.perf_counter() - generation_started
            tracker.generation_ms = generation_seconds * 1000.0
            accuracy = answer_accuracy(response, example.correct_answer)
            parse_failure = answer_parse_failed(response)

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
        if bridge_result is not None:
            metrics = collect_metrics(
                bridge_result,
                query_vector,
                memory_vectors,
                self.app_config.retrieval,
                timings=timings,
                answer_accuracy_value=accuracy,
                recall_value=recall,
                bridge_recall_value=bridge_recall,
                parse_failure_value=parse_failure,
                gold_ids=gold_ids if gold_ids else None,
            )
        else:
            metrics = {name: {} for name in MODULE_NAMES}
            metrics["encoding"] = {
                "memory_count": float(len(memories)),
                "embedding_dimension": float(memory_vectors.shape[1]),
            }
            metrics["selection"] = {"selected_count": float(len(selected_ids))}
            metrics["search"] = {
                "ann_calls": float(tracker.ann_calls_core),
                "visited_nodes": float(tracker.cost_unique_count),
            }
            metrics["cost"] = {
                key: float(value) for key, value in tracker.snapshot().to_dict().items() if key != "stop_reason"
            }
            metrics["outcome"] = {}
            if accuracy is not None:
                metrics["outcome"]["answer_accuracy"] = accuracy
            if recall is not None:
                metrics["outcome"]["recall_at_k"] = recall
            if bridge_recall is not None:
                metrics["outcome"]["bridge_recall_at_k"] = bridge_recall
            if parse_failure is not None:
                metrics["outcome"]["parse_failure_rate"] = parse_failure
            metrics["timing"] = timings
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
        records = []
        for example in examples:
            try:
                records.append(self.evaluate_one(example, method, generate, context))
            except Exception as exc:
                self.writer.write_failure(
                    {**context, "method": method, "question_id": example.question_id},
                    exc,
                )
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


def _resolved_objective(config: TrainingExperimentConfig) -> str | None:
    if config.objective_metric != "auto":
        return config.objective_metric
    if config.validation_generate:
        return "outcome.answer_accuracy"
    if config.bridge_gold_path:
        return "outcome.recall_at_k"
    return None


def _optional_metric(summary: Mapping[str, Any], path: str | None) -> float | None:
    if path is None:
        return None
    try:
        return metric_value(summary, path)
    except KeyError:
        return None


def _cost_tuple(summary: Mapping[str, Any]) -> tuple[float, float, float]:
    return (
        metric_value(summary, "cost.ann_calls_core"),
        metric_value(summary, "cost.candidates_returned"),
        metric_value(summary, "cost.retrieval_core_ms"),
    )


def _is_better(
    score: float,
    cost: tuple[float, ...],
    best_score: float | None,
    best_cost: tuple[float, ...] | None,
    mode: str,
) -> bool:
    if best_score is None:
        return True
    if (mode == "max" and score > best_score + 1e-12) or (mode == "min" and score < best_score - 1e-12):
        return True
    return abs(score - best_score) <= 1e-12 and (best_cost is None or cost < best_cost)


def _cost_pareto_frontier(trials: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    points = []
    for trial in trials:
        summary = trial["validation"]["bridgetree"]
        points.append((trial, _cost_tuple(summary)))
    frontier = []
    for trial, cost in points:
        dominated = any(
            all(other_value <= value for other_value, value in zip(other_cost, cost))
            and any(other_value < value for other_value, value in zip(other_cost, cost))
            for other_trial, other_cost in points
            if other_trial["trial"] != trial["trial"]
        )
        if not dominated:
            frontier.append(
                {
                    "trial": trial["trial"],
                    "retrieval": trial["retrieval"],
                    "cost": {
                        "ann_calls_core": cost[0],
                        "candidates_returned": cost[1],
                        "retrieval_core_ms": cost[2],
                    },
                }
            )
    return frontier


def run_training_experiment(
    app_config: AppConfig,
    training_config: TrainingExperimentConfig,
    embedder: Embedder,
    examples: Sequence[PersonaMemExample] | None = None,
    output_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Tune retrieval configuration with periodic validation and no weight updates.

    Internal diagnostics are never eligible selection objectives. If neither
    generated validation outcomes nor independent gold are available, trials
    remain unranked, no test data is read, and no best config is written.
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

    root = Path(output_dir or training_config.output_dir) / f"tune_{time.time_ns()}"
    writer = TrainingMetricsWriter(root, training_config.keep_example_metrics)
    writer.write_json("training_config.json", asdict(training_config))
    combined_config = {
        "app": app_config.resolved_dict(),
        "tuning": asdict(training_config),
    }
    combined_payload = json.dumps(combined_config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    writer.write_json(
        "resolved_config.json",
        {
            "config_hash": hashlib.sha256(combined_payload.encode("utf-8")).hexdigest(),
            "config": combined_config,
        },
    )
    repository_root = Path(__file__).resolve().parents[2]
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    writer.write_json(
        "run_manifest.json",
        {
            "command": "tune",
            "git_commit": git_commit or None,
            "data_revision": PERSONAMEM_REVISION,
            "embedding_model": app_config.models.embedding.model,
            "generator_model": app_config.models.generator.model,
            "prompt_hash": generation_prompt_hash(),
            "seed": training_config.seed,
        },
    )
    (root / "failures.jsonl").touch()
    writer.write_json("split_manifest.json", _split_manifest(splits, training_config.seed))
    bridge_gold = load_bridge_gold(training_config.bridge_gold_path)
    trials = build_retrieval_trials(app_config.retrieval, training_config.search_space)
    objective_metric = _resolved_objective(training_config)

    trial_summaries = []
    best_trial = None
    best_score = None
    best_cost: tuple[float, ...] | None = None
    best_app_config = None
    best_train_metrics = None
    best_validation_metrics = None

    for trial_index, retrieval_config in enumerate(trials, start=1):
        current_app = replace(app_config, retrieval=retrieval_config)
        evaluator = TrainingEvaluator(current_app, embedder, writer, bridge_gold)
        train_records: List[Mapping[str, Mapping[str, float]]] = []
        latest_probe_by_method: Dict[str, Any] = {}
        for step, example in enumerate(train_examples, start=1):
            try:
                train_records.append(
                    evaluator.evaluate_one(
                        example,
                        "bridgetree",
                        False,
                        {"phase": "train", "trial": trial_index, "step": step},
                    )
                )
            except Exception as exc:
                writer.write_failure(
                    {
                        "phase": "train",
                        "trial": trial_index,
                        "step": step,
                        "method": "bridgetree",
                        "question_id": example.question_id,
                    },
                    exc,
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
                    training_config.validation_generate,
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
                training_config.validation_generate,
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
        objective = _optional_metric(validation_by_method["bridgetree"], objective_metric)
        cost = _cost_tuple(validation_by_method["bridgetree"])
        train_summary = aggregate_module_metrics(train_records)
        trial_summary = {
            "trial": trial_index,
            "retrieval": asdict(retrieval_config),
            "objective": objective,
            "objective_metric": objective_metric,
            "tie_break_cost": {
                "ann_calls_core": cost[0],
                "candidates_returned": cost[1],
                "retrieval_core_ms": cost[2],
            },
            "train": train_summary,
            "validation": validation_by_method,
            "last_periodic_probe": latest_probe_by_method,
        }
        trial_summaries.append(trial_summary)
        if objective is not None and _is_better(
            objective,
            cost,
            best_score,
            best_cost,
            training_config.objective_mode,
        ):
            best_trial = trial_index
            best_score = objective
            best_cost = cost
            best_app_config = current_app
            best_train_metrics = train_summary
            best_validation_metrics = validation_by_method
        writer.write_json("trials.json", trial_summaries)

    pareto_frontier = _cost_pareto_frontier(trial_summaries)
    writer.write_json(
        "pareto_frontier.json",
        {
            "quality_axis": objective_metric,
            "note": (
                "Cost-only frontier; configurations are intentionally unranked because no external validation "
                "outcome is available."
                if objective_metric is None
                else "External validation outcome is used for selection; costs are unweighted tie-breakers."
            ),
            "trials": pareto_frontier,
        },
    )
    if best_app_config is None or best_trial is None:
        final_summary = {
            "optimization_kind": "training_free_configuration_tuning",
            "run_dir": str(root),
            "selection_status": "unselected_no_external_validation_outcome",
            "best_trial": None,
            "best_retrieval_config": None,
            "objective_metric": objective_metric,
            "test_metrics": {},
            "trial_count": len(trials),
            "pareto_frontier": pareto_frontier,
        }
        writer.write_json("final_summary.json", final_summary)
        return final_summary
    final_evaluator = TrainingEvaluator(best_app_config, embedder, writer, bridge_gold)
    final_test_by_method: Dict[str, Any] = {}
    for method in training_config.main_table_methods:
        test_summary = final_evaluator.evaluate_set(
            test_examples,
            method,
            training_config.final_generate,
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
        "optimization_kind": "training_free_configuration_tuning",
        "run_dir": str(root),
        "best_trial": best_trial,
        "best_retrieval_config": asdict(best_app_config.retrieval),
        "objective_metric": objective_metric,
        "objective_mode": training_config.objective_mode,
        "best_validation_objective": best_score,
        "train_metrics": best_train_metrics,
        "validation_metrics": best_validation_metrics,
        "test_metrics": final_test_by_method,
        "test_module_effects_full_minus_ablation": effects,
        "trial_count": len(trials),
        "pareto_frontier": pareto_frontier,
        "selection_status": "selected_on_external_validation_outcome",
    }
    writer.write_json("final_summary.json", final_summary)
    writer.write_json("best_config.json", {"retrieval": asdict(best_app_config.retrieval)})
    return final_summary


# Public tuning names; legacy training names remain import-compatible.
TuningExperimentConfig = TrainingExperimentConfig
load_tuning_config = load_training_config
run_tuning_experiment = run_training_experiment
