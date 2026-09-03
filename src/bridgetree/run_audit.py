from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .config import RetrievalConfig
from .module_metrics import MODULE_NAMES
from .personamem import PERSONAMEM_REVISION, PERSONAMEM_SOURCE_SHA256
from .training import (
    DEFAULT_MAIN_TABLE_METHODS,
    FORMAL_32K_PARTITION_QUERIES,
    FORMAL_32K_SEARCH_SPACE,
    FORMAL_32K_SEED,
    FORMAL_32K_SPLIT,
)


def _question_hash(question_ids: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(question_ids).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_json(root: Path, name: str, errors: list[str], default: Any) -> Any:
    path = root / name
    if not path.is_file():
        errors.append(f"missing required artifact: {name}")
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON artifact {name}: {exc}")
        return default


def _load_jsonl(root: Path, name: str, errors: list[str]) -> list[Dict[str, Any]]:
    path = root / name
    if not path.is_file():
        errors.append(f"missing required artifact: {name}")
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSONL artifact {name}:{line_number}: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"non-object JSONL record {name}:{line_number}")
            continue
        records.append(value)
    return records


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _summary_complete(
    summary: Mapping[str, Any],
    expected_queries: int,
    expected_hash: str,
    label: str,
    errors: list[str],
) -> None:
    _check(summary.get("queries") == expected_queries, f"{label}: aggregate query count mismatch", errors)
    _check(summary.get("attempted_queries") == expected_queries, f"{label}: attempted query count mismatch", errors)
    _check(summary.get("successful_queries") == expected_queries, f"{label}: successful query count mismatch", errors)
    _check(summary.get("failed_queries") == 0, f"{label}: failed_queries is not zero", errors)
    _check(summary.get("failure_rate") == 0.0, f"{label}: failure_rate is not zero", errors)
    _check(
        summary.get("attempted_question_id_sha256") == expected_hash,
        f"{label}: attempted question hash mismatch",
        errors,
    )
    _check(
        summary.get("successful_question_id_sha256") == expected_hash,
        f"{label}: successful question hash mismatch",
        errors,
    )


def audit_tuning_run(
    run_dir: str | Path,
    *,
    require_full_32k: bool = False,
    max_parse_failure_rate: float = 0.05,
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """Independently re-read and validate a completed tuning run's persisted artifacts."""
    if not 0.0 <= max_parse_failure_rate <= 1.0:
        raise ValueError("max_parse_failure_rate must be in [0, 1]")
    root = Path(run_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        raise FileNotFoundError(f"tuning run directory does not exist: {root}")

    required_plain = ("metrics.csv", "pareto_frontier.json")
    for name in required_plain:
        _check((root / name).is_file(), f"missing required artifact: {name}", errors)
    resolved = _load_json(root, "resolved_config.json", errors, {})
    training_config = _load_json(root, "training_config.json", errors, {})
    run_manifest = _load_json(root, "run_manifest.json", errors, {})
    split_manifest = _load_json(root, "split_manifest.json", errors, {})
    trials = _load_json(root, "trials.json", errors, [])
    final = _load_json(root, "final_summary.json", errors, {})
    best_config = _load_json(root, "best_config.json", errors, {})
    run_status = _load_json(root, "run_status.json", errors, {})
    progress = _load_json(root, "progress.json", errors, {})
    failures = _load_jsonl(root, "failures.jsonl", errors)
    events = _load_jsonl(root, "events.jsonl", errors)
    examples = _load_jsonl(root, "example_metrics.jsonl", errors)

    combined = resolved.get("config", {}) if isinstance(resolved, dict) else {}
    app = combined.get("app", {}) if isinstance(combined, dict) else {}
    tuning = combined.get("tuning", {}) if isinstance(combined, dict) else {}
    data = app.get("data", {}) if isinstance(app, dict) else {}
    models = app.get("models", {}) if isinstance(app, dict) else {}
    generator_config = models.get("generator", {}) if isinstance(models, dict) else {}
    context_token_budget = int(generator_config.get("context_token_budget", 0) or 0)
    split_data = {name: split_manifest.get(name, {}) for name in ("train", "validation", "test")}
    validation_queries = int(split_data["validation"].get("queries", -1))
    test_queries = int(split_data["test"].get("queries", -1))
    validation_hash = str(split_data["validation"].get("question_id_sha256", ""))
    test_hash = str(split_data["test"].get("question_id_sha256", ""))
    main_methods = tuple(tuning.get("main_table_methods", ()))
    diagnostic_methods = tuple(tuning.get("diagnostic_methods", ()))

    _check(run_status.get("status") == "completed", "run_status is not completed", errors)
    _check(run_status.get("failure_count") == 0, "run_status failure_count is not zero", errors)
    _check(not failures, f"failures.jsonl contains {len(failures)} records", errors)
    _check(final.get("selection_status") == "selected_on_external_validation_outcome", "selection failed", errors)
    _check(final.get("best_trial") is not None, "best_trial is missing", errors)
    _check(final.get("best_retrieval_config") == best_config.get("retrieval"), "best config mismatch", errors)
    configured_objective = tuning.get("objective_metric")
    _check(
        configured_objective == "auto" or final.get("objective_metric") == configured_objective,
        "final objective metric differs from tuning config",
        errors,
    )
    _check(progress.get("status") == "completed", "progress.json is not completed", errors)
    _check(progress.get("phase") == "completed", "progress.json terminal phase mismatch", errors)
    _check(progress.get("best_trial") == final.get("best_trial"), "progress best trial mismatch", errors)
    _check(
        progress.get("selection_status") == final.get("selection_status"),
        "progress selection status mismatch",
        errors,
    )
    _check(run_status.get("best_trial") == final.get("best_trial"), "run status best trial mismatch", errors)
    _check(
        run_status.get("selection_status") == final.get("selection_status"),
        "run status selection mismatch",
        errors,
    )
    _check(run_manifest.get("command") == "tune", "run manifest command is not tune", errors)
    _check(
        run_manifest.get("optimization_kind") == "training_free_configuration_tuning",
        "run manifest optimization kind mismatch",
        errors,
    )
    _check(run_manifest.get("data_revision") == PERSONAMEM_REVISION, "run manifest data revision mismatch", errors)
    _check(run_manifest.get("data_split") == data.get("split"), "run manifest data split mismatch", errors)
    _check(run_manifest.get("validation_queries") == validation_queries, "manifest validation count mismatch", errors)
    _check(run_manifest.get("test_queries") == test_queries, "manifest test count mismatch", errors)
    _check(run_manifest.get("trial_count") == len(trials), "manifest trial count mismatch", errors)
    _check(final.get("trial_count") == len(trials), "final trial count mismatch", errors)
    _check(
        final.get("evaluated_validation_queries") == validation_queries,
        "final validation query count mismatch",
        errors,
    )
    _check(final.get("evaluated_test_queries") == test_queries, "final test query count mismatch", errors)

    combined_payload = json.dumps(combined, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected_config_hash = hashlib.sha256(combined_payload.encode("utf-8")).hexdigest()
    _check(resolved.get("config_hash") == expected_config_hash, "resolved config hash mismatch", errors)

    personas = [set(split_data[name].get("personas", ())) for name in ("train", "validation", "test")]
    _check(not personas[0] & personas[1], "train/validation persona leakage", errors)
    _check(not personas[0] & personas[2], "train/test persona leakage", errors)
    _check(not personas[1] & personas[2], "validation/test persona leakage", errors)
    partition_queries = sum(int(split_data[name].get("queries", -1)) for name in ("train", "validation", "test"))
    _check(run_manifest.get("dataset_queries") == partition_queries, "manifest dataset query count mismatch", errors)
    _check(
        run_manifest.get("train_queries_reserved") == split_data["train"].get("queries"),
        "manifest train query count mismatch",
        errors,
    )

    if require_full_32k:
        _check(data.get("split") == "32k", "formal audit requires data.split=32k", errors)
        _check(data.get("include_system_persona") is True, "formal audit requires the system persona", errors)
        _check(
            data.get("memory_granularity") == "user_assistant_pair",
            "formal audit requires user-assistant-pair memories",
            errors,
        )
        _check(
            run_manifest.get("source_sha256") == PERSONAMEM_SOURCE_SHA256["32k"],
            "formal audit requires the pinned official source checksums",
            errors,
        )
        _check(app.get("seed") == FORMAL_32K_SEED, "formal audit requires app seed=42", errors)
        _check(tuning.get("seed") == FORMAL_32K_SEED, "formal audit requires tuning seed=42", errors)
        _check(
            tuning.get("split")
            == {
                "train_ratio": FORMAL_32K_SPLIT.train_ratio,
                "validation_ratio": FORMAL_32K_SPLIT.validation_ratio,
                "test_ratio": FORMAL_32K_SPLIT.test_ratio,
            },
            "formal audit requires the pinned persona split",
            errors,
        )
        _check(len(trials) == 16, "formal audit requires exactly 16 trials", errors)
        _check(
            validation_queries == FORMAL_32K_PARTITION_QUERIES["validation"],
            "formal audit requires 84 validation queries",
            errors,
        )
        _check(
            test_queries == FORMAL_32K_PARTITION_QUERIES["test"],
            "formal audit requires 73 test queries",
            errors,
        )
        _check(main_methods == DEFAULT_MAIN_TABLE_METHODS, "formal audit requires all seven ordered methods", errors)
        _check(tuning.get("diagnostic_methods") == ["bridgetree"], "formal audit requires one search method", errors)
        _check(tuning.get("keep_example_metrics") is True, "formal audit requires example metrics", errors)
        _check(tuning.get("validation_generate") is True, "formal validation generation is disabled", errors)
        _check(tuning.get("final_generate") is True, "formal final generation is disabled", errors)
        _check(tuning.get("fail_on_evaluation_error") is True, "formal strict failure handling is disabled", errors)
        _check(final.get("objective_metric") == "outcome.answer_accuracy", "unexpected objective metric", errors)
        formal_retrieval = asdict(RetrievalConfig())
        actual_retrieval = dict(app.get("retrieval", {}))
        for tuned_name in ("initial_width", "branch_width", "search_budget"):
            formal_retrieval.pop(tuned_name)
            actual_retrieval.pop(tuned_name, None)
        _check(
            actual_retrieval == formal_retrieval,
            "formal audit requires the pinned retrieval protocol outside the search axes",
            errors,
        )
        schedule = tuning.get("schedule", {})
        _check(schedule.get("max_validation_queries") is None, "formal validation is limited", errors)
        _check(schedule.get("max_test_queries") is None, "formal test is limited", errors)
        _check(final.get("evaluated_validation_queries") == 84, "final validation count mismatch", errors)
        _check(final.get("evaluated_test_queries") == 73, "final test count mismatch", errors)

    trial_map: Dict[int, Mapping[str, Any]] = {}
    observed_space = set()
    for trial in trials if isinstance(trials, list) else []:
        trial_index = int(trial.get("trial", -1))
        retrieval = trial.get("retrieval", {})
        _check(trial_index not in trial_map, f"duplicate trial index: {trial_index}", errors)
        trial_map[trial_index] = retrieval
        observed_space.add(
            (retrieval.get("initial_width"), retrieval.get("branch_width"), retrieval.get("search_budget"))
        )
        validation = trial.get("validation", {})
        _check(
            set(validation) == set(diagnostic_methods),
            f"validation method set mismatch: trial {trial_index}",
            errors,
        )
        for method in diagnostic_methods:
            summary = validation.get(method, {})
            label = f"validation trial {trial_index} method {method}"
            _summary_complete(summary, validation_queries, validation_hash, label, errors)
            if tuning.get("validation_generate") is True:
                parse_rate = summary.get("modules", {}).get("outcome", {}).get("parse_failure_rate")
                if parse_rate is None or float(parse_rate) > max_parse_failure_rate:
                    errors.append(f"{label}: parse failure rate exceeds threshold")

    search_space = tuning.get("search_space", {})
    expected_space = set(
        product(
            search_space.get("initial_width", ()),
            search_space.get("branch_width", ()),
            search_space.get("search_budget", ()),
        )
    )
    _check(observed_space == expected_space, "observed trial grid does not match configured search space", errors)
    _check(set(trial_map) == set(range(1, len(trials) + 1)), "trial indices are not contiguous", errors)
    if require_full_32k:
        formal_space = {
            (initial_width, branch_width, search_budget)
            for initial_width, branch_width, search_budget in product(
                FORMAL_32K_SEARCH_SPACE.initial_width,
                FORMAL_32K_SEARCH_SPACE.branch_width,
                FORMAL_32K_SEARCH_SPACE.search_budget,
            )
        }
        _check(expected_space == formal_space, "formal audit requires the pinned 2x2x4 search space", errors)

    best_trial = int(final.get("best_trial", -1))
    _check(trial_map.get(best_trial) == best_config.get("retrieval"), "best trial retrieval config mismatch", errors)
    test_metrics = final.get("test_metrics", {})
    _check(set(test_metrics) == set(main_methods), "final method set mismatch", errors)
    _check(final.get("common_test_question_id_sha256") == test_hash, "final common test hash mismatch", errors)
    for method in main_methods:
        summary = test_metrics.get(method, {})
        _summary_complete(summary, test_queries, test_hash, f"test method {method}", errors)
        if tuning.get("final_generate") is True:
            parse_rate = summary.get("modules", {}).get("outcome", {}).get("parse_failure_rate")
            if parse_rate is None or float(parse_rate) > max_parse_failure_rate:
                errors.append(f"test method {method}: parse failure rate exceeds threshold")

    expected_event_groups = {
        *(('validation', trial_index, method) for trial_index in trial_map for method in diagnostic_methods),
        *(("test", best_trial, method) for method in main_methods),
    }
    event_counts = Counter(
        (str(event.get("phase", "")), int(event.get("trial", -1)), str(event.get("method", "")))
        for event in events
    )
    _check(set(event_counts) == expected_event_groups, "event phase/trial/method set mismatch", errors)
    _check(all(count == 1 for count in event_counts.values()), "duplicate aggregate events are present", errors)
    _check(len(events) == len(expected_event_groups), "aggregate event count mismatch", errors)
    _check(
        [event.get("event_id") for event in events] == list(range(1, len(events) + 1)),
        "event IDs are not contiguous",
        errors,
    )
    _check(
        not any(event.get("phase") in {"train", "train_progress", "validation_probe"} for event in events),
        "inert train/probe events are present",
        errors,
    )

    expected_example_count = (
        len(trials) * len(diagnostic_methods) * validation_queries + len(main_methods) * test_queries
    )
    _check(len(examples) == expected_example_count, "example_metrics row count mismatch", errors)
    sequence_by_group: Dict[tuple[str, int, str], list[str]] = defaultdict(list)
    example_keys = set()
    max_unique_budget_ratio = 0.0
    max_parse_rate = 0.0
    for row_number, record in enumerate(examples, start=1):
        phase = str(record.get("phase", ""))
        trial_index = int(record.get("trial", -1))
        method = str(record.get("method", ""))
        question_id = str(record.get("question_id", ""))
        key = (phase, trial_index, method, question_id)
        _check(key not in example_keys, f"duplicate example metric key at row {row_number}", errors)
        example_keys.add(key)
        sequence_by_group[(phase, trial_index, method)].append(question_id)
        retrieval = trial_map.get(trial_index, {})
        modules = record.get("modules", {})
        _check(set(modules) == set(MODULE_NAMES), f"module set mismatch at row {row_number}", errors)
        cost = modules.get("cost", {})
        outcome = modules.get("outcome", {})
        budget = int(retrieval.get("search_budget", 0) or 0)
        visited = float(cost.get("unique_visited_nodes", -1))
        if budget > 0:
            max_unique_budget_ratio = max(max_unique_budget_ratio, visited / budget)
        _check(budget > 0 and 0 <= visited <= budget, f"unique-node budget violation at row {row_number}", errors)
        context_size = int(retrieval.get("context_size", 0) or 0)
        selected_ids = record.get("selected_memory_ids", ())
        final_count = float(cost.get("final_context_count", -1))
        final_tokens = float(cost.get("final_context_tokens", -1))
        _check(
            context_size > 0 and len(selected_ids) <= context_size and 0 <= final_count <= context_size,
            f"final context-size violation at row {row_number}",
            errors,
        )
        _check(
            context_token_budget > 0 and 0 <= final_tokens <= context_token_budget,
            f"final context-token budget violation at row {row_number}",
            errors,
        )
        _check(len(selected_ids) == len(set(selected_ids)), f"duplicate selected memory ID at row {row_number}", errors)
        _check(final_count == len(selected_ids), f"final context count mismatch at row {row_number}", errors)
        if "parse_failure_rate" in outcome:
            parse_failure = float(outcome["parse_failure_rate"])
            max_parse_rate = max(max_parse_rate, parse_failure)

    for trial_index in trial_map:
        for method in diagnostic_methods:
            sequence = sequence_by_group.get(("validation", trial_index, method), [])
            label = f"validation trial {trial_index} method {method}"
            _check(len(sequence) == validation_queries, f"{label}: example count mismatch", errors)
            _check(_question_hash(sequence) == validation_hash, f"{label}: example hash mismatch", errors)
    for method in main_methods:
        sequence = sequence_by_group.get(("test", best_trial, method), [])
        _check(len(sequence) == test_queries, f"test example count mismatch: {method}", errors)
        _check(_question_hash(sequence) == test_hash, f"test example hash mismatch: {method}", errors)

    for module in MODULE_NAMES:
        module_records = _load_jsonl(root, f"modules/{module}.jsonl", errors)
        _check(len(module_records) == len(events), f"module event count mismatch: {module}", errors)
        for event, module_record in zip(events, module_records):
            identity = ("event_id", "phase", "trial", "step", "method")
            _check(
                all(module_record.get(name) == event.get(name) for name in identity),
                f"module event identity mismatch: {module} event {event.get('event_id')}",
                errors,
            )
    if (root / "metrics.csv").is_file():
        with (root / "metrics.csv").open("r", encoding="utf-8", newline="") as handle:
            metric_rows = sum(1 for _row in csv.reader(handle)) - 1
        _check(metric_rows > 0, "metrics.csv has no metric rows", errors)
    temporary_files = sorted(str(path.relative_to(root)) for path in root.rglob("*.tmp"))
    _check(not temporary_files, f"temporary artifacts remain: {temporary_files}", errors)

    if max_parse_rate > 0.0:
        warnings.append(f"at least one individual answer parse failed; max indicator={max_parse_rate}")
    report = {
        "status": "passed" if not errors else "failed",
        "audited_at": time.time(),
        "run_dir": str(root),
        "require_full_32k": require_full_32k,
        "max_parse_failure_rate": max_parse_failure_rate,
        "errors": errors,
        "warnings": warnings,
        "evidence": {
            "trial_count": len(trials),
            "event_count": len(events),
            "example_count": len(examples),
            "validation_queries_per_trial": validation_queries,
            "test_queries_per_method": test_queries,
            "final_method_count": len(main_methods),
            "failure_record_count": len(failures),
            "max_unique_budget_ratio": max_unique_budget_ratio,
            "max_individual_parse_failure": max_parse_rate,
            "common_test_question_id_sha256": test_hash,
        },
        "training_config_matches_resolved": training_config == tuning,
    }
    _check(report["training_config_matches_resolved"], "training_config.json differs from resolved tuning", errors)
    report["status"] = "passed" if not errors else "failed"
    report["errors"] = errors
    _atomic_json(root / "completion_audit.json", report)
    if errors and raise_on_error:
        audit_path = root / "completion_audit.json"
        raise RuntimeError(f"tuning completion audit failed with {len(errors)} errors: {audit_path}")
    return report
