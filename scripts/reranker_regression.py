"""Reconstruct historical requests or replay them through the repaired client.

Payloads stay in ignored outputs. Reconstruction verifies full request and
document hashes before any network call. No model calls during prepare.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

from bridgetree.clients import RerankerClient, build_rerank_payload
from bridgetree.config import RerankerConfig
from bridgetree.dependency_config import load_dependency_config
from bridgetree.dependency_scoring import SetReranker
from bridgetree.diagnostic_identity import content_hash, request_hash
from bridgetree.request_audit import JsonlAuditSink, request_audit_scope


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def read_bundle(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    raw = (path / "requests.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["requests_sha256"]:
        raise ValueError("Regression bundle checksum mismatch")
    rows = [json.loads(line) for line in raw.splitlines()]
    if any(request_hash(row["payload"]) != row["request_hash"] for row in rows):
        raise ValueError("Reconstructed payload identity mismatch")
    if len({r["request_hash"] for r in rows}) != len(rows):
        raise ValueError("Duplicate regression requests")
    if dict(Counter(r["kind"] for r in rows)) != manifest["counts"] or manifest["coverage_gaps"]:
        raise ValueError("Regression coverage is incomplete")
    return manifest, rows


def prepare(args):
    root, out = Path(args.old_run), Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    old = json.loads((root / "run_manifest.json").read_text())
    query_bytes = Path(args.queries).read_bytes()
    if hashlib.sha256(query_bytes).hexdigest() != old["dataset"]["processed_sha256"]["queries.jsonl"]:
        raise ValueError("Queries differ from historical run")
    queries = {r["question_id"]: r["user_question_or_message"] for r in map(json.loads, query_bytes.splitlines())}
    links = json.loads(Path(args.failure_index).read_text())
    unique = {r["physical"]["request_hash"]: r for r in links}
    rows, gaps, scorers = [], [], {}
    client = RerankerClient(RerankerConfig("http://reconstruction.invalid"))
    for digest, row in sorted(unique.items()):
        physical, qid = row["physical"], row["question_id"]
        try:
            if qid not in scorers:
                paths = list((root / "visible_memories").glob(qid + "-*.json"))
                if len(paths) != 1:
                    raise ValueError("Missing or ambiguous visible memories")
                visible = json.loads(paths[0].read_text())["visible_memories"]
                scorers[qid] = SetReranker(queries[qid], {m["memory_id"]: m for m in visible}, client)
            docs = []
            for descriptor in physical["documents"]:
                doc = scorers[qid].prepare_set(descriptor["set_ids"]).document
                if hashlib.sha256(doc.encode()).hexdigest() != descriptor["document_hash"]:
                    raise ValueError("Document hash mismatch")
                docs.append(doc)
            payload = build_rerank_payload(client.config, queries[qid], docs, len(docs))
            if request_hash(payload) != digest:
                raise ValueError("Full payload hash mismatch")
            rows.append(
                {
                    "request_hash": digest,
                    "question_id": qid,
                    "kind": "singleton_500" if physical.get("status_code") == 500 else "batch_timeout",
                    "payload": payload,
                }
            )
        except (ValueError, KeyError, OSError) as exc:
            gaps.append({"request_hash": digest, "error_type": type(exc).__name__})
    control = json.loads(Path(args.control).read_text())
    rows.append({"request_hash": request_hash(control), "kind": "normal_control", "payload": control})
    raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode()
    (out / "requests.jsonl").write_bytes(raw)
    # Two predeclared questions: the original singleton case and one timeout.
    smoke_ids = ["f546a74f-54de-40d0-9d88-8b0e30467d7b"]
    timeout_ids = sorted({r["question_id"] for r in rows if r["kind"] == "batch_timeout"})
    smoke_ids += [q for q in timeout_ids if q not in smoke_ids][:1]
    manifest = {
        "schema_version": 1,
        "old_run_identity": old["identity"]["run_identity"],
        "requests_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": dict(Counter(r["kind"] for r in rows)),
        "coverage_gaps": gaps,
        "smoke_question_ids": smoke_ids,
        "absolute_tolerance": 1e-6,
        "relative_tolerance": 1e-4,
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 1 if gaps else 0


def replay(bundle, config, output):
    manifest, rows = read_bundle(bundle)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = RerankerClient(config.models.reranker)
    report = {
        "passed": False,
        "planned": len(rows),
        "completed": 0,
        "failed": 0,
        "bundle_sha256": content_hash(manifest),
        "config_hash": config.config_hash(),
        "batch_consistency": [],
        "results": [],
    }
    write_json(output / "summary.json", report)
    singletons = {}
    # Reference scores for every timeout-batch member; historical singleton
    # entries and the normal control are also reused as controls when possible.
    reference_payloads = {}
    for row in rows:
        payload = row["payload"]
        for doc in payload["documents"]:
            one = dict(payload, documents=[doc], top_n=1)
            reference_payloads.setdefault(request_hash(one), one)
    report["planned_singleton_references"] = len(reference_payloads)
    audit = JsonlAuditSink(output / "requests.jsonl")

    def score(payload, kind):
        digest = request_hash(payload)
        started = time.monotonic()
        row = {"request_hash": digest, "kind": kind, "state": "started"}
        report["results"].append(row)
        write_json(output / "summary.json", report)
        try:
            if (
                build_rerank_payload(client.config, payload["query"], payload["documents"], len(payload["documents"]))
                != payload
            ):
                raise ValueError("Client would alter historical payload")
            with request_audit_scope({"stage": "historical_regression"}, sink=audit):
                items = client.rerank_all(payload["query"], payload["documents"])
            values = [i.score for i in sorted(items, key=lambda i: i.index)]
            row.update(state="success", scores=values)
            return values
        except Exception as exc:
            row.update(
                state="failed",
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
                error_metadata=getattr(exc, "error_metadata", {}),
            )
            report["failed"] += 1
            return None
        finally:
            row["elapsed_ms"] = (time.monotonic() - started) * 1000
            write_json(output / "summary.json", report)
            print(json.dumps({k: v for k, v in row.items() if k != "scores"}), flush=True)

    report["capacity_contract"] = client.verify_capacity_contract()
    for digest, payload in sorted(reference_payloads.items()):
        values = score(payload, "singleton_reference")
        singletons[digest] = None if values is None else values[0]
    for row in rows:
        payload = row["payload"]
        if len(payload["documents"]) == 1:
            ok = singletons[row["request_hash"]] is not None
        else:
            values = score(payload, row["kind"])
            references = [
                singletons[request_hash(dict(payload, documents=[doc], top_n=1))] for doc in payload["documents"]
            ]
            ok = values is not None and all(v is not None for v in references)
            deltas = [abs(a - b) for a, b in zip(values, references)] if ok else []
            ok = ok and all(
                math.isclose(a, b, abs_tol=manifest["absolute_tolerance"], rel_tol=manifest["relative_tolerance"])
                for a, b in zip(values, references)
            )
            report["batch_consistency"].append(
                {
                    "request_hash": row["request_hash"],
                    "passed": ok,
                    "max_absolute_difference": max(deltas, default=None),
                }
            )
        report["completed"] += int(ok)
    report["passed"] = report["failed"] == 0 and report["completed"] == len(rows)
    report["transport"] = client.transport_stats
    report["scope"] = (
        "Historical complete inputs via bounded batches; numerical tolerance is not a global activation error bound"
    )
    write_json(output / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare")
    for flag in ("old-run", "failure-index", "queries", "control", "output"):
        prep.add_argument("--" + flag, required=True)
    run = sub.add_parser("execute")
    for flag in ("bundle", "config", "output"):
        run.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        return prepare(args)
    result = replay(args.bundle, load_dependency_config(args.config), args.output)
    print(json.dumps({"passed": result["passed"], "completed": result["completed"], "planned": result["planned"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
