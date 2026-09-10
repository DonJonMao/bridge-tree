import json
import os
import signal
import sys
import time
from pathlib import Path

from bridgetree.background import _copy_artifacts, _discover_run_dir, launch_job, read_job_status


def _wait_for_terminal(state_dir: Path, job: str):
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        status = read_job_status(state_dir, job)
        if status["state"] in {"completed", "failed", "interrupted"}:
            return status
        time.sleep(0.02)
    raise AssertionError(f"background job did not finish: {read_job_status(state_dir, job)}")


def test_background_job_detaches_captures_log_and_copies_fixed_artifacts(tmp_path):
    state_dir = tmp_path / "state"
    run_root = tmp_path / "runs"
    code = (
        "import json,os,sys; from pathlib import Path; "
        "run=Path(sys.argv[1])/'effect_validation_test'; run.mkdir(parents=True); "
        "(run/'effect_summary.json').write_text(json.dumps({'status':'completed'})); "
        "(run/'effect_results.csv').write_text('method,accuracy\\ndense,1.0\\n'); "
        "print(f'captured worker output session_id={os.getsid(0)}', flush=True)"
    )

    launched = launch_job(
        job="effect_first",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[sys.executable, "-c", code, str(run_root)],
        run_root=run_root,
        run_prefix="effect_validation_",
        artifacts={
            "effect_summary.json": "effect_first.summary.json",
            "effect_results.csv": "effect_first.results.csv",
        },
    )
    assert launched["launch_result"] == "started"
    assert launched["state"] == "starting"

    status = _wait_for_terminal(state_dir, "effect_first")
    assert status["state"] == "completed"
    assert status["exit_code"] == 0
    assert status["run_dir"].endswith("effect_validation_test")
    assert (state_dir / "effect_first.exit").read_text() == "0\n"
    assert (state_dir / "effect_first.run_dir").read_text().strip() == status["run_dir"]
    log = (state_dir / "effect_first.log").read_text()
    assert "captured worker output" in log
    assert f"session_id={status['pid']}" in log
    assert json.loads((state_dir / "effect_first.summary.json").read_text()) == {"status": "completed"}
    assert "dense,1.0" in (state_dir / "effect_first.results.csv").read_text()


def test_background_job_records_nonzero_exit_in_fixed_status_files(tmp_path):
    state_dir = tmp_path / "state"
    launched = launch_job(
        job="train_32k",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[sys.executable, "-c", "import sys; print('failed run'); sys.exit(7)"],
        run_root=tmp_path / "runs",
        run_prefix="tune_",
    )
    assert launched["launch_result"] == "started"

    status = _wait_for_terminal(state_dir, "train_32k")
    assert status["state"] == "failed"
    assert status["exit_code"] == 7
    assert (state_dir / "train_32k.exit").read_text() == "7\n"
    assert "failed run" in (state_dir / "train_32k.log").read_text()


def test_background_monitor_forwards_graceful_stop_and_records_interruption(tmp_path):
    state_dir = tmp_path / "state"
    run_dir = tmp_path / "runs" / "dependency_exact"
    code = """
import json
import os
import signal
import sys
import time
from pathlib import Path

run = Path(sys.argv[1])
run.mkdir(parents=True)

def stop(_signum, _frame):
    (run / "completion.json").write_text(
        json.dumps({"status": "interrupted", "inference_complete": False})
    )
    raise SystemExit(1)

time.sleep(0.2)
signal.signal(signal.SIGTERM, stop)
(run / ".background_worker_ready.json").write_text(
    json.dumps({"pid": os.getpid()})
)
print("worker-ready", flush=True)
while True:
    time.sleep(0.02)
"""
    launched = launch_job(
        job="graceful",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[sys.executable, "-c", code, str(run_dir)],
        run_root=run_dir.parent,
        run_prefix=run_dir.name,
        exact_run_dir=run_dir,
        artifacts={"completion.json": "graceful.completion.json"},
    )
    assert launched["monitor_ready"] is True
    os.kill(launched["pid"], signal.SIGTERM)
    status = _wait_for_terminal(state_dir, "graceful")

    assert status["state"] == "interrupted"
    assert status["termination_signal"] == signal.SIGTERM
    assert status["exit_code"] == 1
    completion = json.loads((state_dir / "graceful.completion.json").read_text())
    assert completion == {"status": "interrupted", "inference_complete": False}


def test_background_launcher_reports_an_existing_live_job(tmp_path):
    state_dir = tmp_path / "state"
    first = launch_job(
        job="one_job",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[sys.executable, "-c", "import time; time.sleep(0.4)"],
        run_root=tmp_path / "runs",
        run_prefix="run_",
    )
    second = launch_job(
        job="one_job",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[sys.executable, "-c", "raise SystemExit('must not run')"],
        run_root=tmp_path / "runs",
        run_prefix="run_",
    )

    assert second["launch_result"] == "already_running"
    assert second["pid"] == first["pid"]
    assert _wait_for_terminal(state_dir, "one_job")["state"] == "completed"


def test_artifact_copy_error_is_reported_without_leaving_a_temporary_file(tmp_path):
    run_dir = tmp_path / "run"
    state_dir = tmp_path / "state"
    run_dir.mkdir()
    state_dir.mkdir()
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    (state_dir / "fixed.json").mkdir()

    copied, missing, errors = _copy_artifacts(
        run_dir,
        state_dir,
        {"summary.json": "fixed.json"},
    )

    assert copied == {}
    assert missing == []
    assert "summary.json" in errors
    assert not list(state_dir.glob("fixed.json.*.tmp"))


def test_run_discovery_recognizes_exact_preexisting_resume_directory(tmp_path):
    run_root = tmp_path / "runs"
    exact = run_root / "dependency_20260910_120000"
    sibling = run_root / "dependency_20260910_120000_old"
    exact.mkdir(parents=True)
    sibling.mkdir()

    discovered = _discover_run_dir(run_root, exact.name, {exact.resolve(), sibling.resolve()})

    assert discovered == exact.resolve()


def test_background_status_exposes_declared_run_directory_while_running(tmp_path):
    state_dir = tmp_path / "state"
    run_root = tmp_path / "runs"
    exact = run_root / "dependency_exact"
    launched = launch_job(
        job="declared",
        state_dir=state_dir,
        cwd=tmp_path,
        command=[
            sys.executable,
            "-c",
            "import pathlib,sys,time; pathlib.Path(sys.argv[1]).mkdir(parents=True); time.sleep(.2)",
            str(exact),
        ],
        run_root=run_root,
        run_prefix=exact.name,
        exact_run_dir=exact,
    )
    assert launched["run_dir"] == str(exact.resolve())
    assert _wait_for_terminal(state_dir, "declared")["run_dir"] == str(exact.resolve())
