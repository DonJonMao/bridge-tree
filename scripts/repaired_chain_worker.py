"""Gate one fresh full run on historical regression and fixed end-to-end tasks."""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path

from reranker_regression import read_bundle, replay, write_json

from bridgetree.dependency_config import load_dependency_config
from bridgetree.dependency_experiment import load_dependency_dataset, run_dependency_experiment
from bridgetree.diagnostic_identity import content_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "acceptance.json").exists() or (root / "run_manifest.json").exists():
        raise ValueError("Use a fresh run directory; old results cannot be resumed under a new deployment")

    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    ready = root / ".background_worker_ready.json"
    write_json(ready, {"pid": os.getpid()})
    state = {"passed": False, "phase": "preflight", "full_run_started": False}

    def save():
        write_json(root / "acceptance.json", state)
        print(json.dumps(state), flush=True)

    try:
        config = load_dependency_config(args.config)
        manifest, _ = read_bundle(args.bundle)
        if manifest["counts"] != {"singleton_500": 190, "batch_timeout": 3, "normal_control": 1}:
            raise ValueError("Expected the complete audited 190 + 3 inputs and normal control")
        dataset = load_dependency_dataset(config, require_full_32k=True)
        by_id = {e.question_id: e for e in dataset.examples}
        fixed = [by_id[q] for q in manifest["smoke_question_ids"]]
        if len(fixed) != 2 or len({e.question_id for e in fixed}) != 2:
            raise ValueError("Expected two distinct predeclared smoke questions")
        # Freeze the formal plan while its directory is still empty. Later
        # acceptance artifacts coexist with this preflight-complete run.
        run_dependency_experiment(config, root, preflight_only=True, require_full_32k=True)
        state.update(
            config_hash=config.config_hash(),
            bundle_sha256=content_hash(manifest),
            dataset=dataset.public_dict(),
            smoke_question_ids=manifest["smoke_question_ids"],
            phase="historical_regression",
        )
        save()
        regression = replay(args.bundle, config, root / "regression")
        if not regression["passed"]:
            state.update(phase="regression_failed")
            save()
            return 1
        state.update(phase="end_to_end_acceptance")
        save()
        # Explicit subset boundary: production data was verified above. This
        # separate acceptance run is never merged into the formal 589-question run.
        smoke = run_dependency_experiment(config, root / "smoke", examples=fixed, require_full_32k=False)
        summary = smoke.get("summary", {})
        expected = len(fixed) * len(config.execution.methods)
        if (
            smoke.get("status") != "completed"
            or summary.get("successful_tasks") != expected
            or summary.get("failed_tasks") != 0
            or summary.get("pending_tasks") != 0
        ):
            state.update(phase="end_to_end_failed")
            save()
            return 1
        # Accuracy is intentionally absent from this gate. Production executor
        # requires complete scoring rounds and validated context/response shapes.
        state.update(passed=True, phase="full_experiment", full_run_started=True)
        save()
        result = run_dependency_experiment(config, root, require_full_32k=True)
        state.update(phase=result.get("status", "unknown"))
        save()
        return 0 if result.get("status") == "completed" else 1
    except KeyboardInterrupt:
        state.update(phase="interrupted")
        save()
        return 130
    except Exception as exc:
        state.update(phase="failed", error_type=type(exc).__name__)
        save()
        raise
    finally:
        ready.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
