from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_uses_current_outcomes_and_missing_fields(tmp_path):
    module = load_script("summarize_evidence_bridge")
    plan = [
        {"task_id": "a", "method_id": "evidence_bridge"},
        {"task_id": "b", "method_id": "evidence_bridge"},
        {"task_id": "c", "method_id": "evidence_bridge"},
    ]
    (tmp_path / "planned_tasks.jsonl").write_text("\n".join(map(json.dumps, plan)))
    outcomes = tmp_path / "outcomes"
    outcomes.mkdir()
    (outcomes / "a.json").write_text(
        json.dumps(
            {
                "task": plan[0],
                "status": "success",
                "attempt": 3,
                "correct": True,
                "selected_ids": ["m1"],
                "diagnostics": {"evidence_bridge_summary": {"search": {"roots_visited": 4}}},
                "costs": {"evidence": {"calls": 5}},
            }
        )
    )
    (outcomes / "b.json").write_text(
        json.dumps(
            {
                "task": plan[1],
                "status": "error",
                "attempt": 2,
                "error_type": "EvidenceSchemaError",
                "diagnostics": {},
                "costs": {},
            }
        )
    )
    (tmp_path / "predictions.jsonl").write_text("ignored retry history\n" * 20)
    result = module.summarize(tmp_path)
    row = result["methods"]["evidence_bridge"]
    assert (row["successful_tasks"], row["failed_tasks"], row["pending_tasks"]) == (1, 1, 1)
    assert row["mechanism_summary_absent_tasks"] == 1
    assert row["mechanism_metrics"]["search.roots_visited"] == {
        "observed_tasks": 1,
        "missing_tasks": 1,
        "sum": 4,
        "mean": 4,
        "min": 4,
        "max": 4,
    }
    assert row["success_accuracy"] == 1.0
    # Wrong identity must be visible, never silently counted as a valid task.
    (outcomes / "c.json").write_text(json.dumps({"task": {**plan[2], "method_id": "other"}, "status": "success"}))
    assert len(module.summarize(tmp_path)["invalid_outcome_files"]) == 1


def test_package_contains_data_pdf_and_excludes_private_state(tmp_path):
    module = load_script("package_evidence_bridge")
    repo = tmp_path / "repo"
    for name in module.REQUIRED:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    for name in (
        "configs/credentials.local.yaml",
        "configs/server.local.yaml",
        "scripts/__pycache__/x.pyc",
        "outputs/old-run/secret.json",
        ".venv/bin/python",
        "src/bridgetree/cache/x",
        "data/raw/real.txt",
    ):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    (repo / "configs" / "link.yaml").symlink_to(repo / "configs/credentials.local.yaml")
    archive, checksum = module.package(repo, tmp_path / "dist")
    with tarfile.open(archive) as handle:
        names = handle.getnames()
    assert all(name in names for name in module.REQUIRED)
    assert "data/raw/real.txt" in names
    assert not any(module.excluded(Path(name)) for name in names)
    assert "configs/link.yaml" not in names
    assert len(checksum.read_text().split()[0]) == 64


FAKE_WORKER = """from pathlib import Path
import argparse,json,os,signal,time
p=argparse.ArgumentParser()
p.add_argument('--config');p.add_argument('--output-dir');p.add_argument('--override-config')
p.add_argument('--resume',action='store_true');p.add_argument('--preflight-only',action='store_true')
a=p.parse_args();root=Path(a.output_dir);root.mkdir(parents=True,exist_ok=True)
methods=['dense','activation','evidence_bridge']
if a.preflight_only:
 if os.environ.get('FAKE_PREFLIGHT_INVALID'): methods=['dense']
 print(json.dumps(dict(status='preflight_complete',model_calls=0,inference_complete=False,methods=methods,
 dataset=dict(questions=589,synthetic=False,split='32k',dataset_revision='fd7c30f071d5c2ee2a211506783be222d7b6002e'),
 expected_tasks=1767,summary=dict(pending_tasks=1767))))
 raise SystemExit(0)
(root/'.background_worker_ready.json').write_text(json.dumps(dict(pid=os.getpid())))
(root/'config_seen.json').write_text(json.dumps(vars(a)))
def finish(sig=None,frame=None):
 for name in ['summary.json','progress.json','completion.json']:
  (root/name).write_text(json.dumps(dict(status='interrupted' if sig else 'completed')))
 raise SystemExit(130 if sig else 0)
signal.signal(signal.SIGTERM,finish)
if a.resume:
 (root/'resumed').write_text('true');finish()
(root/'begun').write_text('true')
while True: time.sleep(.01)
"""


def test_real_detached_start_stop_resume_and_linux_bootstrap(tmp_path):
    repo = tmp_path / "repo with spaces"
    for name in (
        "scripts/run_evidence_bridge.sh",
        "scripts/start_evidence_bridge_linux.sh",
        "scripts/evidence_bridge_control.py",
        "scripts/background_entrypoint.py",
        "src/bridgetree/background.py",
    ):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (repo / "src/bridgetree/__init__.py").write_text("")
    (repo / "scripts/chain_worker.py").write_text(FAKE_WORKER)
    (repo / "configs").mkdir()
    config = repo / "configs/evidence_bridge.yaml"
    config.write_text("fixture: true\n")
    deployment = repo / "configs/server.local.yaml"
    deployment.write_text("fixture: true\n")
    venv = repo / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
    (venv / "bin/python").chmod(0o755)
    (venv / "pyvenv.cfg").write_text("fixture\n")
    state = tmp_path / "state"
    env = {
        **os.environ,
        "BRIDGETREE_SETUP_PYTHON": sys.executable,
        "BRIDGETREE_BASE_PYTHON": sys.executable,
        "BRIDGETREE_VENV_DIR": str(venv),
        "BRIDGETREE_SKIP_INSTALL": "true",
        "BRIDGETREE_ALLOW_NON_LINUX": "true",
        "BRIDGETREE_DEPLOYMENT_CONFIG": str(deployment),
        "BACKGROUND_STATE_DIR": str(state),
        "OUTPUT_DIR": str(tmp_path / "runs"),
    }

    def command(*args):
        return subprocess.run(
            ["bash", "scripts/run_evidence_bridge.sh", *args],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    def poll(predicate):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = json.loads(command("status").stdout)
            if predicate(value):
                return value
            time.sleep(0.05)
        raise AssertionError(f"background process did not reach expected state: {value}")

    try:
        launch = subprocess.run(
            ["bash", "scripts/start_evidence_bridge_linux.sh"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Detached inference submitted" in launch.stdout
        status = poll(lambda s: s["state"] == "running")
        run = Path(status["run_dir"])
        deadline = time.monotonic() + 5
        while not (run / "begun").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (run / "begun").is_file()
        original_pid = status["pid"]
        assert json.loads(command("start").stdout)["pid"] == original_pid
        assert json.loads(command("stop").stdout)["stop_requested"] is True
        poll(lambda s: s["state"] == "interrupted")
        env["BRIDGETREE_DEPLOYMENT_CONFIG"] = "/nonexistent/ignored-on-resume.yaml"
        resumed = json.loads(command("resume").stdout)
        assert Path(resumed["run_dir"]) == run
        poll(lambda s: s["state"] == "completed")
        assert (run / "resumed").is_file()
        config_seen = json.loads((run / "config_seen.json").read_text())
        assert config_seen["config"] == str(config)
        assert config_seen["override_config"] == str(deployment)
        assert config_seen["resume"] is True
        assert (state / "evidence_bridge.log").is_file()
        assert (state / "history").is_dir()
        # An invalid preflight must not submit another detached worker.
        env["BRIDGETREE_DEPLOYMENT_CONFIG"] = str(deployment)
        env["FAKE_PREFLIGHT_INVALID"] = "1"
        invalid = subprocess.run(
            ["bash", "scripts/start_evidence_bridge_linux.sh"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        assert invalid.returncode != 0
        assert "full 32k data-only preflight failed" in invalid.stderr
        assert json.loads(command("status").stdout)["run_dir"] == str(run)
    finally:
        command("stop")


def test_scripts_parse_as_bash_and_reject_module_path(tmp_path):
    for name in ("run_evidence_bridge.sh", "start_evidence_bridge_linux.sh", "package_evidence_bridge.sh"):
        assert (ROOT / "scripts" / name).stat().st_mode & 0o111
        subprocess.run(["bash", "-n", str(ROOT / "scripts" / name)], check=True)
    result = subprocess.run(
        ["bash", "scripts/run_evidence_bridge.sh", "module-log", "../credentials"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "BRIDGETREE_BASE_PYTHON": sys.executable, "BACKGROUND_STATE_DIR": str(tmp_path)},
    )
    assert result.returncode == 2
    assert "unknown module" in result.stderr


def test_controller_bootstrap_needs_no_installed_scientific_packages(tmp_path):
    # -S disables site-packages: fresh-server status must work before pip or
    # importing bridgetree.__init__ and its numpy/PyYAML dependencies.
    result = subprocess.run(
        [sys.executable, "-S", "scripts/evidence_bridge_control.py", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "BACKGROUND_STATE_DIR": str(tmp_path / "fresh-state")},
    )
    assert json.loads(result.stdout)["state"] == "not_started"
