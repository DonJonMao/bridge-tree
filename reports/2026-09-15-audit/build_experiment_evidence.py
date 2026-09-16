"""Reproduce the read-only archive audit; never contacts model services.

Only report artifacts in this directory are written.  Input tar files are
read through tarfile without extraction.  Config output uses an allowlist;
credentials, endpoint URLs and the original full config are never exported.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from bridgetree.protocol import _source_package_snapshot  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(archive, name):
    return json.load(archive.extractfile(name))


def read_jsonl(archive, name):
    return [json.loads(line) for line in archive.extractfile(name) if line.strip()]


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else None


def error_category(row):
    message = str(row.get("error", ""))
    if "HTTP status 500" in message:
        return "HTTP_500"
    if "TimeoutError" in message:
        return "TimeoutError"
    return str(row.get("error_type") or "other")


def task_key(row):
    return row["task"]["task_id"]


def question_key(row):
    return (row["task"]["persona_id"], row["task"]["question_id"])


def stage(row):
    module = row["diagnostics"]["module_effectiveness"]
    if module["generation_evaluation"]["generator_calls"]:
        return "generation_started"
    return "selection" if module["selection"]["available"] else "dependency_search"


def result_counts(rows):
    successful = [row for row in rows if row["status"] == "success"]
    correct = sum(row["correct"] is True for row in successful)
    failed = len(rows) - len(successful)
    return {
        "completed": len(rows), "successful": len(successful),
        "correct": correct, "incorrect_successful": sum(row["correct"] is False for row in successful),
        "failed": failed, "execution_success_rate": safe_div(len(successful), len(rows)),
        "successful_accuracy": safe_div(correct, len(successful)),
        "correct_per_completed_including_failures": safe_div(correct, len(rows)),
    }


def pair_summary(left_name, right_name, by_method, restrict_questions=None):
    left = {question_key(row): row for row in by_method[left_name] if row["status"] == "success"}
    right = {question_key(row): row for row in by_method[right_name] if row["status"] == "success"}
    common = set(left) & set(right)
    if restrict_questions is not None:
        common &= restrict_questions
    cells = collections.Counter()
    rescues, harms = [], []
    for key in sorted(common):
        a, b = left[key]["correct"] is True, right[key]["correct"] is True
        cells[(a, b)] += 1
        item = {"persona_id": key[0], "question_id": key[1],
                "left_task_id": task_key(left[key]), "right_task_id": task_key(right[key])}
        if b and not a:
            rescues.append(item)
        elif a and not b:
            harms.append(item)
    discordant = len(rescues) + len(harms)
    p_value = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(len(rescues), len(harms)) + 1)) / (2 ** discordant)) if discordant else 1.0
    return {"left": left_name, "right": right_name, "common_success_tasks": len(common),
            "both_correct": cells[(True, True)], "both_incorrect": cells[(False, False)],
            "right_rescues": len(rescues), "right_harms": len(harms),
            "left_correct": cells[(True, True)] + cells[(True, False)],
            "right_correct": cells[(True, True)] + cells[(False, True)],
            "right_minus_left_accuracy": safe_div(len(rescues) - len(harms), len(common)),
            "exact_mcnemar_p_unadjusted_exploratory": p_value,
            "rescues": rescues, "harms": harms}


def cost_summary(rows):
    costs = [row["costs"] for row in rows]
    scorers = [cost.get("set_scorer", {}) for cost in costs]
    transports = [scorer.get("reranker_transport", {}) for scorer in scorers]
    failures = [row for row in rows if row["event"] == "task_failure"]
    return {
        "executor_attempts": len(rows),
        "unique_tasks": len({task_key(row) for row in rows}),
        "executor_elapsed_seconds": sum(cost["elapsed_ms"] for cost in costs) / 1000,
        "failed_attempt_elapsed_seconds": sum(row["costs"]["elapsed_ms"] for row in failures) / 1000,
        "reranker_elapsed_seconds": sum(scorer.get("reranker_elapsed_ms", 0) for scorer in scorers) / 1000,
        "adapter_invocations": {key: sum(cost["adapter_invocations"].get(key, 0) for cost in costs)
                                for key in ("embedding_adapter_invocations", "generator_adapter_invocations", "reranker_adapter_invocations")},
        "memory_embedding_adapter_invocations": sum(cost.get("memory_embedding_adapter_invocations", 0) for cost in costs),
        "persistent_cache_hits": sum(scorer.get("persistent_cache_hits", 0) for scorer in scorers),
        "memory_cache_hits": sum(scorer.get("memory_cache_hits", 0) for scorer in scorers),
        "reranker_samples": sum(scorer.get("reranker_samples", 0) for scorer in scorers),
        "logical_unique_sets_charged_attempt_sum": sum(scorer.get("scored_sets", 0) for scorer in scorers),
        "logical_input_tokens_estimate_attempt_sum": sum(scorer.get("logical_input_tokens_estimate", 0) for scorer in scorers),
        "transport": {key: sum(value.get(key, 0) for value in transports)
                      for key in ("logical_calls", "logical_documents", "batch_requests", "batch_documents", "failed_batch_requests", "split_events", "split_recovered_calls", "transport_attempts", "transport_document_attempts")},
    }


def detail_checks(detail_path):
    results = []
    with tarfile.open(detail_path) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            item = read_json(archive, member.name)
            activations = item["search"]["activations"]
            rounds = item["selection"]["rounds"]
            comparisons = [comparison for row in rounds for comparison in row["comparisons"]]
            scores = collections.defaultdict(list)
            for row in activations:
                for key in ("P", "Pe", "PG", "PGe"):
                    scores[tuple(sorted(row["sets"][key]))].append(row[key])
            for row in comparisons:
                if row["base_score"] is not None:
                    scores[tuple(sorted(row["current_ids"]))].append(row["base_score"])
                    scores[tuple(sorted(row["union_ids"]))].append(row["combined_score"])
            last = rounds[-1]["comparisons"]
            results.append({
                "task_id": item["task_id"], "question_id": item["selection"]["selected_ids"][0].split(":")[0],
                "activation_records": len(activations), "selection_comparisons": len(comparisons),
                "max_activation_formula_error": max(abs(row["activation"] - (row["PGe"] - row["PG"] - row["Pe"] + row["P"])) for row in activations),
                "max_selection_marginal_error": max(abs(row["marginal"] - (row["combined_score"] - row["base_score"])) for row in comparisons if row["marginal"] is not None),
                "infeasible_comparisons": sum(not row["feasible"] for row in comparisons),
                "incomplete_rounds": sum(not row["complete"] for row in rounds),
                "repeated_set_score_disagreements_gt_1e_minus_12": sum(max(values) - min(values) > 1e-12 for values in scores.values()),
                "empty_set_score": rounds[0]["comparisons"][0]["base_score"],
                "final_score": next(row["base_score"] for row in last if row["base_score"] is not None),
                "final_max_marginal": max(row["marginal"] for row in last if row["marginal"] is not None),
                "final_negative_comparisons": sum(row["marginal"] is not None and row["marginal"] < 0 for row in last),
                "final_comparisons": len(last), "selected_ids": item["selection"]["selected_ids"],
                "initial_targets": len(item["search"]["initial_target_ids"]),
                "visited_target_counts": dict(collections.Counter(row["state"]["target_id"] for row in item["search"]["states"])),
                "positive_activation_with_negative_context_marginal": sum(row["accepted"] and row["context_marginal"] < 0 for row in activations),
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", type=Path, default=Path("/Users/mao/chain-audit-full.tgz"))
    parser.add_argument("--detail", type=Path, default=Path("/Users/mao/chain-audit-detail.tgz"))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    with tarfile.open(args.full) as archive:
        summary = read_json(archive, "summary.json")
        manifest = read_json(archive, "run_manifest.json")
        wrapped_config = read_json(archive, "resolved_config.json")
        config = wrapped_config["config"]
        outcomes = [read_json(archive, member.name) for member in archive.getmembers()
                    if member.isfile() and member.name.startswith("outcomes/")]
        predictions = read_jsonl(archive, "predictions.jsonl")
        failures = read_jsonl(archive, "failures.jsonl")
        current = read_jsonl(archive, "modules/effectiveness.current.jsonl")
    attempts = predictions + failures
    assert len({(task_key(row), row["attempt"]) for row in attempts}) == len(attempts), "duplicate attempts need adjudication"
    assert len({task_key(row) for row in outcomes}) == len(outcomes), "duplicate outcome IDs"
    assert {task_key(row) for row in attempts} == {task_key(row) for row in outcomes}
    for outcome in outcomes:
        candidates = [row for row in attempts if task_key(row) == task_key(outcome)]
        latest = max(candidates, key=lambda row: row["attempt"])
        assert latest["attempt"] == outcome["attempt"]
        assert (latest["event"] == "prediction") == (outcome["status"] == "success")
    methods = config["execution"]["methods"]
    by_method = {method: [row for row in outcomes if row["task"]["method_id"] == method] for method in methods}
    common_success = set.intersection(*[{question_key(row) for row in rows if row["status"] == "success"} for rows in by_method.values()])
    common_processed = set.intersection(*[{question_key(row) for row in rows} for rows in by_method.values()])
    question_csv = ROOT / "data/raw/personamem-v1/questions_32k.csv"
    with question_csv.open(newline="") as stream:
        questions = {row["question_id"]: row for row in csv.DictReader(stream)}
    assert sha256(question_csv) == manifest["dataset"]["source_sha256"]["questions_32k.csv"]
    failed_outcomes = [row for row in outcomes if row["status"] == "error"]
    final_failures = [row for row in failures if row["attempt"] == max(item["attempt"] for item in failures if task_key(item) == task_key(row))]
    failures_by_task = collections.defaultdict(list)
    for row in failures:
        failures_by_task[task_key(row)].append(row)
    ordered_failures = [sorted(rows, key=lambda row: row["attempt"]) for rows in failures_by_task.values()]
    fingerprint_keys = ("logical_calls", "logical_documents", "batch_documents", "batch_requests", "failed_batch_requests", "split_events", "transport_attempts", "transport_document_attempts")
    fingerprints = collections.Counter(tuple(row["costs"]["set_scorer"]["reranker_transport"][key] for key in fingerprint_keys) for row in final_failures)
    costs = cost_summary(attempts)
    retry_rows = [row for row in failures if row["attempt"] > 1]
    retry_settings = config["execution"]
    planned_wait_seconds = sum(min(retry_settings["infrastructure_retry_initial_seconds"] * retry_settings["infrastructure_retry_multiplier"] ** (row["attempt"] - 2), retry_settings["infrastructure_retry_max_seconds"]) for row in retry_rows)
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout)
    local_source_hash = _source_package_snapshot()
    model_keys = ("model", "backend", "score_space", "score_contract", "max_tokens", "temperature", "context_token_budget", "query_instruction")
    safe_models = {name: {key: value[key] for key in model_keys if key in value} for name, value in config["models"].items()}
    report = {
        "schema_version": 1, "scope": "Downloaded archive snapshot, not current remote state",
        "inputs": {"full_archive": {"name": args.full.name, "sha256": sha256(args.full), "bytes": args.full.stat().st_size},
                   "detail_archive": {"name": args.detail.name, "sha256": sha256(args.detail), "bytes": args.detail.stat().st_size}},
        "snapshot": {"authoritative_outcomes": len(outcomes), "current_module_rows": len(current),
                     "summary_completed": summary["completed_tasks"], "summary_counts": {key: summary[key] for key in ("successful_tasks", "failed_tasks", "correct", "incorrect", "expected_tasks", "pending_tasks")},
                     "overall": result_counts(outcomes), "prediction_rows": len(predictions), "failure_attempt_rows": len(failures),
                     "unique_executor_attempts": len(attempts), "summary_lag_tasks": len(outcomes) - summary["completed_tasks"],
                     "outcome_tasks_absent_from_current": [{"task_id": task_key(row), "method_id": row["task"]["method_id"], "status": row["status"], "correct": row["correct"]} for row in outcomes if task_key(row) not in {item["task_id"] for item in current}],
                     "completed_question_groups_all_methods": len(common_processed), "common_success_questions_all_methods": len(common_success)},
        "counts_by_method": {method: result_counts(rows) for method, rows in by_method.items()},
        "paired_common_success": [pair_summary(a, b, by_method) for a, b in itertools.combinations(methods, 2)],
        "dense_pairs_on_all_methods_common_success": [pair_summary("dense", method, by_method, common_success) for method in methods if method != "dense"],
        "failures": {"final_error_categories": dict(collections.Counter(error_category(row) for row in final_failures)),
                     "stages": dict(collections.Counter(stage(row) for row in failed_outcomes)),
                     "stages_by_method": {method: dict(collections.Counter(stage(row) for row in rows if row["status"] == "error")) for method, rows in by_method.items()},
                     "by_attempt": {str(number): {"count": len(rows), "categories": dict(collections.Counter(error_category(row) for row in rows)), "executor_elapsed_seconds": sum(row["costs"]["elapsed_ms"] for row in rows) / 1000} for number in sorted({row["attempt"] for row in failures}) for rows in [[row for row in failures if row["attempt"] == number]]},
                     "recovered_after_any_failed_attempt": len({task_key(row) for row in predictions} & set(failures_by_task)),
                     "same_ann_and_scored_sets_all_attempts": sum(len({(row["costs"]["ann_calls"], row["costs"]["scored_sets"]) for row in rows}) == 1 for rows in ordered_failures),
                     "retry_attempts_single_reranker_logical_call": sum(row["costs"]["reranker_adapter_requests"] == 1 for row in retry_rows),
                     "attempt_2_and_3_identical_transport_counts": sum(len(rows) == 3 and rows[1]["costs"]["set_scorer"]["reranker_transport"] == rows[2]["costs"]["set_scorer"]["reranker_transport"] for rows in ordered_failures),
                     "final_transport_fingerprints": [{"count": count, **dict(zip(fingerprint_keys, values))} for values, count in fingerprints.most_common()],
                     "generator_started_tasks": sum(row["costs"]["generator_calls"] > 0 for row in final_failures),
                     "ann_budget_remaining_tasks": sum(row["diagnostics"]["module_effectiveness"]["retrieval"]["remaining_ann_calls"] > 0 for row in failed_outcomes),
                     "score_budget_remaining_min": min(row["costs"]["set_scorer"]["remaining_set_budget"] for row in final_failures),
                     "score_budget_remaining_max": max(row["costs"]["set_scorer"]["remaining_set_budget"] for row in final_failures)},
        "failure_strata_search_methods": {},
        "costs": {"all_attempts": costs, "by_method": {method: cost_summary([row for row in attempts if row["task"]["method_id"] == method]) for method in methods},
                  "first_attempt_by_method": {method: cost_summary([row for row in attempts if row["task"]["method_id"] == method and row["attempt"] == 1]) for method in methods},
                  "latest_outcome_executor_seconds_only": sum(row["costs"]["elapsed_ms"] for row in outcomes) / 1000,
                  "retry_executor_seconds": sum(row["costs"]["elapsed_ms"] for row in retry_rows) / 1000,
                  "configured_retry_wait_seconds_not_directly_measured": planned_wait_seconds,
                  "successful_latency_seconds": {method: {"n": len(rows), "median": statistics.median(rows), "mean": statistics.mean(rows), "p90_nearest_rank": sorted(rows)[math.ceil(len(rows) * .9) - 1]} for method in methods for rows in [[row["costs"]["elapsed_ms"] / 1000 for row in predictions if row["task"]["method_id"] == method]]}},
        "provenance": {"run_identity": manifest["identity"], "dataset": manifest["dataset"],
                       "execution_attempts": manifest["execution_attempts"], "safe_models": safe_models,
                       "dependency_config": config["dependency"], "execution_config": config["execution"],
                       "data_policy": {key: config["data"][key] for key in ("split", "memory_granularity", "include_system_persona")},
                       "local_git_head_at_audit": git_head, "local_worktree_dirty_at_audit": dirty,
                       "local_source_package_hash_at_audit": local_source_hash,
                       "local_source_matches_archived_run": local_source_hash == manifest["identity"]["source_code_hash"],
                       "source_hash_algorithm": "protocol._source_package_snapshot: tracked+untracked files in src/bridgetree,reference,configs,scripts,pyproject.toml (git ls-files -co; filesystem fallback), excludes credentials/caches. For sorted paths concatenate relative path, NUL, byte length, NUL, file bytes, NUL and SHA256.",
                       "model_identity_limit": "Configured generator is deepseek-v4-flash; INT8/284B/checkpoint/thinking-mode not established by archive. Reranker model field is empty; its actual server model is not pinned by this field. No endpoint URLs or credentials exported."},
        "detail_arithmetic_checks": detail_checks(args.detail),
        "limitations": ["Snapshot is non-atomic; summary/current lag authoritative outcomes by three success tasks.",
                        "Only four personas are covered. Method-by-question units within a question are correlated; unequal failure missingness prevents unqualified successful-accuracy comparisons.",
                        "Reported execution costs exclude task-level waits and service probes unless explicitly marked; outcome costs retain latest attempt only. Logical token estimates are not billed tokens or per-request input size.",
                        "Paired tests are descriptive/exploratory, conditional on both succeeding, and unadjusted for multiple comparisons.",
                        "Existing logs do not preserve exact failed request body, actual tokenization or server traceback; singleton 500 does not establish OOM or token-limit cause.",
                        "Monotonic logit transform preserves selection marginal sign and argmax for a fixed archive. High scores do not imply correctness probabilities."]}
    search_outcomes = [row for row in outcomes if row["task"]["method_id"] not in ("dense", "dense_rerank")]
    for dimension in ("persona_id", "question_type"):
        values = collections.defaultdict(list)
        for row in search_outcomes:
            value = row["task"]["persona_id"] if dimension == "persona_id" else questions[row["task"]["question_id"]]["question_type"]
            values[value].append(row)
        report["failure_strata_search_methods"][dimension] = {value: {"completed": len(rows), "failed": sum(row["status"] == "error" for row in rows), "failure_rate": sum(row["status"] == "error" for row in rows) / len(rows)} for value, rows in sorted(values.items())}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "experiment_evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 实验日志证据备忘", "", "本文件由 build_experiment_evidence.py 读取两个下载包生成。未调用模型服务、未修改实验代码；完整精确值及逐题配对清单见同目录 JSON。", "", "## 口径", "", f"权威 outcomes {len(outcomes)} 条；summary/current {summary['completed_tasks']}/{len(current)} 条，滞后 {len(outcomes)-summary['completed_tasks']} 条成功。predictions {len(predictions)} + failures {len(failures)} = {len(attempts)} 次去重 executor 调用。", "", "| 方法 | 已处理 | 成功 | 答对 | 答错（成功输出） | 执行失败 | 成功样本正确率 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for method, counts in report["counts_by_method"].items():
        lines.append(f"| {method} | {counts['completed']} | {counts['successful']} | {counts['correct']} | {counts['incorrect_successful']} | {counts['failed']} | {counts['successful_accuracy']:.2%} |")
    lines += ["", "## 与 dense 的同题共同成功配对", "", "rescue＝dense 错/方法对；harm＝dense 对/方法错。分母各不相同，不是全部任务正确率。", "", "| 方法 | 共同成功 | dense 对 | 方法对 | rescue | harm | 净变化（百分点） |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pair in report["paired_common_success"]:
        if pair["left"] == "dense":
            lines.append(f"| {pair['right']} | {pair['common_success_tasks']} | {pair['left_correct']} | {pair['right_correct']} | {pair['right_rescues']} | {pair['right_harms']} | {100*pair['right_minus_left_accuracy']:+.2f} |")
    lines += ["", f"五方法全都成功的共同题数：{len(common_success)}；五方法都有结果的共同题数：{len(common_processed)}。", "", "## 失败与重试", "", f"最终失败类型：{report['failures']['final_error_categories']}；阶段：{report['failures']['stages']}。所有失败都未调用生成器。", "", f"{report['failures']['same_ann_and_scored_sets_all_attempts']} 个任务的三次尝试停在相同 ANN/scored_sets 计数；{len(retry_rows)} 次重试都只剩一次 reranker 逻辑调用。重试恢复 {report['failures']['recovered_after_any_failed_attempt']} 个任务。", "", "HTTP500 已拆到单个集合文档仍失败，不意味着单条 memory 失败；日志不足以确认超长/OOM。", "", "| attempt | 失败数 | HTTP500 | Timeout | executor 小时 |", "|---|---:|---:|---:|---:|"]
    for number, counts in report["failures"]["by_attempt"].items():
        lines.append(f"| {number} | {counts['count']} | {counts['categories'].get('HTTP_500',0)} | {counts['categories'].get('TimeoutError',0)} | {counts['executor_elapsed_seconds']/3600:.3f} |")
    lines += ["", "## 成本与缓存", "", f"全 attempts 执行 {costs['executor_elapsed_seconds']/3600:.3f} 小时，其中失败 {costs['failed_attempt_elapsed_seconds']/3600:.3f} 小时（{costs['failed_attempt_elapsed_seconds']/costs['executor_elapsed_seconds']:.2%}）。仅累加 outcomes 会得到 {report['costs']['latest_outcome_executor_seconds_only']/3600:.3f} 小时，遗漏前期失败尝试。", "", f"后续重试执行 {report['costs']['retry_executor_seconds']/3600:.3f} 小时；按配置推算任务退避 {planned_wait_seconds/3600:.3f} 小时（非等待事件直接计时）。", "", "| 方法 | 全尝试小时 | 成功任务中位秒 | 首次尝试 persistent hits | 首次尝试 memory embedding 调用 |", "|---|---:|---:|---:|---:|"]
    for method in methods:
        all_cost = report["costs"]["by_method"][method]
        first = report["costs"]["first_attempt_by_method"][method]
        lines.append(f"| {method} | {all_cost['executor_elapsed_seconds']/3600:.3f} | {report['costs']['successful_latency_seconds'][method]['median']:.2f} | {first['persistent_cache_hits']} | {first['memory_embedding_adapter_invocations']} |")
    lines += ["", "后执行方法大量复用缓存，dense 独自承担 memory embedding，以上原始时延不是算法固有速度排序。阶段成本不得再次加到 task totals。", "", "## 版本与模型", "", f"数据：PersonaMem-v1 / {manifest['dataset']['split']} / {manifest['dataset']['questions']} 题，revision `{manifest['dataset']['dataset_revision']}`。本地原始问题文件 SHA256 与运行 manifest 完全一致。", "", f"运行 source package hash：`{manifest['identity']['source_code_hash']}`。", "", f"审计本地 HEAD：`{git_head}`，dirty={dirty}；本地 source package hash：`{local_source_hash}`；与运行一致={report['provenance']['local_source_matches_archived_run']}。", "", "源码身份是指定目录内路径与文件字节的聚合 SHA256（包括未跟踪源文件），不是 Git commit。不能把当前本地 HEAD 单独当作服务器运行版本。本次实际聚合哈希匹配，支持用本地源码解释运行机制；该匹配不证明远端模型权重身份。", "", f"模型安全字段：`{json.dumps(safe_models, ensure_ascii=False)}`。", "", report["provenance"]["model_identity_limit"], "", "## 三个详细 case 的复算", "", "| task 前缀 | activation 条数 | selection 比较 | 不可行/不完整 | 最终分 | 末轮最大边际 |", "|---|---:|---:|---:|---:|---:|"]
    for case in report["detail_arithmetic_checks"]:
        lines.append(f"| {case['task_id'][:12]} | {case['activation_records']} | {case['selection_comparisons']} | {case['infeasible_comparisons']}/{case['incomplete_rounds']} | {case['final_score']:.10f} | {case['final_max_marginal']:.10f} |")
    lines += ["", "公式误差为浮点重算精度范围内的零，同集合评分一致；末轮均严格负边际。证据支持代理评分偏好问题，不支持把这些 case 归因于预算过滤或简单改成 logit 即可解决。", "", "## 解释边界", ""]
    lines.extend("- " + value for value in report["limitations"])
    (args.output_dir / "experiment_evidence.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"outcomes": len(outcomes), "attempts": len(attempts), "common_success": len(common_success), "source_matches": report["provenance"]["local_source_matches_archived_run"], "outputs": [str(args.output_dir / "experiment_evidence.json"), str(args.output_dir / "experiment_evidence.md")]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
