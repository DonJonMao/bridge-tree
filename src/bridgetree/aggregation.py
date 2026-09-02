from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from .metrics import paired_bootstrap_interval


def _base_label(run_label: str) -> str:
    return re.sub(r"_seed\d+$", "", run_label)


def aggregate_runs(
    input_dir: str | Path,
    reference_label: str = "core",
    bootstrap_seed: int = 42,
    bootstrap_resamples: int = 2000,
) -> Dict[str, Any]:
    root = Path(input_dir)
    runs = []
    for manifest_path in sorted(root.glob("*/run_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_dir = manifest_path.parent
        summary_path = run_dir / "summary.json"
        predictions_path = run_dir / "predictions.jsonl"
        if not summary_path.exists() or not predictions_path.exists():
            continue
        predictions = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines() if line]
        runs.append(
            {
                "run_dir": str(run_dir),
                "label": _base_label(str(manifest.get("run_label", manifest.get("method", "unknown")))),
                "seed": int(manifest.get("seed", 0)),
                "summary": json.loads(summary_path.read_text(encoding="utf-8")),
                "predictions": predictions,
            }
        )
    if not runs:
        raise ValueError(f"no completed experiment runs found in {root}")

    by_label: Dict[str, list[Dict[str, Any]]] = {}
    for run in runs:
        by_label.setdefault(run["label"], []).append(run)
    if reference_label not in by_label:
        raise ValueError(f"reference label is unavailable: {reference_label}")

    metric = None
    for candidate in ("answer_accuracy", "recall_at_k", "bridge_recall_at_k"):
        if any(
            prediction.get("outcome", {}).get(candidate) is not None
            for run in runs
            for prediction in run["predictions"]
        ):
            metric = candidate
            break

    reference_values: Dict[tuple[int, str], float] = {}
    if metric:
        for run in by_label[reference_label]:
            for prediction in run["predictions"]:
                value = prediction.get("outcome", {}).get(metric)
                if value is not None:
                    reference_values[(run["seed"], prediction["question_id"])] = float(value)

    labels: Dict[str, Any] = {}
    for label, label_runs in sorted(by_label.items()):
        seeds = sorted({run["seed"] for run in label_runs})
        costs = [run["summary"].get("cost", {}).get("mean", {}) for run in label_runs]
        cost_names = sorted({name for record in costs for name in record})
        mean_cost = {name: sum(float(record.get(name, 0.0)) for record in costs) / len(costs) for name in cost_names}
        values_by_key = {}
        if metric:
            for run in label_runs:
                for prediction in run["predictions"]:
                    value = prediction.get("outcome", {}).get(metric)
                    if value is not None:
                        values_by_key[(run["seed"], prediction["question_id"])] = float(value)
        common = sorted(set(values_by_key) & set(reference_values))
        paired = None
        if metric and common:
            paired = paired_bootstrap_interval(
                [values_by_key[key] for key in common],
                [reference_values[key] for key in common],
                seed=bootstrap_seed,
                resamples=bootstrap_resamples,
            )
        labels[label] = {
            "runs": len(label_runs),
            "seeds": seeds,
            "seed_requirement_met": len(seeds) >= 3,
            "queries_with_outcome": len(values_by_key),
            "mean_outcome": (sum(values_by_key.values()) / len(values_by_key) if values_by_key else None),
            "paired_vs_reference": paired,
            "mean_cost": mean_cost,
            "run_dirs": [run["run_dir"] for run in label_runs],
        }
    result = {
        "input_dir": str(root),
        "reference_label": reference_label,
        "outcome_metric": metric,
        "bootstrap": {
            "unit": "query_seed_pair",
            "seed": bootstrap_seed,
            "resamples": bootstrap_resamples,
            "confidence": 0.95,
        },
        "labels": labels,
    }
    output_path = root / "aggregate_summary.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_path": str(output_path), **result}
