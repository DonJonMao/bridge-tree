#!/usr/bin/env python3
"""Tokenize recorded R6 request variants only; never generate or read labels."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from lossless_wire_probe import INSTRUCTION, TABLE, compact, encode_observations, decode_observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.receipt.resolve().is_relative_to(root) or args.receipt.exists():
        raise ValueError("Receipt must be new and outside source repository")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    from dagbt.token_counting import DeploymentTokenCounter
    from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE, PERSONAL_READING_GUIDANCE, PERSONAL_AUDIT_GUIDANCE
    constants = {"history_evidence": PERSONAL_HISTORY_GUIDANCE,
                 "response_selection": PERSONAL_READING_GUIDANCE,
                 "response_audit": PERSONAL_AUDIT_GUIDANCE}
    output = root / "outputs/v4_validation_r6"
    manifest = json.loads((output / "manifest.json").read_text())
    unit = manifest["question_ids"]["personamem"][0]
    key = hashlib.sha256(json.dumps(unit, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    attempt = output / "personamem/dagbt_residual_memory_v2/attempts" / key / "attempt-001"
    events = [json.loads(line) for line in (attempt / "fusion_events.jsonl").read_text().splitlines() if line.strip()]
    responses = {e["logical_call_index"]: e for e in events if e.get("event") == "reasoning_response"}
    records = {}
    for path in (attempt / "requests").glob("*.json"):
        record = json.loads(path.read_text())
        stage = record.get("stage", [])
        if len(stage) >= 2 and str(stage[1]).isdigit() and str(stage[0]).startswith("joint_read"):
            records[int(stage[1])] = record
    config = deepcopy(manifest["config"])
    config["credentials_file"] = str((root / config["credentials_file"]).resolve())
    token_events = []
    counter = DeploymentTokenCounter(config, token_events.append)
    report = {"schema": "dagv2_r6_lossless_wire_probe_v1", "unit_id": unit,
              "scope": "Recorded reading/recovery requests; exact mandatory compose token counts from runtime events, without reconstructing hypothetical compose payloads.",
              "labels_read": False, "generation_calls": 0, "runtime_files_modified": False,
              "context_tokens": 16384, "output_reserve": 4096, "input_margin": 256,
              "safety_margin": 8, "maximum_input_tokens": 12024,
              "mandatory_compose_rejections": [], "recorded_request_variants": []}
    for index, event in enumerate(events):
        if event.get("event") == "joint_support_capacity_rejected":
            token_records = [e for e in events[max(0, index - 4):index] if e.get("event") == "tokenization_count"]
            report["mandatory_compose_rejections"].append({
                "sequence": event["sequence"], "source_spans": event["source_spans"],
                "base_and_repair_input_counts": [e["count"] for e in token_records],
                "tokenization_request_sha256": [e["tokenization_request_sha256"] for e in token_records],
                "input_overflow_tokens": max(e["count"] for e in token_records) - 12024})
    for index in (11, 12, 13, 14, 16):
        event, record = responses[index], records[index]
        wire = record["payload"]
        user_index = next(i for i, m in enumerate(wire["messages"]) if m["role"] == "user")
        system_index = next(i for i, m in enumerate(wire["messages"]) if m["role"] == "system")
        data = json.loads(wire["messages"][user_index]["content"])
        system = wire["messages"][system_index]["content"]
        phase = data.get("phase")
        guidance = constants[phase]
        assert data["personal_task_instruction"] == guidance and guidance in system
        baseline = counter.count(wire)["count"]
        assert baseline == event["input_tokens_local"], (index, baseline, event["input_tokens_local"])
        row = {"logical_call_index": index, "operation": event["operation"],
               "node_id": data["task"]["output_slot"], "phase": phase,
               "baseline_input_tokens": baseline, "baseline_matches_recorded_count": True,
               "duplicated_phase_instruction_chars": len(guidance),
               "system_contains_exact_phase_instruction": True,
               "largest_user_fields_bytes": sorted(
                   [{"field": k, "bytes": len(compact(v).encode())} for k, v in data.items()],
                   key=lambda x: x["bytes"], reverse=True)[:6], "variants": {}}
        phase_only = deepcopy(data)
        phase_only.pop("personal_task_instruction")
        assert {**deepcopy(phase_only), "personal_task_instruction": guidance} == data
        packed, packing = encode_observations(data)
        row["observation_packing"] = packing
        variants = [("omit_exact_duplicate_phase_only", phase_only, "")]
        if TABLE in packed:
            assert decode_observations(packed) == data
            variants.append(("share_exact_observations_only", packed, INSTRUCTION))
            combined = deepcopy(packed)
            combined.pop("personal_task_instruction")
            assert {**decode_observations(combined), "personal_task_instruction": guidance} == data
            variants.append(("combined", combined, INSTRUCTION))
        for name, body, instruction in variants:
            altered = deepcopy(wire)
            altered["messages"][user_index]["content"] = compact(body)
            altered["messages"][system_index]["content"] += instruction
            count = counter.count(altered)["count"]
            row["variants"][name] = {"input_tokens": count,
                "saved_input_tokens": baseline - count,
                "source_counter_route_roundtrip_equal": True,
                "phase_instruction_still_complete_in_system": True}
        report["recorded_request_variants"].append(row)
    report["tokenization_http_attempts"] = sum(e.get("http_attempts", 0) for e in token_events)
    report["tokenization_counts"] = len(token_events)
    report["limitations"] = [
        "No mandatory compose request body is persisted in these rejection events; its complete exact-body variant savings are not claimed.",
        "Observed reading-request savings cannot be subtracted wholesale from downstream compose counts.",
        "Tokenization-only changes establish wire size and reversible encoding, not model quality or release readiness."]
    with args.receipt.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"receipt": str(args.receipt), "tokenization_http_attempts": report["tokenization_http_attempts"],
                      "generation_calls": 0, "request_samples": len(report["recorded_request_variants"])}, indent=2))


if __name__ == "__main__":
    main()
