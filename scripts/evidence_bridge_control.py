#!/usr/bin/env python3
"""Management for the new method; reuse the tested detached process manager."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path

JOB = "evidence_bridge"
MODULES = {
    "planner",
    "scheduler",
    "target",
    "evidence",
    "feedback",
    "scoring",
    "activation",
    "proposal",
    "state",
    "stop",
    "selection",
    "context",
    "cost",
    "effectiveness",
    "effectiveness-current",
    "requests",
    "archive",
}
REPO = Path(__file__).resolve().parents[1]
# Bootstrap/status run before pip installs numpy/PyYAML. Importing the package
# initializer would load those dependencies; the manager itself is stdlib-only.
_manager = runpy.run_path(str(REPO / "src/bridgetree/background.py"))
ACTIVE_STATES = _manager["ACTIVE_STATES"]
launch_job = _manager["launch_job"]
read_job_status = _manager["read_job_status"]


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def recorded_run(state: Path) -> Path:
    value = (state / f"{JOB}.run_dir").read_text(encoding="utf-8").strip()
    run = Path(value)
    if not value or not run.is_dir():
        raise ValueError("recorded run is unavailable; start a run first")
    return run.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("start", "preflight", "status", "stop", "resume", "log", "module-log", "summary")
    )
    parser.add_argument(
        "argument", nargs="?", help="config for start/preflight; module for module-log; run dir for summary"
    )
    args = parser.parse_args()
    state = Path(os.environ.get("BACKGROUND_STATE_DIR", REPO / "outputs/background-evidence-bridge")).resolve()
    run_root = Path(os.environ.get("OUTPUT_DIR", REPO / "outputs/evidence-bridge")).resolve()
    status = read_job_status(state, JOB)
    if args.action == "status":
        result = status
    elif args.action == "stop":
        if status.get("state") in ACTIVE_STATES and isinstance(status.get("pid"), int):
            os.kill(status["pid"], signal.SIGTERM)
            result = {
                "stop_requested": True,
                "monitor_pid": status["pid"],
                "message": "SIGTERM sent; use status to verify interruption before resume",
            }
        else:
            result = {"stop_requested": False, "state": status.get("state")}
    elif args.action in {"log", "module-log"}:
        if args.action == "log":
            path = state / f"{JOB}.log"
        else:
            module = args.argument or "effectiveness-current"
            if module not in MODULES:
                parser.error("unknown module; choose " + ", ".join(sorted(MODULES)))
            name = "effectiveness.current" if module == "effectiveness-current" else module
            path = recorded_run(state) / "modules" / f"{name}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"log has not been created: {path}")
        os.execvp("tail", ["tail", "-n", "100", "-F", str(path)])
    elif args.action == "summary":
        run = Path(args.argument).resolve() if args.argument else recorded_run(state)
        return subprocess.call([sys.executable, str(REPO / "scripts/summarize_evidence_bridge.py"), str(run)])
    else:
        if status.get("state") in ACTIVE_STATES:
            print(json.dumps({**status, "launch_result": "already_running"}, ensure_ascii=False, indent=2))
            return 0 if args.action != "preflight" else 1
        if args.action == "resume":
            if args.argument is not None:
                parser.error("resume reuses the original config; do not supply a new config")
            spec = read_json(state / f"{JOB}.spec.json")
            run = recorded_run(state)
            command = list(spec["command"])
            if "--resume" not in command:
                command.append("--resume")
            # Config and deployment paths come from the original command, not
            # this shell's current BRIDGETREE_DEPLOYMENT_CONFIG. The executor
            # verifies unchanged contents/source/data before resuming.
        else:
            config = Path(args.argument or REPO / "configs/evidence_bridge.yaml").resolve()
            if not config.is_file():
                raise FileNotFoundError(config)
            run = run_root / f"{args.action}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
            command = [
                sys.executable,
                str(REPO / "scripts/chain_worker.py"),
                "--config",
                str(config),
                "--output-dir",
                str(run),
            ]
            deployment = os.environ.get("BRIDGETREE_DEPLOYMENT_CONFIG")
            if deployment:
                override = Path(deployment).expanduser().resolve()
                if not override.is_file():
                    raise FileNotFoundError(override)
                command.extend(["--override-config", str(override)])
            if args.action == "preflight":
                return subprocess.call([*command, "--preflight-only"], cwd=REPO)
        result = launch_job(
            job=JOB,
            state_dir=state,
            cwd=REPO,
            command=command,
            run_root=run.parent,
            run_prefix=run.name,
            exact_run_dir=run,
            artifacts={name: f"{JOB}.{name}" for name in ("summary.json", "progress.json", "completion.json")},
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (
        args.action in {"start", "resume"}
        and result.get("launch_result") == "started"
        and result.get("monitor_ready") is not True
    ):
        print("Monitor readiness was not confirmed; inspect status before retrying start.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
