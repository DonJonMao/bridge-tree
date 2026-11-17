#!/usr/bin/env python3
"""Read-only, label-free smoke inspection using only Python's standard library.

No project modules, model services, evaluation labels, or credential files are
loaded. Only selected structural fields are emitted; prompts, source text,
predictions, error prose, response bodies, and manifest configuration are omitted.
The optional receipt must be outside both the repository and experiment output.
"""

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys


IDENTIFIER = re.compile(r"^[A-Za-z0-9_./:*+-]{1,160}$")
BUDGET_KINDS = ("ann", "set_score", "llm", "reader", "json_repairs",
                "embedding_http", "http_attempts")
ERROR_CODES = (
    ("citation_capacity", "citation_capacity"),
    ("Non-support observation must not bind a value", "non_support_value"),
    ("Evidence obligation resolution requires", "invalid_obligation_resolution"),
    ("Observation omitted a grounded parameter dependency", "missing_parent_dependency"),
    ("Unavailable/out-of-scope/stale actual parent", "invalid_parent_dependency"),
    ("invisible alias or ambiguous source", "invalid_source_alias"),
    ("requires nonempty retract_ids", "invalid_retraction_target"),
    ("terminal value", "invalid_terminal_value"),
)


def identifier(value):
    return value if isinstance(value, str) and IDENTIFIER.fullmatch(value) else None


def identifiers(values):
    if not isinstance(values, (list, tuple, dict)):
        return []
    return [value for item in values if (value := identifier(item)) is not None]


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value, 3) if math.isfinite(value) else None


def numeric_fields(value, allowed=BUDGET_KINDS):
    if not isinstance(value, dict):
        return {}
    return {key: number(value[key]) for key in allowed
            if key in value and number(value[key]) is not None}


def read_json(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
        return (value, None) if isinstance(value, dict) else (None, "not_object")
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError, ValueError):
        return None, "unreadable_or_partial_json"


def unit_digest(unit):
    return hashlib.sha256(json.dumps(unit, sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()


def brief_failure(slot):
    if not isinstance(slot, dict):
        return {"error_code": "malformed_failure_slot"}
    error = slot.get("error", "")
    code = next((code for pattern, code in ERROR_CODES
                 if isinstance(error, str) and pattern in error), "validation_error")
    return {"variable": identifier(slot.get("variable")),
            "slot_id": identifier(slot.get("id")), "error_code": code}


def plan_summary(plan):
    if not isinstance(plan, dict):
        return None
    steps = plan.get("steps", plan.get("dag", []))
    program = plan.get("program", plan.get("F", {}))
    if not isinstance(program, dict):
        program = {}
    variables = program.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}
    return {
        "final_node_id": identifier(plan.get("final_node_id")),
        "nodes": [{"id": identifier(step.get("output_slot")),
                   "execution": identifier(step.get("execution")),
                   "answer_type": identifier(step.get("answer_type")),
                   "inputs": identifiers(step.get("inputs", []))}
                  for step in steps if isinstance(step, dict)],
        "variables": [{"id": identifier(key), "type": identifier(value.get("type")),
                       "demand": identifier(value.get("demand"))}
                      for key, value in variables.items()
                      if identifier(key) and isinstance(value, dict)],
    }


def request_fields(event):
    # The event carries the full messages, but only public structural IDs are
    # extracted; never copy any message, question, source, observation or value.
    result = {"phase": None, "variables": None, "node_id": None}
    for message in event.get("messages", []):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        try:
            payload = json.loads(message.get("content", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        result["phase"] = identifier(payload.get("phase"))
        variables = payload.get("requested_slots", payload.get("variables"))
        result["variables"] = identifiers(variables) if variables is not None else None
        task = payload.get("task", {})
        if isinstance(task, dict):
            result["node_id"] = identifier(task.get("output_slot"))
    return result


def inspect_events(path):
    calls = deque(maxlen=3)
    plan = None
    used = {}
    active_demands = []
    counts = Counter()
    last_event = None
    latest_failed_slots = []
    malformed = incomplete = 0
    try:
        stream = path.open("rb")
    except OSError:
        return {"read_error": "unreadable_events"}
    with stream:
        for raw in stream:
            # A concurrently appended last line need not yet be complete.
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except (UnicodeError, ValueError):
                if not raw.endswith(b"\n"):
                    incomplete += 1
                else:
                    malformed += 1
                continue
            if not isinstance(event, dict):
                malformed += 1
                continue
            kind = event.get("event")
            counts[kind if identifier(kind) else "unknown"] += 1
            last_event = {"event": identifier(kind), "sequence": number(event.get("sequence")),
                          "elapsed_seconds": number(event.get("elapsed_seconds"))}
            if kind in ("plan_frozen", "typed_dag_initialized"):
                plan = plan_summary(event.get("plan") if kind == "plan_frozen" else event)
            elif kind == "budget_reserved" and event.get("kind") in BUDGET_KINDS:
                value = number(event.get("used"))
                if value is not None:
                    used[event["kind"]] = value
            elif kind == "residual_state":
                active_demands = identifiers(event.get("active_demands", []))
            elif kind == "reasoning_request_started":
                operation = identifier(event.get("operation"))
                index = number(event.get("logical_call_index"))
                calls.append({"logical_call_index": index, "operation": operation,
                              "stage": f"{operation}/{index}" if operation and index is not None else None,
                              "phase": None, "variables": None, "node_id": None,
                              "state": "started_no_response_event", "failed_slots": None,
                              "start_elapsed_seconds": number(event.get("elapsed_seconds")),
                              "budget_used_at_start": dict(used)})
            elif kind == "model_context_budget" and calls:
                calls[-1]["stage"] = identifier(event.get("stage"))
                calls[-1]["context_budget"] = numeric_fields(event, (
                    "input_tokens_local", "output_token_reserve", "input_margin",
                    "safety_margin", "context_tokens", "total_tokens_local"))
            elif kind == "reasoning_response":
                index = event.get("logical_call_index", event.get("call_index"))
                call = next((item for item in reversed(calls)
                             if item["logical_call_index"] == index), None)
                if call is not None:
                    call.update(request_fields(event))
                    call.update(state="response_recorded",
                                response_elapsed_seconds=number(event.get("elapsed_seconds")),
                                budget_used_after_response=dict(used))
            elif kind == "joint_read_completed":
                slots = event.get("failed_slots", [])
                slots = [brief_failure(slot) for slot in slots] if isinstance(slots, list) else []
                if slots:
                    latest_failed_slots = slots
                if calls:
                    calls[-1]["failed_slots"] = slots
                    calls[-1]["batch_complete"] = event.get("complete") is True
    return {"plan": plan, "ledger_used_from_events": used,
            "last_active_demands": active_demands, "recent_reasoning_calls": list(calls),
            "latest_failed_slots": latest_failed_slots, "last_event": last_event,
            "event_counts": dict(sorted(counts.items())), "ignored_partial_lines": incomplete,
            "ignored_malformed_lines": malformed,
            "pending_request_note": "A started call without a response event is not proof of a live process; phase and variables remain unknown."}


def row_summary(path, unit):
    row, error = read_json(path)
    if row is None:
        return {"row_state": "absent" if error == "missing" else "unreadable",
                "status": None, "seconds": None, "ledger_used": None}, error
    answer = row.get("answer")
    if row.get("unit_id") != unit or not isinstance(answer, dict):
        return {"row_state": "invalid", "status": None, "seconds": None,
                "ledger_used": None}, "row_identity_or_answer_invalid"
    diagnostics = row.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    ledger = diagnostics.get("ledger", {})
    if not isinstance(ledger, dict):
        ledger = {}
    runner = row.get("runner", {})
    cost = runner.get("cost", {}) if isinstance(runner, dict) else {}
    return {"row_state": "published", "status": identifier(answer.get("status")),
            "seconds": number(row.get("seconds")),
            "published_attempt": number(runner.get("attempt")) if isinstance(runner, dict) else None,
            "ledger_used": numeric_fields(ledger.get("used")) if ledger else None,
            "ledger_limits": numeric_fields(ledger.get("limits")) if ledger else None,
            "observed_cost": numeric_fields(cost, ("http_attempts", "physical_llm_attempts",
                                                   "prompt_tokens", "completion_tokens"))}, None


def inspect(root, output):
    manifest, error = read_json(output / "manifest.json")
    if manifest is None:
        raise ValueError("manifest_unavailable: " + str(error))
    arms = manifest.get("arms")
    question_ids = manifest.get("question_ids")
    if (not isinstance(arms, list) or not arms or not isinstance(question_ids, dict)
            or any(not identifier(arm) or "/" in arm or arm in (".", "..") for arm in arms)):
        raise ValueError("invalid_manifest_structure")
    progress, progress_error = read_json(output / "progress.json")
    progress = progress or {}
    progress_brief = {key: identifier(progress.get(key)) for key in
                      ("state", "dataset", "arm", "unit_id", "error_type") if key in progress}
    progress_brief.update(numeric_fields(progress, (
        "question_index", "questions_in_dataset", "failed_arm_tasks", "updated_unix")))
    summaries = []
    statuses = {arm: Counter() for arm in arms}
    unfinished = []
    for dataset, units in question_ids.items():
        if (not identifier(dataset) or "/" in dataset or dataset in (".", "..")
                or not isinstance(units, list) or any(not isinstance(unit, str) for unit in units)
                or len(units) != len(set(units))):
            raise ValueError("invalid_manifest_question_ids")
        for index, unit in enumerate(units):
            digest = unit_digest(unit)
            item = {"dataset": dataset, "question_index": index, "unit_id": identifier(unit), "arms": {}}
            for arm in arms:
                row, row_error = row_summary(output / dataset / arm / "rows" / (digest + ".json"), unit)
                item["arms"][arm] = row
                statuses[arm][row["status"] or row["row_state"]] += 1
                if row_error and row_error != "missing":
                    row["read_error"] = row_error
                if "residual" not in arm:
                    continue
                attempts = output / dataset / arm / "attempts" / digest
                candidates = []
                for path in attempts.glob("attempt-*/fusion_events.jsonl"):
                    try:
                        candidates.append((path.stat().st_mtime_ns, path))
                    except OSError:
                        pass
                if candidates:
                    stamp, path = max(candidates)
                    attempt_match = re.fullmatch(r"attempt-(\d+)", path.parent.name)
                    attempt_number = int(attempt_match[1]) if attempt_match else None
                    published_attempt = row.get("published_attempt")
                    if (row["row_state"] != "published" or
                            (attempt_number is not None and published_attempt is not None
                             and attempt_number > published_attempt)):
                        unfinished.append((stamp, dataset, unit, arm, path))
            summaries.append(item)
    latest = None
    if unfinished:
        _, dataset, unit, arm, path = max(unfinished)
        latest = {"dataset": dataset, "unit_id": identifier(unit), "arm": arm,
                  "events_file": str(path.relative_to(output)), **inspect_events(path)}
        config = manifest.get("config", {})
        fusion = config.get("fusion", {}) if isinstance(config, dict) else {}
        if isinstance(fusion, dict):
            latest["budget_limits_from_manifest"] = {
                kind: number(fusion[key]) for kind, key in (
                    ("ann", "ann_calls"), ("set_score", "set_score_calls"),
                    ("llm", "llm_calls"), ("reader", "reader_calls"),
                    ("json_repairs", "json_repairs"))
                if key in fusion and number(fusion[key]) is not None}
    return {"schema": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
            "repository": str(root), "output": str(output), "labels_read": False,
            "read_only": True, "scope": "Manifest IDs, current published rows, progress and unfinished-attempt fusion events only; no scoring or process control.",
            "progress": progress_brief, "progress_read_error": progress_error,
            "planned_questions": len(summaries), "status_counts": {arm: dict(counts) for arm, counts in statuses.items()},
            "questions": summaries, "latest_unfinished_residual_attempt": latest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Repository root; not imported or modified")
    parser.add_argument("--output", required=True, type=Path, help="Experiment directory, relative to --root or absolute")
    parser.add_argument("--receipt", type=Path, help="Optional new JSON file outside repository and experiment")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    output = args.output.expanduser()
    output = (root / output).resolve() if not output.is_absolute() else output.resolve()
    receipt = args.receipt.expanduser().resolve() if args.receipt else None
    if receipt and (receipt.is_relative_to(root) or receipt.is_relative_to(output)):
        parser.error("--receipt must be outside the repository and experiment output")
    try:
        result = inspect(root, output)
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if receipt:
            with receipt.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        sys.stdout.write(rendered)
    except (OSError, ValueError) as exc:
        # Do not echo exception text which could include untrusted file content.
        sys.stderr.write("Inspection failed: " + type(exc).__name__ + ". Check the input paths, JSON structure, and that the receipt path is new.\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
