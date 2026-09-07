#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
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
    (out / "train.log").write_text("mode=train_free optimizer_steps=0 weights_updated=false\n", encoding="utf-8")
    (out / "progress.json").write_text(json.dumps({"expected_tasks": len(tasks), "completed_tasks": 0}, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summarize_outcomes(tasks, []), indent=2), encoding="utf-8")
    (out / "completion.json").write_text(json.dumps({"status": "planned", "expected_tasks": len(tasks)}, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(out), "expected_tasks": len(tasks)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
