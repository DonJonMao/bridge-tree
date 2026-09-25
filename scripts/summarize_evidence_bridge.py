#!/usr/bin/env python3
"""Rebuild a retry-safe mechanism summary from current authoritative outcomes."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def numeric_leaves(value: dict, prefix: str = "") -> dict[str, float]:
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(numeric_leaves(item, name))
        elif isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item):
            result[name] = item
    return result


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def summarize(root: Path) -> dict[str, Any]:
    if not (root / "planned_tasks.jsonl").is_file():
        raise FileNotFoundError(f"no frozen task plan under {root}")
    plan = [
        json.loads(line)
        for line in (root / "planned_tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    planned = {row["task_id"]: row for row in plan}
    if len(planned) != len(plan):
        raise ValueError("duplicate task ID in frozen plan")
    rows = {}
    invalid = []
    for path in sorted((root / "outcomes").glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            task = row["task"]
            task_id = task["task_id"]
            if task_id not in planned or task != planned[task_id] or task_id in rows:
                raise ValueError("outcome identity does not match frozen plan")
            if row.get("status") not in {"success", "error"}:
                raise ValueError("unknown outcome status")
            rows[task_id] = row
        except (OSError, ValueError, KeyError, TypeError) as exc:
            invalid.append({"file": str(path.relative_to(root)), "error_type": type(exc).__name__})
    by_method = defaultdict(list)
    expected = Counter(row["method_id"] for row in plan)
    for task_id, row in rows.items():
        by_method[planned[task_id]["method_id"]].append(row)
    methods = {}
    for method, count in expected.items():
        outcomes = by_method[method]
        successful = [row for row in outcomes if row["status"] == "success"]
        mechanism_rows = []
        costs = []
        absent_summary = 0
        errors = Counter()
        for row in outcomes:
            diagnostics = row.get("diagnostics", {})
            summary = diagnostics.get("evidence_bridge_summary")
            if not isinstance(summary, dict):
                absent_summary += 1
            else:
                mechanism_rows.append(numeric_leaves(summary))
            costs.append(numeric_leaves(row.get("costs", {})))
            if row["status"] == "error":
                errors[row.get("error_type") or "unknown"] += 1

        def aggregate(values: list[dict], denominator: int) -> dict:
            names = sorted({name for value in values for name in value})
            result = {}
            for name in names:
                samples = [value[name] for value in values if name in value]
                result[name] = {
                    "observed_tasks": len(samples),
                    "missing_tasks": denominator - len(samples),
                    "sum": sum(samples),
                    "mean": sum(samples) / len(samples),
                    "min": min(samples),
                    "max": max(samples),
                }
            return result

        methods[method] = {
            "expected_tasks": count,
            "outcome_tasks": len(outcomes),
            "successful_tasks": len(successful),
            "failed_tasks": len(outcomes) - len(successful),
            "pending_tasks": count - len(outcomes),
            "correct": sum(row.get("correct") is True for row in successful),
            "success_accuracy": sum(row.get("correct") is True for row in successful) / len(successful)
            if successful
            else None,
            "selected_memories_mean": sum(len(row.get("selected_ids", [])) for row in successful) / len(successful)
            if successful
            else None,
            "mechanism_summary_absent_tasks": absent_summary,
            "mechanism_metrics": aggregate(mechanism_rows, len(outcomes)),
            "cost_metrics": aggregate(costs, len(outcomes)),
            "failure_types": dict(errors),
        }
    return {
        "schema_version": 1,
        "generated_at_epoch": time.time(),
        "run_dir": str(root),
        "source": "frozen planned_tasks.jsonl and one current outcomes file per task",
        "attempt_history_accumulated": False,
        "live_snapshot_is_transactional": False,
        "interpretation": (
            "Evidence coverage is a validated model judgment, not gold evidence recall or causal answer utility. "
            "Numeric sums of ratios are descriptive only; use means and observed/missing counts."
        ),
        "invalid_outcome_files": invalid,
        "methods": methods,
    }


def markdown(result: dict) -> str:
    lines = [
        "# Evidence BridgeTree 当前运行汇总",
        "",
        f"运行目录：`{result['run_dir']}`",
        "",
        "只读取当前权威 outcome；未累加重试日志。运行中读取是快照，任务完成后可再次生成。覆盖判断不等于真实答案效用。",
        "",
        "| 方法 | 成功 | 失败 | 待运行 | 正确 | 成功准确率 | 缺机制汇总 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method, row in result["methods"].items():
        accuracy = "未产生" if row["success_accuracy"] is None else f"{100 * row['success_accuracy']:.2f}%"
        lines.append(
            f"| {method} | {row['successful_tasks']} | {row['failed_tasks']} | {row['pending_tasks']} "
            f"| {row['correct']} | {accuracy} | {row['mechanism_summary_absent_tasks']} |"
        )
    for method, row in result["methods"].items():
        lines.extend(
            [
                "",
                f"## {method} 模块与成本",
                "",
                "缺字段保持缺失，均值只以确实观测到的任务为分母。"
                "失败任务的已完成模块同样计入，详查具体 outcome 可区分成功与失败。",
                "",
                "| 指标 | 有值任务 | 缺失任务 | 均值 | 最小 | 最大 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for section in ("mechanism_metrics", "cost_metrics"):
            for name, stat in row[section].items():
                lines.append(
                    f"| {section}.{name} | {stat['observed_tasks']} | {stat['missing_tasks']} "
                    f"| {stat['mean']:.6g} | {stat['min']:.6g} | {stat['max']:.6g} |"
                )
    lines.extend(["", f"无效 outcome 文件数：{len(result['invalid_outcome_files'])}；详细身份错误见 JSON。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    root = args.run_dir.expanduser().resolve()
    result = summarize(root)
    atomic_text(root / "mechanism_summary.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    atomic_text(root / "mechanism_summary.md", markdown(result))
    print(markdown(result))
    print(f"JSON: {root / 'mechanism_summary.json'}")
    return 1 if result["invalid_outcome_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
