from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from .clients import build_embedder
from .config import load_config
from .experiment import METHODS, run_personamem_experiment
from .personamem import PERSONAMEM_REPO, PERSONAMEM_REVISION, prepare_split
from .training import load_training_config, run_training_experiment


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

    run = subparsers.add_parser("run", help="Run a PersonaMem retrieval/e2e experiment")
    run.add_argument("--config", default="configs/default.yaml")
    run.add_argument("--override-config")
    run.add_argument("--method", choices=METHODS, default="bridgetree")
    run.add_argument("--limit", type=int)
    run.add_argument("--generate", action="store_true")
    run.add_argument("--bridge-gold", help="Independent JSONL gold memory annotations")
    run.add_argument("--output-dir")

    sweep = subparsers.add_parser("sweep", help="Run required methods over one or more search budgets")
    sweep.add_argument("--config", default="configs/default.yaml")
    sweep.add_argument("--override-config")
    sweep.add_argument("--method", action="append", choices=METHODS, default=[])
    sweep.add_argument("--budget", action="append", type=int, default=[])
    sweep.add_argument("--limit", type=int)
    sweep.add_argument("--generate", action="store_true")
    sweep.add_argument("--bridge-gold")
    sweep.add_argument("--output-dir")

    train = subparsers.add_parser(
        "train",
        help="Run training-free retrieval configuration search with periodic validation",
    )
    train.add_argument("--config", default="configs/default.yaml")
    train.add_argument("--override-config")
    train.add_argument("--training-config", default="configs/train.yaml")
    train.add_argument("--output-dir")

    check = subparsers.add_parser("check-ascend", help="Report Ascend/PyTorch runtime availability")
    check.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download-personamem":
        download_personamem(args.raw_dir, args.split or ["32k"])
        return 0
    if args.command == "prepare-personamem":
        print(json.dumps(prepare_split(args.raw_dir, args.processed_dir, args.split), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        config = load_config(args.config, args.override_config)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        result = run_personamem_experiment(
            config,
            args.method,
            embedder,
            limit=args.limit,
            generate=args.generate,
            bridge_gold_path=args.bridge_gold,
            output_dir=args.output_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "sweep":
        config = load_config(args.config, args.override_config)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        methods = args.method or list(METHODS)
        budgets = args.budget or [config.retrieval.search_budget]
        sweep_root = Path(args.output_dir or config.runtime.output_dir) / f"sweep_{time.time_ns()}"
        sweep_root.mkdir(parents=True, exist_ok=False)
        runs = []
        for budget in budgets:
            if budget < config.retrieval.first_hop_width:
                raise ValueError("every sweep budget must be >= first_hop_width")
            current = replace(config, retrieval=replace(config.retrieval, search_budget=budget))
            for method in methods:
                result = run_personamem_experiment(
                    current,
                    method,
                    embedder,
                    limit=args.limit,
                    generate=args.generate,
                    bridge_gold_path=args.bridge_gold,
                    output_dir=sweep_root,
                )
                runs.append({"budget": budget, **result})
        manifest = {"methods": methods, "budgets": budgets, "runs": runs}
        with (sweep_root / "sweep_summary.json").open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"sweep_dir": str(sweep_root), **manifest}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "train":
        config = load_config(args.config, args.override_config)
        training_config = load_training_config(args.training_config)
        embedder = build_embedder(config.models.embedding, device=config.runtime.device)
        result = run_training_experiment(
            config,
            training_config,
            embedder,
            output_dir=args.output_dir,
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
    return 2


if __name__ == "__main__":
    sys.exit(main())
