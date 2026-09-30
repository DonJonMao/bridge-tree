#!/usr/bin/env python3
"""Read-only v2 export replay of v3 payload visibility and coverage validation.

No backend calls or new answers: old plans/mappings remain frozen. The report
contains IDs, hashes and counts, not source text, prompts or deployment secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

from bridgetree.clients import build_context_plan, estimate_tokens
from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.evidence_recovery import compact_coverage_repair_payload
from bridgetree.evidence_selection import SELECT_PROMPT, EvidenceSelector, EvidenceValidationError, _parse
from bridgetree.evidence_spans import source_segments
from bridgetree.types import Memory


class NoModel:
    def complete_messages(self, *args, **kwargs):
        raise AssertionError("offline replay must never invoke a model")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selector_for(evidence, settings):
    selector = EvidenceSelector(
        NoModel(), settings,
        generation_feasible=lambda _ids: (_ for _ in ()).throw(AssertionError("no selection execution")),
    )
    selector.requirements = tuple(evidence["requirements"])
    selector.mappings = list(evidence["mappings"])
    selector.exposures = list(evidence["exposures"])
    selector.candidate_ids = list(evidence["candidate_ids"])
    selector._mapped_ids = set(evidence.get("fully_mapped_ids", evidence.get("mapped_candidate_ids", [])))
    selector._eligible_ids = {f["memory_id"] for f in selector.mappings}
    return selector


def request_payload(request):
    return json.loads(request["messages"][1]["content"])


def original_query(evidence):
    queries = {request_payload(r)["query"] for r in evidence["requests"] if r.get("messages")}
    if len(queries) != 1:
        raise ValueError("recorded evidence requests do not have one consistent query")
    return queries.pop()


def raw_review_case(run, outcome, dense, evidence, context, settings, reader_budget):
    """Build the actual v3 payload without obtaining any new model response."""
    question = outcome["task"]["question_id"]
    paths = list((run / "visible_memories").glob(question + "-*.json"))
    if len(paths) != 1:
        raise ValueError("expected one visible-memory artifact for the question")
    visible = read_json(paths[0])
    if (str(visible["persona_id"]), visible["question_id"]) != (
        str(outcome["task"]["persona_id"]), question,
    ):
        raise ValueError("visible-memory task identity mismatch")
    records = {m["memory_id"]: Memory(**m) for m in visible["visible_memories"]}
    baseline = dense["selected_ids"]
    if set(baseline) - set(evidence["candidate_ids"]):
        raise ValueError("dense selected IDs are not in the recorded evidence candidate pool")
    plan = context["context_plan"]
    if plan["selected_ids"] != baseline or not plan["token_count"] <= plan["budget"]:
        raise ValueError("dense reader context does not verify the baseline set and budget")
    query = original_query(evidence)
    request = plan["request"]
    # The options are used only by the original reader budget builder. They
    # never enter evidence planning or the raw-review payload.
    user = request["messages"][-1]["content"]
    options = user.rsplit("\n\nAnswer options:\n", 1)[1].rsplit(
        "\nReturn the best option label and a concise answer.", 1,
    )[0]
    canonical = {"messages", "model", "endpoint", "temperature", "max_tokens", "response_format"}

    def context_for(ids):
        return build_context_plan(
            query, [records[i] for i in ids], options, token_budget=reader_budget,
            strict=False, selected_ids=ids, model=request.get("model", ""), endpoint=request.get("endpoint", ""),
            temperature=request.get("temperature", 0.0), max_tokens=request.get("max_tokens"),
            response_format=request.get("response_format"),
            request_params={k: v for k, v in request.items() if k not in canonical},
        )

    reconstructed = context_for(baseline)
    if (list(reconstructed.messages) != request["messages"]
            or reconstructed.token_count != plan["token_count"]):
        raise ValueError("reader reconstruction differs from the exported actual request")
    selector = selector_for(evidence, settings)
    selector.baseline_ids = list(baseline)
    costs = []
    for identifier in selector.candidate_ids:
        singleton = context_for([identifier])
        costs.append({"memory_id": identifier, "singleton_input_tokens_estimate": singleton.token_count,
                      "singleton_feasible": singleton.within_budget,
                      "raw_memory_tokens_estimate": estimate_tokens(records[identifier].text)})
    raw = [{"memory_id": i, "text": records[i].text, "source_segments": source_segments(records[i]),
            "observed_order": records[i].timestamp,
            "mapped_requirement_ids": list(dict.fromkeys(
                f["requirement_id"] for f in selector.mappings if f["memory_id"] == i)),
            "mapping_complete": i in selector._mapped_ids} for i in baseline]
    empty = context_for([])
    payload = selector._selection_payload(query, costs, {"token_count": empty.token_count, "budget": reader_budget},
                                          None, raw_candidates=raw)
    observed = {row["memory_id"]: row for row in payload["raw_memory_candidates"]}
    exact = all(observed[i]["text"] == records[i].text
                and observed[i]["source_segments"] == source_segments(records[i]) for i in observed)
    audit = selector.selection_inputs[-1]
    if selector._calls or selector.requests:
        raise AssertionError("payload-only replay generated model requests")
    return {
        "baseline_ids": baseline, "raw_review_ids": list(observed),
        "omitted_baseline_ids": [i for i in baseline if i not in observed],
        "all_baseline_visible": set(baseline) == set(observed), "visible_raw_text_and_roles_exact": exact,
        "previous_selected_ids": outcome["selected_ids"],
        "previously_dropped_baseline_ids_now_visible": [
            i for i in baseline if i not in outcome["selected_ids"] and i in observed],
        "input_tokens_estimate": audit["input_tokens_after"], "payload_limit": audit["selection_payload_limit"],
        "within_budget": audit["input_tokens_after"] <= audit["selection_payload_limit"],
        "mapped_records_before": len(evidence["mappings"]),
        "mapped_records_retained": len(payload["evidence_ledger"]),
        "new_model_calls": selector._calls, "new_answers": 0,
        "visible_memories_path": str(paths[0].relative_to(run)), "visible_memories_sha256": digest(paths[0]),
        "dense_context_module_line": context["module_line"],
    }


def restore_request_visibility(selector, payload):
    """Keep the old aliases and visible subset, not today's truncation result."""
    counts, aliases = {}, {}
    for fact in selector.mappings:
        req = fact["requirement_id"]
        counts[req] = counts.get(req, 0) + 1
        aliases[f"{req}_e{counts[req]}"] = fact
    selector._visible_evidence = {}
    for row in payload["evidence_ledger"]:
        fact = aliases.get(row["evidence_id"])
        if fact is None or any(fact[k] != row[k] for k in ("memory_id", "requirement_id", "claim")):
            raise ValueError("cannot restore exact recorded evidence alias")
        selector._visible_evidence[row["evidence_id"]] = fact
    selector._visible_candidates = set(payload["candidate_ids"])


def error_categories(errors):
    categories = Counter()
    for error in errors:
        category = next((name for phrase, name in (
            ("different requirement", "wrong_requirement"),
            ("outside final selected set", "outside_selected_set"),
            ("unknown or invisible", "unknown_or_invisible_evidence"),
            ("invalid coverage kind", "invalid_kind"),
            ("verified supporting evidence", "insufficient_support"),
            ("partial coverage requires", "empty_partial"),
            ("missing requirement must", "cited_missing"),
        ) if phrase in error), "other_validation")
        categories[category] += 1
    return dict(categories)


def compact_budget_case(selector, base_payload, response, pending, request):
    """Compare the recorded v2 full-payload repair with today's compact repair."""
    legacy = dict(base_payload)
    legacy["repair_scope"] = {"requirement_ids": sorted(pending), "selected_ids": response["selected_ids"],
                              "instruction": "Keep selected_ids fixed. Return only these coverage rows."}
    feedback = request.get("validation_error", "")[:1200]
    legacy["validation_feedback"] = feedback
    system = request["messages"][0]["content"]
    budget = selector.settings.input_token_budget

    def count(value, prompt):
        return selector._tokens(selector._messages(prompt, value), "evidence_select_repair")

    while count(legacy, system) > budget and len(legacy["validation_feedback"]) > 80:
        value = legacy["validation_feedback"]
        legacy["validation_feedback"] = value[:max(80, len(value) // 2)]
    compact, audit = compact_coverage_repair_payload(
        base_payload, pending_requirement_ids=sorted(pending), selected_ids=response["selected_ids"],
    )
    compact["validation_feedback"] = feedback
    while count(compact, SELECT_PROMPT) > budget and len(compact["validation_feedback"]) > 80:
        value = compact["validation_feedback"]
        compact["validation_feedback"] = value[:max(80, len(value) // 2)]
    return {"legacy_full_repair_tokens_estimate": count(legacy, system),
            "legacy_repair_over_budget": count(legacy, system) > budget,
            "compact_repair_tokens_estimate": count(compact, SELECT_PROMPT),
            "compact_repair_within_budget": count(compact, SELECT_PROMPT) <= budget,
            "input_token_budget": budget, "pending_requirement_ids": sorted(pending),
            "selected_ids": response["selected_ids"], "evidence_records_before": audit["evidence_records_before"],
            "evidence_records_after": audit["evidence_records_after"],
            "old_failure_scope_reused": True,
            "interpretation": "Feasible repair request only; no repair model response was generated."}


def selection_responses(evidence, settings):
    results, base_payload = [], None
    for request in evidence["requests"]:
        if not request["operation"].startswith("evidence_select"):
            continue
        payload = request_payload(request)
        if request["operation"] == "evidence_select":
            base_payload = payload
        selector = selector_for(evidence, replace(settings, response_format=request.get("response_format", "plain")))
        restore_request_visibility(selector, payload)
        row = {"call_index": request["call_index"], "operation": request["operation"],
               "recorded_validation_status": request.get("validation_status"),
               "recorded_messages_hash": request.get("messages_hash"),
               "raw_response_sha256": hashlib.sha256(str(request.get("raw_response", "")).encode()).hexdigest()}
        try:
            metadata = request.get("response_metadata", {})
            if metadata.get("finish_reason") == "length":
                raise EvidenceValidationError("recorded provider truncation", category="output_truncated")
            if metadata.get("refusal") or metadata.get("finish_reason") == "content_filter":
                raise EvidenceValidationError("recorded provider refusal", category="refusal")
            raw = _parse(request["raw_response"])
            selected = selector._selection_header(raw)
            scope = payload.get("repair_scope", {})
            if scope and selected != scope["selected_ids"]:
                raise EvidenceValidationError("repair changed the frozen selected set")
            expected = set(scope.get("requirement_ids", [r["id"] for r in selector.requirements]))
            valid, errors = selector._selection_rows(raw, selected, expected)
            row.update(v3_header_valid=True, v3_response_valid=not errors, valid_requirement_ids=sorted(valid),
                       normalized_requirement_ids=sorted(k for k, v in valid.items() if v["normalization_reason"]),
                       remaining_error_categories=error_categories(errors))
            # Use original failed requirements even if normalization fixes them
            # now. This isolates compacting from any new semantic response.
            pending = set(re.findall(r"coverage ([^ :;]+):", request.get("validation_error", "")))
            pending &= {r["id"] for r in selector.requirements}
            if pending and base_payload is not None and selector.settings.response_format == "plain":
                row["repair_budget"] = compact_budget_case(selector, base_payload, raw, pending, request)
        except EvidenceValidationError as exc:
            row.update(v3_response_valid=False, v3_header_valid=False,
                       remaining_error_categories={getattr(exc, "category", "validation"): 1})
        results.append(row)
    return results


def replay(run_dir: Path, output_dir: Path) -> dict:
    run, output = run_dir.resolve(), output_dir.resolve()
    if output == run or run in output.parents:
        raise ValueError("replay output must be outside the read-only source run")
    if (output / "replay_report.json").exists():
        raise ValueError("use a fresh replay output directory")
    config_path = run / "resolved_config.json"
    config = read_json(config_path)["config"]
    settings = EvidenceSelectionConfig(**{**config["evidence_bridge"]["selection"],
                                         "raw_memory_review": True, "allow_unassessed_coverage": True})
    indexed = {}
    for path in sorted((run / "outcomes").glob("*.json")):
        value = read_json(path)
        task = value["task"]
        key = (str(task["persona_id"]), task["question_id"], task["method_id"])
        if key in indexed or path.stem != task["task_id"]:
            raise ValueError("duplicate or mismatched authoritative outcome identity")
        indexed[key] = value
    contexts = {}
    for number, line in enumerate((run / "modules/context.jsonl").open(encoding="utf-8"), 1):
        value = json.loads(line)
        if value.get("method_id") == "dense" and value.get("context_plan"):
            contexts[value["task_id"]] = {**value, "module_line": number}
    cases, skipped = [], []
    for (persona, question, method), outcome in sorted(indexed.items()):
        if method != "evidence_bridge":
            continue
        normal = (outcome["status"] == "success" and outcome.get("diagnostics", {}).get(
            "evidence_bridge_summary", {}).get("reliability", {}).get("reliability_status") == "normal")
        if not normal and outcome["status"] != "error":
            continue
        task_id = outcome["task"]["task_id"]
        path = run / "candidate_pool" / f"{task_id}.json"
        case = {"task_id": task_id, "persona_id": persona, "question_id": question,
                "recorded_status": outcome["status"], "candidate_pool_path": str(path.relative_to(run)),
                "outcome_path": f"outcomes/{task_id}.json"}
        try:
            artifact = read_json(path)
            if artifact["task_id"] != task_id:
                raise ValueError("candidate-pool identity mismatch")
            evidence = artifact["evidence_selection"]
            case["candidate_pool_sha256"] = digest(path)
            if normal:
                dense = indexed[(persona, question, "dense")]
                if dense["status"] != "success":
                    raise ValueError("normal evidence task has no successful paired dense task")
                case["dense_task_id"] = dense["task"]["task_id"]
                case["raw_review"] = raw_review_case(
                    run, outcome, dense, evidence, contexts[dense["task"]["task_id"]], settings,
                    config["models"]["generator"]["context_token_budget"],
                )
            else:
                case["recorded_error_type"] = outcome.get("error_type")
                case["response_replays"] = selection_responses(evidence, settings)
            cases.append(case)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # No exception text: it may include original user/model strings.
            skipped.append({**case, "error_type": type(exc).__name__})
    reviews = [c["raw_review"] for c in cases if "raw_review" in c]
    errors = [c for c in cases if "response_replays" in c]
    responses = [r for c in errors for r in c["response_replays"]]
    overflows = [r["repair_budget"] for r in responses if r.get("repair_budget", {}).get("legacy_repair_over_budget")]
    report = {
        "schema_version": 1, "source_run": str(run), "resolved_config_sha256": digest(config_path),
        "mode": "offline_frozen_v2_state_v3_payload_and_validator", "new_model_calls": 0, "new_answers": 0,
        "interpretation": "Visibility/validation replay is not a v3 accuracy or task-recovery experiment.",
        "summary": {"normal_tasks_replayed": len(reviews),
                    "normal_tasks_all_baseline_visible": sum(r["all_baseline_visible"] for r in reviews),
                    "normal_payloads_within_budget": sum(r["within_budget"] for r in reviews),
                    "raw_text_and_roles_exact": (
                        all(r["visible_raw_text_and_roles_exact"] for r in reviews) if reviews else None),
                    "old_error_tasks_replayed": len(errors), "old_selection_responses_replayed": len(responses),
                    "old_error_tasks_final_recorded_response_now_valid": sum(
                        bool(c["response_replays"]) and c["response_replays"][-1]["v3_response_valid"] for c in errors),
                    "valid_normalized_coverage_row_observations": sum(
                        len(r.get("normalized_requirement_ids", [])) for r in responses),
                    "remaining_error_categories": dict(sum(
                        (Counter(r.get("remaining_error_categories", {})) for r in responses), Counter())),
                    "legacy_repair_overflow_responses": len(overflows),
                    "legacy_overflows_compact_within_budget": sum(r["compact_repair_within_budget"] for r in overflows),
                    "skipped_tasks": len(skipped)},
        "cases": cases, "skipped": skipped,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "replay_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = replay(args.run_dir, args.output_dir)
    print(json.dumps({"report": str(args.output_dir / "replay_report.json"), **report["summary"]}, indent=2))
    return 1 if report["skipped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
