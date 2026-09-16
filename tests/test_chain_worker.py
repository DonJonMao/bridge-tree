import json
import runpy
import signal
import sys
import time
from pathlib import Path

import pytest

from bridgetree import dependency_config, dependency_experiment
from bridgetree.background import launch_job, read_job_status

WORKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "chain_worker.py"


@pytest.mark.parametrize(
    ("result_status", "inference_complete", "exit_code"),
    [("completed_with_failures", True, 0), ("interrupted", False, 1)],
)
def test_chain_worker_exit_status_preserves_failure_results(
    tmp_path, monkeypatch, capsys, result_status, inference_complete, exit_code
):
    run_dir = tmp_path / "run"
    result = {
        "status": result_status,
        "inference_complete": inference_complete,
        "summary": {"failed_tasks": 1, "successful_tasks": 2},
    }
    config = object()
    monkeypatch.setattr(dependency_config, "load_dependency_config", lambda *_: config)

    def run_experiment(actual_config, output_dir, **_kwargs):
        assert actual_config is config
        assert output_dir == run_dir
        assert (run_dir / ".background_worker_ready.json").is_file()
        return result

    monkeypatch.setattr(dependency_experiment, "run_dependency_experiment", run_experiment)
    monkeypatch.setattr(
        sys, "argv", [str(WORKER_PATH), "--config", "unused.yaml", "--output-dir", str(run_dir)]
    )
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    main = runpy.run_path(str(WORKER_PATH))["main"]

    assert main() == exit_code
    assert json.loads(capsys.readouterr().out) == result
    assert not (run_dir / ".background_worker_ready.json").exists()
    assert signal.getsignal(signal.SIGTERM) is previous_sigterm


def test_chain_worker_background_completion_keeps_failed_task_artifacts(tmp_path):
    state_dir = tmp_path / "state"
    run_dir = tmp_path / "runs" / "dependency_skipped"
    code = """
import json
import runpy
import sys

from bridgetree import dependency_config, dependency_experiment

def finish_with_failure(_config, output_dir, **_kwargs):
    summary = {
        "status": "complete",
        "expected_tasks": 3,
        "completed_tasks": 3,
        "successful_tasks": 2,
        "failed_tasks": 1,
        "pending_tasks": 0,
    }
    completion = {
        "status": "completed_with_failures",
        "inference_complete": True,
        "failed_tasks": 1,
    }
    for name, artifact in (("summary.json", summary), ("completion.json", completion)):
        (output_dir / name).write_text(json.dumps(artifact), encoding="utf-8")
    return {**completion, "summary": summary}

dependency_config.load_dependency_config = lambda *_args: None
dependency_experiment.run_dependency_experiment = finish_with_failure
worker = sys.argv[1]
sys.argv = [worker, "--config", "unused.yaml", "--output-dir", sys.argv[2]]
runpy.run_path(worker, run_name="__main__")
"""
    launched = launch_job(
        job="chain_skipped",
        state_dir=state_dir,
        cwd=WORKER_PATH.parents[1],
        command=[sys.executable, "-c", code, str(WORKER_PATH), str(run_dir)],
        run_root=run_dir.parent,
        run_prefix=run_dir.name,
        exact_run_dir=run_dir,
        artifacts={
            "completion.json": "chain_skipped.completion.json",
            "summary.json": "chain_skipped.summary.json",
        },
    )
    assert launched["launch_result"] == "started"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        status = read_job_status(state_dir, "chain_skipped")
        if status["state"] not in {"starting", "running"}:
            break
        time.sleep(0.02)

    assert status["state"] == "completed", status
    assert status["exit_code"] == 0
    assert status["missing_artifacts"] == []
    assert status["artifact_errors"] == {}
    assert (state_dir / "chain_skipped.exit").read_text() == "0\n"
    completion = json.loads((state_dir / "chain_skipped.completion.json").read_text())
    summary = json.loads((state_dir / "chain_skipped.summary.json").read_text())
    assert completion["status"] == "completed_with_failures"
    assert summary["status"] == "complete"
    assert completion["failed_tasks"] == summary["failed_tasks"] == 1
    assert completion["inference_complete"] is True
    assert summary["successful_tasks"] == 2
    assert summary["pending_tasks"] == 0
    log = (state_dir / "chain_skipped.log").read_text()
    assert '"status": "completed_with_failures"' in log
    assert '"failed_tasks": 1' in log
