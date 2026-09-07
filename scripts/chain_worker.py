#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from bridgetree.chain_experiment import build_full_plan, summarize_outcomes, write_plan

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--queries", default="data/processed/personamem-v1/32k/queries.jsonl")
    args = parser.parse_args()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    source = Path(args.queries)
    queries = [json.loads(line) for line in source.open(encoding="utf-8") if line.strip()] if source.is_file() else []
    tasks = build_full_plan(queries, dataset_revision="personamem-v1-32k", config_hash="chain_full")
    write_plan(out / "planned_tasks.jsonl", tasks)
    manifest = {
        "schema_version": 1,
        "mode": "train_free",
        "dataset_revision": "personamem-v1-32k",
        "config": args.config,
        "created_at_epoch": time.time(),
        "methods": sorted({task.method_id for task in tasks}),
        "expected_tasks": len(tasks),
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "resolved_config.json").write_text(json.dumps({"config_path": args.config}, indent=2), encoding="utf-8")
    (out / "train.log").write_text("mode=train_free optimizer_steps=0 weights_updated=false\n", encoding="utf-8")
    for name in ("visibility", "proposal", "graph", "joint", "closure", "lookahead", "join", "stop", "context", "outcome", "cost"):
        module_dir = out / "modules"
        module_dir.mkdir(exist_ok=True)
        (module_dir / f"{name}.jsonl").write_text("", encoding="utf-8")
    for name in ("events.jsonl", "predictions.jsonl", "failures.jsonl", "metrics.csv"):
        (out / name).write_text("", encoding="utf-8")
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    for name in ("seen_report.json", "confirmation_report.json", "all_data_report.json"):
        (reports / name).write_text(json.dumps({"status": "planned", "expected_tasks": len(tasks)}, indent=2), encoding="utf-8")
    (out / "progress.json").write_text(json.dumps({"expected_tasks": len(tasks), "completed_tasks": 0}, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summarize_outcomes(tasks, []), indent=2), encoding="utf-8")
    (out / "completion.json").write_text(json.dumps({"status": "planned", "expected_tasks": len(tasks)}, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(out), "expected_tasks": len(tasks)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
