"""Read-only audit of authoritative outcomes; no service calls or runtime edits."""
import argparse
import collections
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def key(x):
    return (x["task"]["persona_id"], x["task"]["question_id"])


def counts(xs):
    return {
        "processed": len(xs),
        "success": sum(x["status"] == "success" for x in xs),
        "error": sum(x["status"] == "error" for x in xs),
        "correct": sum(x.get("correct") is True for x in xs),
    }


def paired(xs, dense):
    ps = [(x, dense[key(x)]) for x in xs if key(x) in dense]
    labels = collections.Counter(
        ("both_correct" if a.get("correct") is True and b.get("correct") is True else
         "evidence_only_correct" if a.get("correct") is True else
         "dense_only_correct" if b.get("correct") is True else "both_wrong")
        for a, b in ps
    )
    return {
        "n": len(ps),
        "dense_correct": sum(b.get("correct") is True for a, b in ps),
        "evidence_correct": sum(a.get("correct") is True for a, b in ps),
        **dict(labels),
        "identical_request_hash": sum(
            a.get("diagnostics", {}).get("request_hash") is not None
            and a["diagnostics"]["request_hash"] == b.get("diagnostics", {}).get("request_hash")
            for a, b in ps
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    xs = [read(p) for p in sorted((args.run / "outcomes").glob("*.json"))]
    plan = [json.loads(s) for s in (args.run / "planned_tasks.jsonl").read_text().splitlines() if s.strip()]
    planned = {x["task_id"] for x in plan}
    actual = [x["task"]["task_id"] for x in xs]
    methods = collections.defaultdict(list)
    for x in xs:
        methods[x["task"]["method_id"]].append(x)
    dense = {key(x): x for x in methods["dense"]}
    eb = methods["evidence_bridge"]
    cohorts = collections.defaultdict(list)
    for x in eb:
        status = x.get("diagnostics", {}).get("evidence_bridge_summary", {}).get("reliability", {}).get("reliability_status", "unknown")
        cohorts[(x["status"], status)].append(x)
    errors = [x for x in eb if x["status"] == "error"]
    patterns = {
        "inference_as_explicit": "inferential mappings cannot become explicit coverage",
        "outside_selected": "coverage cites evidence outside final selected set",
        "different_requirement": "mapped to a different requirement",
        "invalid_kind": "invalid coverage kind",
        "unsupported_covered": "covered requirement needs",
    }
    details = []
    for x in errors:
        pool = read(args.run / "candidate_pool" / (x["task"]["task_id"] + ".json"))
        s = pool["evidence_selection"]
        select_requests = [r for r in s["requests"] if r["operation"].startswith("evidence_select")]
        details.append({
            "task_id": x["task"]["task_id"], "key": key(x), "error": x["error"],
            "calls": s["costs"]["evidence_llm_calls"],
            "repairs": s["costs"]["evidence_json_repairs"],
            "selection_requests": [{k: r.get(k) for k in ("operation", "input_tokens_estimate", "local_repair_index", "validation_status", "validation_error")} for r in select_requests],
            "selection_truncated": any(v["truncated"] for v in s["selection_inputs"]),
        })
    successes = [x for x in eb if x["status"] == "success"]
    result = {
        "source": str(args.run.resolve()),
        "integrity": {"outcomes": len(xs), "planned": len(plan), "duplicate_task_ids": len(actual) - len(set(actual)), "unplanned_task_ids": sorted(set(actual) - planned)},
        "methods": {m: counts(v) for m, v in methods.items()},
        "paired_all_evidence_processed": paired(eb, dense),
        "paired_evidence_success": paired(successes, dense),
        "cohorts": {state + "/" + cohort: {**counts(v), "paired": paired(v, dense)} for (state, cohort), v in cohorts.items()},
        "terminal_error_patterns_nonexclusive": {name: sum(text in x["error"] for x in errors) for name, text in patterns.items()},
        "error_type_counts": dict(collections.Counter(x["error_type"] for x in errors)),
        "selection_request_counts_on_errors": dict(collections.Counter(len(d["selection_requests"]) for d in details)),
        "errors": details,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "errors"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
