from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from .aggregation import aggregate_runs
from .clients import build_embedder
from .config import apply_runtime_overrides, load_config
from .experiment import METHODS, run_personamem_experiment
from .offline_validation import validate_full_32k_offline
from .personamem import PERSONAMEM_REPO, PERSONAMEM_REVISION, prepare_split
from .run_audit import audit_tuning_run
from .server_bundle import build_server_bundle, verify_bundle_offline_launcher
from .smoke import run_synthetic_smoke
from .training import (
    EFFECT_FIRST_VALIDATION_METHODS,
    load_tuning_config,
    preflight_tuning,
    run_effect_first_validation,
    run_tuning_experiment,
)


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "BridgeTree/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    temporary.replace(destination)


def download_personamem(raw_dir: str | Path, splits: list[str]) -> None:
    root = Path(raw_dir)
    for split in splits:
        for filename in (f"questions_{split}.csv", f"shared_contexts_{split}.jsonl"):
            destination = root / filename
            if destination.exists() and destination.stat().st_size > 0:
                print(f"exists: {destination}")
                continue
            url = (
                f"https://huggingface.co/datasets/{PERSONAMEM_REPO}/resolve/"
                f"{PERSONAMEM_REVISION}/{filename}?download=true"
            )
            print(f"downloading {filename} -> {destination}")
            _download(url, destination)


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--initial-width", type=int)
    parser.add_argument("--branch-width", type=int)
    parser.add_argument("--context-size", type=int)
    parser.add_argument("--search-budget", type=int)
    parser.add_argument("--max-ann-calls", type=int)
    parser.add_argument("--max-candidate-exposure", type=int)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--cluster-mode", choices=("none", "fixed", "effective_rank"))
    parser.add_argument("--cluster-count", type=int)
    parser.add_argument("--max-clusters", type=int)
    parser.add_argument("--min-cluster-size", type=int)
    parser.add_argument("--search-order", choices=("best_first", "bfs"))
    parser.add_argument("--feature-mode", choices=("rho", "path_conditioned"))
    parser.add_argument("--selection-mode", choices=("rho_topk", "mmr", "rho_logdet", "path_logdet"))
    parser.add_argument("--stop-mode", choices=("budget", "certificate_or_budget"))
    parser.add_argument("--diagnostic-level", choices=("off", "light", "full"))
    parser.add_argument("--root-anchor-weight", type=float)
    parser.add_argument("--dense-pool-width", type=int)
    parser.add_argument("--anchor-width", type=int)
    parser.add_argument("--expand-branch-count", type=int)
    parser.add_argument("--branch-overfetch-width", type=int)
    parser.add_argument("--branch-keep-width", type=int)
    parser.add_argument("--probe-mode", choices=("centroid", "query_anchor"))
    parser.add_argument("--path-filter", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument(
        "--rerank-use-options",
        dest="use_answer_options",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--rerank-include-time",
        dest="include_time_metadata",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--bridge-query-instruction")
    parser.add_argument("--final-rerank-instruction")
    parser.add_argument("--path-filter-instruction")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--index-backend", choices=("exact", "faiss"))
    parser.add_argument("--memory-granularity", choices=("user_only", "user_assistant_pair"))
    parser.add_argument(
        "--include-system-persona",
        action=argparse.BooleanOptionalAction,
        default=None,
    )


def _resolved_config(args: argparse.Namespace):
    return apply_runtime_overrides(load_config(args.config, args.override_config), vars(args))


def _resolved_tuning_config(args: argparse.Namespace):
    tuning = load_tuning_config(args.tuning_config)
    search_changes = {}
    if args.initial_width is not None:
        search_changes["initial_width"] = (args.initial_width,)
    if args.branch_width is not None:
        search_changes["branch_width"] = (args.branch_width,)
    if args.search_budget is not None:
        search_changes["search_budget"] = (args.search_budget,)
    if search_changes:
        tuning = replace(tuning, search_space=replace(tuning.search_space, **search_changes))
    if args.seed is not None:
        tuning = replace(tuning, seed=args.seed)
    tuning.validate()
    return tuning


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridgetree")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download-personamem", help="Download the pinned official PersonaMem-v1 files")
    download.add_argument("--raw-dir", default="data/raw/personamem-v1")
    download.add_argument("--split", action="append", choices=("32k", "128k", "1M"), default=[])

    prepare = subparsers.add_parser("prepare-personamem", help="Validate and normalize a PersonaMem split")
    prepare.add_argument("--raw-dir", default="data/raw/personamem-v1")
    prepare.add_argument("--processed-dir", default="data/processed/personamem-v1")
    prepare.add_argument("--split", choices=("32k", "128k", "1M"), default="32k")

    configured_data = subparsers.add_parser(
        "prepare-configured-data",
        help="Download, pinned-checksum, and prepare formal PersonaMem 32K data from app config",
    )
    configured_data.add_argument("--config", default="configs/default.yaml")
    configured_data.add_argument("--override-config")
    configured_data.add_argument("--download-missing", action=argparse.BooleanOptionalAction, default=True)

    run = subparsers.add_parser("run", help="Run a PersonaMem retrieval/e2e experiment")
    run.add_argument("--config", default="configs/default.yaml")
    run.add_argument("--override-config")
    run.add_argument("--method", choices=METHODS, default="bridgetree")
    run.add_argument("--limit", type=int)
    run.add_argument("--generate", action=argparse.BooleanOptionalAction, default=False)
    run.add_argument("--bridge-gold", help="Independent JSONL gold memory annotations")
    run.add_argument("--output-dir")
    run.add_argument("--run-label")
    _add_runtime_arguments(run)

    sweep = subparsers.add_parser("sweep", help="Run required methods over one or more search budgets")
    sweep.add_argument("--config", default="configs/default.yaml")
    sweep.add_argument("--override-config")
    sweep.add_argument("--method", action="append", choices=METHODS, default=[])
    sweep.add_argument("--budget", action="append", type=int, default=[])
    sweep.add_argument(
        "--budget-protocol",
        choices=("matched_ann_calls", "matched_candidate_exposure"),
        default="matched_candidate_exposure",
    )
    sweep.add_argument("--limit", type=int)
    sweep.add_argument("--generate", action=argparse.BooleanOptionalAction, default=False)
    sweep.add_argument("--bridge-gold")
    sweep.add_argument("--output-dir")
    _add_runtime_arguments(sweep)

    tune = subparsers.add_parser(
        "tune",
        aliases=["train"],
        help="Tune retrieval configuration with external validation outcomes",
    )
    tune.add_argument("--config", default="configs/default.yaml")
    tune.add_argument("--override-config")
    tune.add_argument("--tuning-config", "--training-config", dest="tuning_config", default="configs/train.yaml")
    tune.add_argument("--output-dir")
    tune.add_argument(
        "--audit-full-32k",
        action="store_true",
        help="Require the persisted run to pass the independent formal 32K completion audit",
    )
    tune.add_argument("--max-parse-failure-rate", type=float, default=0.05)
    _add_runtime_arguments(tune)

    preflight = subparsers.add_parser(
        "preflight-tuning",
        help="Validate tuning data, protocol, search space, and model services",
    )
    preflight.add_argument("--config", default="configs/default.yaml")
    preflight.add_argument("--override-config")
    preflight.add_argument("--tuning-config", "--training-config", dest="tuning_config", default="configs/train.yaml")
    preflight.add_argument("--check-services", action=argparse.BooleanOptionalAction, default=False)
    preflight.add_argument("--require-full-32k", action="store_true")
    _add_runtime_arguments(preflight)

    check = subparsers.add_parser("check-ascend", help="Report Ascend/PyTorch runtime availability")
    check.add_argument("--strict", action="store_true")

    synthetic = subparsers.add_parser("smoke-synthetic", help="Run an offline q-to-m1-to-m2 retrieval smoke test")
    synthetic.add_argument("--output-dir", default="outputs/smoke")

    aggregate = subparsers.add_parser("aggregate", help="Aggregate multi-seed runs with paired bootstrap CIs")
    aggregate.add_argument("--input-dir", required=True)
    aggregate.add_argument("--reference-label", default="core")
    aggregate.add_argument("--bootstrap-seed", type=int, default=42)
    aggregate.add_argument("--bootstrap-resamples", type=int, default=2000)

    package = subparsers.add_parser(
        "package-server",
        help="Build and verify a portable server bundle containing formal 32K data",
    )
    package.add_argument("--output-dir", default="dist/server")
    package.add_argument(
        "--verify-offline-launcher",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    offline_full = subparsers.add_parser(
        "validate-full-32k-offline",
        help="Run the complete 32K scheduler with explicit fake local clients",
    )
    offline_full.add_argument("--config", default="configs/default.yaml")
    offline_full.add_argument("--tuning-config", default="configs/train.yaml")
    offline_full.add_argument("--output-dir", default="outputs/offline-full-32k-validation")

    effect = subparsers.add_parser(
        "validate-effect-first",
        help="Run the predefined reranker-guided method matrix on validation personas only",
    )
    effect.add_argument("--config", default="configs/default.yaml")
    effect.add_argument("--override-config", default="configs/personamem32k_effect_first.yaml")
    effect.add_argument("--method", action="append", choices=EFFECT_FIRST_VALIDATION_METHODS, default=[])
    effect.add_argument("--output-dir", default="outputs/effect-first-validation")
    effect.add_argument("--limit", type=int)
    effect.add_argument("--generate", action=argparse.BooleanOptionalAction, default=True)
    _add_runtime_arguments(effect)

    audit = subparsers.add_parser(
        "audit-tuning-run",
        help="Independently validate a completed tuning run from its persisted artifacts",
    )
    audit.add_argument("--run-dir", required=True)
    audit.add_argument("--require-full-32k", action="store_true")
    audit.add_argument("--max-parse-failure-rate", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download-personamem":
        download_personamem(args.raw_dir, args.split or ["32k"])
        return 0
    if args.command == "prepare-personamem":
        print(json.dumps(prepare_split(args.raw_dir, args.processed_dir, args.split), ensure_ascii=False, indent=2))
        return 0
    if args.command == "prepare-configured-data":
        config = load_config(args.config, args.override_config)
        split = config.data.split
        if split != "32k":
            raise ValueError("prepare-configured-data is the pinned formal 32K data gate")
        raw_root = Path(config.data.raw_dir)
        source_paths = (
            raw_root / f"questions_{split}.csv",
            raw_root / f"shared_contexts_{split}.jsonl",
        )
        if any(not path.is_file() or path.stat().st_size <= 0 for path in source_paths):
            if not args.download_missing:
                raise FileNotFoundError(f"PersonaMem {split} source is missing and download is disabled")
            download_personamem(raw_root, [split])
        result = prepare_split(
            raw_root,
            config.data.processed_dir,
            split,
            verify_pinned_source=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        config = _resolved_config(args)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        result = run_personamem_experiment(
            config,
            args.method,
            embedder,
            limit=args.limit,
            generate=args.generate,
            bridge_gold_path=args.bridge_gold,
            output_dir=args.output_dir,
            run_label=args.run_label,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "sweep":
        config = _resolved_config(args)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        methods = args.method or list(METHODS)
        if args.budget:
            budgets = args.budget
        elif args.budget_protocol == "matched_ann_calls":
            budgets = [config.retrieval.max_ann_calls or 1]
        else:
            budgets = [config.retrieval.max_candidate_exposure or config.retrieval.search_budget]
        sweep_root = Path(args.output_dir or config.runtime.output_dir) / f"sweep_{time.time_ns()}"
        sweep_root.mkdir(parents=True, exist_ok=False)
        runs = []
        static_methods = {
            "dense",
            "dense_rerank",
            "dense_rerank_20",
            "dense_rerank_28",
            "full_pool_rerank",
            "rfmem_familiarity",
        }
        for method in methods:
            method_budgets = [None] if method in static_methods else budgets
            for budget in method_budgets:
                current = config
                if budget is not None and args.budget_protocol == "matched_ann_calls":
                    if budget <= 0:
                        raise ValueError("matched ANN-call budgets must be positive")
                    current = replace(config, retrieval=replace(config.retrieval, max_ann_calls=budget))
                elif budget is not None:
                    if budget < max(config.retrieval.initial_width, config.retrieval.context_size):
                        raise ValueError("candidate-exposure budgets must cover initial_width and context_size")
                    current = replace(
                        config,
                        retrieval=replace(config.retrieval, max_candidate_exposure=budget),
                    )
                result = run_personamem_experiment(
                    current,
                    method,
                    embedder,
                    limit=args.limit,
                    generate=args.generate,
                    bridge_gold_path=args.bridge_gold,
                    output_dir=sweep_root,
                )
                actual_cost = result["summary"].get("cost", {}).get("mean", {})
                runs.append(
                    {
                        "budget": budget,
                        "budget_protocol": "actual_cost" if budget is None else args.budget_protocol,
                        "actual_cost": actual_cost,
                        **result,
                    }
                )
        manifest = {
            "methods": methods,
            "budget_protocol": args.budget_protocol,
            "budgets": budgets,
            "runs": runs,
        }
        with (sweep_root / "sweep_summary.json").open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"sweep_dir": str(sweep_root), **manifest}, ensure_ascii=False, indent=2))
        return 0
    if args.command in {"tune", "train"}:
        if args.command == "train":
            print("warning: `bridgetree train` is deprecated; use `bridgetree tune`", file=sys.stderr)
        config = _resolved_config(args)
        training_config = _resolved_tuning_config(args)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        result = run_tuning_experiment(
            config,
            training_config,
            embedder,
            output_dir=args.output_dir,
        )
        if args.audit_full_32k:
            completion_audit = audit_tuning_run(
                result["run_dir"],
                require_full_32k=True,
                max_parse_failure_rate=args.max_parse_failure_rate,
                raise_on_error=True,
            )
            result = {**result, "completion_audit": completion_audit}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "preflight-tuning":
        config = _resolved_config(args)
        training_config = _resolved_tuning_config(args)
        embedder = (
            build_embedder(config.models.embedding, device=config.runtime.device) if args.check_services else None
        )
        result = preflight_tuning(
            config,
            training_config,
            embedder=embedder,
            check_services=args.check_services,
            require_full_32k=args.require_full_32k,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "check-ascend":
        status = {"torch": False, "torch_npu": False, "npu_available": False}
        try:
            import torch

            status["torch"] = True
            try:
                import torch_npu  # noqa: F401

                status["torch_npu"] = True
                status["npu_available"] = bool(torch.npu.is_available())
            except (ImportError, AttributeError):
                pass
        except ImportError:
            pass
        print(json.dumps(status, indent=2))
        return int(args.strict and not status["npu_available"])
    if args.command == "smoke-synthetic":
        print(json.dumps(run_synthetic_smoke(args.output_dir), ensure_ascii=False, indent=2))
        return 0
    if args.command == "aggregate":
        result = aggregate_runs(
            args.input_dir,
            reference_label=args.reference_label,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_resamples=args.bootstrap_resamples,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "package-server":
        repository_root = Path(__file__).resolve().parents[2]
        result = build_server_bundle(repository_root, args.output_dir)
        if args.verify_offline_launcher:
            result.update(verify_bundle_offline_launcher(result["archive"], sys.executable))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-full-32k-offline":
        result = validate_full_32k_offline(
            config_path=args.config,
            tuning_config_path=args.tuning_config,
            output_dir=args.output_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-effect-first":
        config = _resolved_config(args)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        result = run_effect_first_validation(
            config,
            embedder,
            methods=args.method or EFFECT_FIRST_VALIDATION_METHODS,
            output_dir=args.output_dir,
            limit=args.limit,
            generate=args.generate,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "audit-tuning-run":
        result = audit_tuning_run(
            args.run_dir,
            require_full_32k=args.require_full_32k,
            max_parse_failure_rate=args.max_parse_failure_rate,
            raise_on_error=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
