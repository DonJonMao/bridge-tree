"""Linux bootstrap acceptance with real venvs, stub pip/wrapper, zero network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


def fixture_repo(tmp_path, *, make_venv=True):
    repo = tmp_path / "repository with spaces"
    scripts, configs, package = repo / "scripts", repo / "configs", repo / "src" / "bridgetree"
    scripts.mkdir(parents=True)
    configs.mkdir()
    package.mkdir(parents=True)
    for name in ("start_diagnostics_linux.sh", "background_entrypoint.py"):
        shutil.copy2(REPO / "scripts" / name, scripts / name)
    shutil.copy2(REPO / "src" / "bridgetree" / "background.py", package / "background.py")
    config = configs / "diagnostic_28.server.yaml"
    config.write_text("fixture: true\n", encoding="utf-8")
    (scripts / "run_diagnostics.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\n'
        '"$BRIDGETREE_SETUP_PYTHON" - "$@" <<\'PY\'\n'
        'import json, os, sys\n'
        'from pathlib import Path\n'
        'value = {"args":sys.argv[1:], "python":os.environ["BRIDGETREE_BASE_PYTHON"], '
        '"state":os.environ["DIAGNOSTIC_STATE_DIR"], "root":os.environ["DIAGNOSTIC_RUN_ROOT"]}\n'
        'with Path(os.environ["FIXTURE_START_LOG"]).open("a") as f: f.write(json.dumps(value)+"\\n")\n'
        'print(json.dumps({"launch_result":"started", "state":"running", "monitor_ready":True}))\n'
        'raise SystemExit(int(os.environ.get("FIXTURE_START_EXIT", "0")))\n'
        'PY\n', encoding="utf-8",
    )
    stubs = tmp_path / "stub modules"
    stubs.mkdir()
    for module in ("bridgetree", "numpy", "yaml"):
        (stubs / (module + ".py")).write_text("# dependency import fixture only\n", encoding="utf-8")
    (stubs / "pip.py").write_text(
        'import json, os, sys, time\nfrom pathlib import Path\n'
        'with Path(os.environ["FIXTURE_PIP_LOG"]).open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
        'if sys.argv[1:] == ["--version"]: print("pip fixture"); raise SystemExit(0)\n'
        'assert sys.argv[1] == "install"\n'
        'print("fixture installation output", flush=True)\n'
        'if os.environ.get("FIXTURE_PIP_GATE"):\n'
        '    gate = Path(os.environ["FIXTURE_PIP_GATE"])\n'
        '    gate.with_suffix(".entered").touch()\n'
        '    deadline = time.monotonic() + 10\n'
        '    while not gate.exists() and time.monotonic() < deadline: time.sleep(.02)\n'
        '    if not gate.exists(): raise SystemExit("fixture gate timed out")\n'
        'if os.environ.get("FIXTURE_STATUS_AFTER_INSTALL"):\n'
        '    status = Path(os.environ["DIAGNOSTIC_STATE_DIR"]) / "diagnostics.status.json"\n'
        '    status.write_text(json.dumps({"job":"diagnostics", "state":"running", "pid":os.getppid()}))\n'
        'raise SystemExit(int(os.environ.get("FIXTURE_PIP_EXIT", "0")))\n', encoding="utf-8",
    )
    venv = repo / ".venv-diagnostics"
    if make_venv:
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True, capture_output=True)
    state, root = repo / "outputs" / "background-diagnostics", repo / "outputs" / "diagnostics"
    starts, installs = tmp_path / "starts.jsonl", tmp_path / "installs.jsonl"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("BRIDGETREE_", "DIAGNOSTIC_", "FIXTURE_"))}
    env.update(BRIDGETREE_SETUP_PYTHON=sys.executable, BRIDGETREE_ALLOW_NON_LINUX="true",
               PYTHONPATH=str(stubs), PIP_NO_INDEX="1", FIXTURE_START_LOG=str(starts),
               FIXTURE_PIP_LOG=str(installs), BRIDGETREE_CHAT_API_KEY="SECRET_NOT_FOR_BOOTSTRAP_OUTPUT")
    return SimpleNamespace(repo=repo, config=config, venv=venv, state=state, root=root,
                           env=env, starts=starts, installs=installs)


def run(fixture, *args, **environment):
    return subprocess.run(["bash", "scripts/start_diagnostics_linux.sh", *args], cwd=fixture.repo,
                          env={**fixture.env, **environment}, capture_output=True, text=True, timeout=30)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def set_status(fixture, state):
    fixture.state.mkdir(parents=True, exist_ok=True)
    (fixture.state / "diagnostics.status.json").write_text(
        json.dumps({"job": "diagnostics", "state": state, "pid": os.getpid()}), encoding="utf-8")


def test_installs_only_base_dependencies_then_delegates_absolute_offline_start(tmp_path):
    fixture = fixture_repo(tmp_path)
    completed = run(fixture, "--offline")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert rows(fixture.installs) == [["--version"],
        ["install", "--disable-pip-version-check", "--no-input", "-e", str(fixture.repo)]]
    assert rows(fixture.starts) == [{"args": ["start", "--config", str(fixture.config), "--offline"],
                                    "python": str(fixture.venv / "bin" / "python"),
                                    "state": str(fixture.state), "root": str(fixture.root)}]
    log = fixture.state / "bootstrap.log"
    assert "fixture installation output" in completed.stdout and "fixture installation output" in log.read_text()
    assert "optimizer_steps=0, weights_updated=false" in log.read_text()
    assert fixture.env["BRIDGETREE_CHAT_API_KEY"] not in completed.stdout + completed.stderr + log.read_text()
    assert log.stat().st_mode & 0o077 == 0
    assert not (fixture.repo / ".start_diagnostics_linux.lock").exists()


def test_explicit_config_and_output_overrides_and_skip_install(tmp_path):
    fixture = fixture_repo(tmp_path)
    config = fixture.repo / "configs" / "another config.yaml"
    config.write_text("fixture: alternate\n")
    state, root = tmp_path / "private state", tmp_path / "private runs"
    completed = run(fixture, "configs/another config.yaml", BRIDGETREE_SKIP_INSTALL="true",
                    DIAGNOSTIC_STATE_DIR=str(state), DIAGNOSTIC_RUN_ROOT=str(root))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not fixture.installs.exists()
    assert rows(fixture.starts)[0] == {"args": ["start", "--config", str(config)],
        "python": str(fixture.venv / "bin" / "python"), "state": str(state), "root": str(root)}


def test_first_bootstrap_creates_a_distinct_real_venv_before_stub_install(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    completed = run(fixture, "--offline")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (fixture.venv / "pyvenv.cfg").is_file()
    assert "Creating independent diagnostic virtual environment" in completed.stdout
    assert len([r for r in rows(fixture.installs) if r[0] == "install"]) == 1
    assert len(rows(fixture.starts)) == 1
    assert not (fixture.repo / ".venv").exists()


@pytest.mark.parametrize("state", ["starting", "running", "failed", "interrupted"])
def test_existing_active_or_resumable_run_blocks_before_any_venv_or_install(tmp_path, state):
    fixture = fixture_repo(tmp_path, make_venv=False)
    set_status(fixture, state)
    completed = run(fixture)
    assert completed.returncode != 0
    text = completed.stdout + completed.stderr
    assert ("already active" if state in {"starting", "running"} else "resume") in text
    assert not fixture.venv.exists() and not fixture.installs.exists() and not fixture.starts.exists()
    assert not (fixture.repo / ".start_diagnostics_linux.lock").exists()


def test_completed_run_allows_new_start(tmp_path):
    fixture = fixture_repo(tmp_path)
    set_status(fixture, "completed")
    completed = run(fixture, BRIDGETREE_SKIP_INSTALL="true")
    assert completed.returncode == 0 and len(rows(fixture.starts)) == 1


@pytest.mark.parametrize("content", ["{truncated", "[]", '{"job":"other","state":"completed"}'])
def test_corrupt_status_does_not_become_not_started(tmp_path, content):
    fixture = fixture_repo(tmp_path, make_venv=False)
    fixture.state.mkdir(parents=True)
    (fixture.state / "diagnostics.status.json").write_text(content)
    completed = run(fixture)
    assert completed.returncode != 0 and "cannot validate existing diagnostic status" in completed.stdout
    assert not fixture.venv.exists() and not fixture.installs.exists() and not fixture.starts.exists()


def test_incomplete_venv_is_left_untouched(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    fixture.venv.mkdir()
    sentinel = fixture.venv / "preserve-me"
    sentinel.write_text("existing data")
    completed = run(fixture)
    assert completed.returncode != 0 and "incomplete virtual environment" in completed.stdout
    assert list(fixture.venv.iterdir()) == [sentinel] and sentinel.read_text() == "existing data"
    assert not fixture.installs.exists() and not fixture.starts.exists()


def test_existing_python_that_is_not_a_venv_is_rejected(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    (fixture.venv / "bin").mkdir(parents=True)
    (fixture.venv / "pyvenv.cfg").write_text("home = fixture\n")
    (fixture.venv / "bin" / "python").write_text('#!/usr/bin/env bash\nexec "$BRIDGETREE_SETUP_PYTHON" "$@"\n')
    (fixture.venv / "bin" / "python").chmod(0o755)
    completed = run(fixture)
    assert completed.returncode != 0 and "identity mismatch" in completed.stdout
    assert not fixture.installs.exists() and not fixture.starts.exists()


def test_dangling_venv_symlink_is_not_repaired_by_creating_its_target(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    missing_target = tmp_path / "missing-environment"
    fixture.venv.symlink_to(missing_target, target_is_directory=True)
    completed = run(fixture)
    assert completed.returncode != 0 and "dangling virtual environment symlink" in completed.stderr
    assert fixture.venv.is_symlink() and not missing_target.exists()
    assert not fixture.installs.exists() and not fixture.starts.exists()


@pytest.mark.parametrize("target", ["/", "home", "repo", "overlap", "nested"])
def test_unsafe_and_conflicting_output_paths_are_rejected_before_setup(tmp_path, target):
    fixture = fixture_repo(tmp_path, make_venv=False)
    paths = {"/": "/", "home": str(Path.home()), "repo": str(fixture.repo),
             "overlap": str(fixture.root), "nested": str(fixture.root / "state")}
    completed = run(fixture, DIAGNOSTIC_STATE_DIR=paths[target])
    assert completed.returncode != 0
    assert "unsafe" in completed.stderr or "conflicting" in completed.stderr
    assert not fixture.venv.exists() and not fixture.installs.exists() and not fixture.starts.exists()


def test_venv_cannot_overlap_run_root_and_symlink_cannot_hide_repo_target(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    rejected = run(fixture, BRIDGETREE_VENV_DIR=str(fixture.root / "venv"))
    assert rejected.returncode != 0 and "conflicting" in rejected.stderr
    link = tmp_path / "repo-alias"
    link.symlink_to(fixture.repo, target_is_directory=True)
    rejected = run(fixture, DIAGNOSTIC_RUN_ROOT=str(link))
    assert rejected.returncode != 0 and "unsafe" in rejected.stderr
    assert not fixture.installs.exists() and not fixture.starts.exists()


def test_pip_failure_is_teed_and_prevents_start(tmp_path):
    fixture = fixture_repo(tmp_path)
    completed = run(fixture, FIXTURE_PIP_EXIT="37")
    assert completed.returncode == 37
    assert "fixture installation output" in (fixture.state / "bootstrap.log").read_text()
    assert not fixture.starts.exists()
    assert not (fixture.repo / ".start_diagnostics_linux.lock").exists()


def test_start_failure_propagates_through_tee(tmp_path):
    fixture = fixture_repo(tmp_path)
    completed = run(fixture, FIXTURE_START_EXIT="23", BRIDGETREE_SKIP_INSTALL="true")
    assert completed.returncode == 23 and len(rows(fixture.starts)) == 1


def test_status_is_rechecked_after_install_before_start(tmp_path):
    fixture = fixture_repo(tmp_path)
    completed = run(fixture, FIXTURE_STATUS_AFTER_INSTALL="true")
    assert completed.returncode != 0 and "already active" in completed.stdout
    assert len([r for r in rows(fixture.installs) if r[0] == "install"]) == 1
    assert not fixture.starts.exists()


def test_concurrent_bootstraps_cannot_both_install_even_with_different_state_directories(tmp_path):
    fixture = fixture_repo(tmp_path)
    gate = tmp_path / "installer.gate"
    first = subprocess.Popen(["bash", "scripts/start_diagnostics_linux.sh"], cwd=fixture.repo,
                             env={**fixture.env, "FIXTURE_PIP_GATE": str(gate)}, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 8
        while not gate.with_suffix(".entered").exists() and time.monotonic() < deadline:
            if first.poll() is not None:
                pytest.fail("first bootstrap exited before the installer gate: " + str(first.communicate()))
            time.sleep(.02)
        assert gate.with_suffix(".entered").exists()
        second = run(fixture, DIAGNOSTIC_STATE_DIR=str(tmp_path / "other-state"))
        assert second.returncode != 0 and "bootstrap lock exists" in second.stderr
        assert len([r for r in rows(fixture.installs) if r[0] == "install"]) == 1
        gate.touch()
        stdout, stderr = first.communicate(timeout=10)
        assert first.returncode == 0, stdout + stderr
        assert len(rows(fixture.starts)) == 1
    finally:
        gate.touch()
        if first.poll() is None:
            first.terminate()
            first.communicate(timeout=10)


def test_stale_or_unverifiable_bootstrap_lock_is_not_deleted(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    lock = fixture.repo / ".start_diagnostics_linux.lock"
    lock.mkdir()
    (lock / "pid").write_text("not-a-trustworthy-pid\n")
    completed = run(fixture)
    assert completed.returncode != 0 and "Verify its recorded PID" in completed.stderr
    assert (lock / "pid").read_text() == "not-a-trustworthy-pid\n"
    assert not fixture.venv.exists() and not fixture.installs.exists()


@pytest.mark.parametrize("target", ["bootstrap.log", "diagnostics.status.json"])
def test_symlink_log_or_status_is_not_followed(tmp_path, target):
    fixture = fixture_repo(tmp_path, make_venv=False)
    fixture.state.mkdir(parents=True)
    protected = tmp_path / "protected.txt"
    protected.write_text("unchanged")
    (fixture.state / target).symlink_to(protected)
    completed = run(fixture)
    assert completed.returncode != 0 and protected.read_text() == "unchanged"
    assert not fixture.venv.exists() and not fixture.installs.exists() and not fixture.starts.exists()


def test_linux_gate_boolean_flags_usage_and_shell_syntax(tmp_path):
    fixture = fixture_repo(tmp_path, make_venv=False)
    shim = tmp_path / "bin"
    shim.mkdir()
    uname = shim / "uname"
    uname.write_text('#!/usr/bin/env bash\nprintf "Darwin\\n"\n')
    uname.chmod(0o755)
    rejected = run(fixture, BRIDGETREE_ALLOW_NON_LINUX="false", PATH=f"{shim}:{os.environ['PATH']}")
    assert rejected.returncode != 0 and "only supports Linux" in rejected.stderr
    rejected = run(fixture, BRIDGETREE_SKIP_INSTALL="yes")
    assert rejected.returncode == 2 and "must be true or false" in rejected.stderr
    assert run(fixture, "--unknown").returncode == 2
    assert run(fixture, "--offline", "--offline").returncode == 2
    assert run(fixture, "--help").returncode == 0
    script = REPO / "scripts" / "start_diagnostics_linux.sh"
    assert script.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(script)], check=True)
