#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import time
from contextlib import suppress
from pathlib import Path

from bridgetree.dependency_config import load_dependency_config
from bridgetree.dependency_experiment import run_dependency_experiment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run or preflight the train-free conditional-activation experiment"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--override-config")
    parser.add_argument("--protocol-manifest")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true")
    mode.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    ready_path = output_dir / ".background_worker_ready.json"
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def interrupt_for_sigterm(signum, _frame):
        raise KeyboardInterrupt(f"received {signal.Signals(signum).name}")

    signal.signal(signal.SIGTERM, interrupt_for_sigterm)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        temporary_ready = ready_path.with_name(
            f".{ready_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        temporary_ready.write_text(
            json.dumps({"pid": os.getpid(), "ready_at_epoch": time.time()}) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_ready, ready_path)
        config = load_dependency_config(args.config, args.override_config)
        result = run_dependency_experiment(
            config,
            output_dir,
            resume=args.resume,
            preflight_only=args.preflight_only,
            protocol_manifest=args.protocol_manifest,
        )
    finally:
        with suppress(OSError):
            ready_path.unlink()
        signal.signal(signal.SIGTERM, previous_sigterm)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"completed", "preflight_complete"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
