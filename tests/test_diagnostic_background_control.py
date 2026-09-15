"""Management checks and real local detached processes; no model services."""
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import time

import pytest

from bridgetree import diagnostic_background as service
from bridgetree.background import launch_job, read_job_status


def test_printed_commands_preserve_spaces_runtime_and_custom_root(tmp_path):
    repo, state, root = (tmp_path / name for name in ("repo space", "state space", "run space"))
    commands = service._management_commands(repo, state, root, "my-job")
    words = shlex.split(commands["resume"])
    assert words == ["env", "BRIDGETREE_BASE_PYTHON=" + sys.executable,
                     "bash", str(repo / "scripts/run_diagnostics.sh"), "resume",
                     "--state-dir", str(state), "--run-root", str(root), "--job", "my-job"]


@pytest.mark.parametrize("state,root,job", [
    ("/", "/tmp/diagnostic-runs", "diagnostics"),
    ("/tmp/diagnostic-state", "/tmp/diagnostic-state/runs", "diagnostics"),
    ("/tmp/diagnostic-state", "/tmp/diagnostic-runs", "../invalid"),
])
def test_unsafe_management_paths_rejected(state, root, job):
    args = service.build_parser().parse_args(["status", "--state-dir", state,
                                             "--run-root", root, "--job", job])
    with pytest.raises(ValueError):
        service._paths(args)


def test_resume_recovers_root_config_mode_without_reset(tmp_path, monkeypatch, capsys):
    state, root = tmp_path / "state", tmp_path / "custom runs"
    config = tmp_path / "server config.yaml"
    config.write_text("fixture only")
    previous = {"state": "interrupted", "run_root": str(root), "run_dir": str(root / "frozen"),
                "command": [sys.executable, "-u", "worker", "--config", str(config), "--offline"]}
    monkeypatch.delenv("DIAGNOSTIC_RUN_ROOT", raising=False)
    monkeypatch.setattr(service, "read_job_status", lambda *a: previous)
    calls = []
    def launch(**kwargs):
        calls.append(kwargs)
        return {"state": "starting", "run_dir": str(kwargs["exact_run_dir"])}
    monkeypatch.setattr(service, "launch_job", launch)
    assert service.main(["resume", "--state-dir", str(state)]) == 0
    assert calls[0]["run_root"] == root
    assert calls[0]["exact_run_dir"] == root / "frozen"
    assert "--resume-worker" in calls[0]["command"]
    assert "--offline" in calls[0]["command"]
    assert str(config) in calls[0]["command"]
    assert service.main(["resume", "--state-dir", str(state), "--online"]) == 0
    assert "--offline" not in calls[1]["command"]
    assert "--resume-worker" in calls[1]["command"]


def test_live_job_is_returned_without_config_or_new_launch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(service, "read_job_status", lambda *a: {"state": "running", "pid": 123})
    monkeypatch.setattr(service, "launch_job", lambda **k: pytest.fail("duplicate launch"))
    assert service.main(["start", "--state-dir", str(tmp_path / "state")]) == 0
    assert json.loads(capsys.readouterr().out)["launch_result"] == "already_running"


def test_failed_job_requires_explicit_resume_or_new_run(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.yaml"
    config.write_text("fixture only")
    monkeypatch.setattr(service, "read_job_status", lambda *a: {"state": "failed"})
    monkeypatch.setattr(service, "launch_job", lambda **k: pytest.fail("must not launch"))
    assert service.main(["start", "--state-dir", str(tmp_path / "state"),
                         "--config", str(config)]) == 1
    assert "resume" in json.loads(capsys.readouterr().err)["message"]


def test_stop_refuses_unrelated_pid_before_any_signal(tmp_path, monkeypatch):
    signalled = []
    monkeypatch.setattr(service.os, "kill", lambda *args: signalled.append(args))
    with pytest.raises(RuntimeError, match="refusing"):
        service._verified_stop({"state": "running", "pid": os.getpid()}, tmp_path, "unrelated")
    assert signalled == []
    assert service._verified_stop({"state": "completed", "pid": os.getpid()}, tmp_path, "job")["result"] == "not_running"


@pytest.mark.parametrize("content", ["{broken", "[]", '{}',
    '{"job":"diagnostics","state":"running"}',
    '{"job":"diagnostics","state":"running","pid":true}'])
def test_corrupt_status_never_launches_another_job(tmp_path, monkeypatch, content):
    state = tmp_path / "state"
    state.mkdir()
    (state / "diagnostics.status.json").write_text(content)
    monkeypatch.setattr(service, "launch_job", lambda **k: pytest.fail("must not launch"))
    assert service.main(["start", "--state-dir", str(state)]) == 1


@pytest.mark.parametrize("completion,code", [("failed", 1), ("interrupted", 130), ("offline_complete", 0)])
def test_preflight_propagates_completion_exit_code(tmp_path, monkeypatch, completion, code):
    config = tmp_path / "config.yaml"
    config.write_text("fixture only")
    monkeypatch.setattr(service, "run_pipeline", lambda *a, **k: {"status": completion})
    assert service.main(["preflight", "--config", str(config),
                         "--state-dir", str(tmp_path / "state"),
                         "--run-root", str(tmp_path / "runs")]) == code


def _wait(predicate, *, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError("local detached process did not reach expected state")


def test_real_detached_monitor_live_log_duplicate_and_verified_stop(tmp_path):
    state, run = tmp_path / "state space", tmp_path / "run space" / "one"
    code = """
import json, os, signal, sys, time
from pathlib import Path
run = Path(sys.argv[1]); run.mkdir(parents=True)
def stop(signum, frame):
    (run / 'completion.json').write_text(json.dumps({'status': 'interrupted'}))
    print('clean-stop', flush=True)
    raise SystemExit(130)
signal.signal(signal.SIGTERM, stop)
(run / '.background_worker_ready.json').write_text(json.dumps({'pid': os.getpid()}))
print('ready-sid=' + str(os.getsid(0)), flush=True)
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    print('live-heartbeat', flush=True)
    time.sleep(.05)
"""
    launch = dict(job="diagnostics", state_dir=state, cwd=tmp_path,
                  command=[sys.executable, "-u", "-c", code, str(run)],
                  run_root=run.parent, run_prefix=run.name, exact_run_dir=run)
    result = launch_job(**launch)
    pid = result["pid"]
    try:
        log = state / "diagnostics.log"
        _wait(lambda: log.exists() and "live-heartbeat" in log.read_text())
        assert os.getsid(pid) == pid and pid != os.getsid(0)
        assert f"ready-sid={pid}" in log.read_text()
        duplicate = launch_job(**launch)
        assert duplicate["launch_result"] == "already_running"
        assert duplicate["pid"] == pid
        stopped = service._verified_stop(read_job_status(state, "diagnostics"), state, "diagnostics")
        assert stopped["result"] == "graceful_stop_requested"
        def terminal():
            status = read_job_status(state, "diagnostics")
            return status if status["state"] not in {"starting", "running"} else None
        status = _wait(terminal)
        assert status["state"] == "interrupted" and status["exit_code"] == 130
        assert json.loads((run / "completion.json").read_text())["status"] == "interrupted"
        assert "clean-stop" in log.read_text()
    finally:
        status = read_job_status(state, "diagnostics")
        if status.get("state") in {"starting", "running"}:
            service._verified_stop(status, state, "diagnostics")
