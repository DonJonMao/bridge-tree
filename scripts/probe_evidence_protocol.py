#!/usr/bin/env python3
"""Explicit, nonprivate planner protocol smoke check before a detached run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import replace
from pathlib import Path

from bridgetree.clients import GeneratorClient, HTTPTransportError
from bridgetree.dependency_config import load_dependency_config
from bridgetree.evidence_protocol import evidence_response_schema
from bridgetree.evidence_selection import EvidenceSelector
from bridgetree.request_audit import TransportBudget, request_audit_scope


def probe(config_path: str, *, override_config: str | None = None, response_format: str | None = None) -> dict:
    """Check one real method request, with no JSON repairs or protocol switch.

    Success proves that this deployment accepted the configured request and
    returned a valid planner object for one fixed query. It does not certify
    schema enforcement, mapping/selection quality, or future model responses.
    """
    started = time.time()
    report = {
        "schema_version": 1, "scope": "deployment_preflight", "status": "failed",
        "check": "evidence_plan_protocol_smoke", "experiment_task": False,
        "started_at_epoch": started, "response_format": response_format,
        "logical_calls": 0, "transport_attempts": 0,
        "protocol_fallback": False,
    }
    events = []
    budget = TransportBudget(4)
    try:
        config = load_dependency_config(config_path, override_config)
        configured_format = config.evidence_bridge.selection.response_format
        selected_format = configured_format if response_format is None else response_format
        selected_settings = replace(config.evidence_bridge.selection, response_format=selected_format)
        effective_config = replace(config, evidence_bridge=replace(config.evidence_bridge, selection=selected_settings))
        schema = evidence_response_schema("evidence_plan")
        report.update({
            "configured_response_format": configured_format,
            "response_format": selected_format,
            "config_hash": effective_config.config_hash(),
            "generator_model": config.models.generator.model,
            "response_schema_sha256": hashlib.sha256(
                json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        })
        # The probe exercises the same prompts, parser, and requirement
        # validation as the experiment. Disable recovery so success cannot
        # hide a malformed first response behind additional model calls.
        selector = EvidenceSelector(
            GeneratorClient(config.models.generator),
            replace(selected_settings, max_json_repairs=0, max_repairs_per_request=0),
            generation_feasible=lambda _ids: {"feasible": True},
        )
        with request_audit_scope(
            {"phase": "deployment_preflight", "scope": "protocol_probe"}, sink=events.append, budget=budget,
        ):
            requirements = selector.plan("Which kind of tea did I say I preferred last spring?")
        report.update({"status": "passed", "requirements_validated": len(requirements)})
    except Exception as exc:
        # Exception text may contain service payloads or private deployment
        # configuration; persist a type and numeric status, never credentials.
        report["error_type"] = type(exc).__name__
        status_code = getattr(exc, "status_code", None)
        report["http_status"] = status_code if isinstance(status_code, int) else None
        if isinstance(exc, HTTPTransportError):
            # Transport causes are class names, not arbitrary exception/body
            # text. Keep observed audit attempts separately below.
            cause = exc.cause_type
            report["cause_type"] = cause if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", cause) else None
            report["attempts"] = exc.attempts
    finally:
        report["logical_calls"] = sum(event["event"] == "model_call_started" for event in events)
        report["transport_attempts"] = budget.used
        responses = [event for event in events if event["event"] == "http_attempt_completed"]
        if responses:
            # Events are already filtered by the payload-free audit layer.
            report["response_metadata"] = {
                key: value for key, value in responses[-1].items()
                if key.startswith("server_") or key == "response_protocol"
            }
        report["elapsed_seconds"] = time.time() - started
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/evidence_bridge.yaml")
    parser.add_argument("--override-config")
    parser.add_argument("--response-format", choices=("plain", "json_object", "json_schema"))
    parser.add_argument("--output", help="Save the credential-free protocol report as JSON")
    args = parser.parse_args(argv)
    result = probe(args.config, override_config=args.override_config, response_format=args.response_format)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        path = Path(args.output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    print(text, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
