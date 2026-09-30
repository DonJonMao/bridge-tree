from __future__ import annotations

import hashlib
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
from types import SimpleNamespace

import pytest

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
    assert row["evidence_reliability"]["completion_cohorts"]["unknown"]["tasks"] == 1
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
    destination = tmp_path / "dist"
    destination.mkdir()
    old_archive = destination / "bridge-tree-evidence-v2.tar.gz"
    old_archive.write_bytes(b"previously distributed v2 archive")
    archive, checksum = module.package(repo, destination)
    with tarfile.open(archive) as handle:
        names = handle.getnames()
    assert all(name in names for name in module.REQUIRED)
    assert "data/raw/real.txt" in names
    assert not any(module.excluded(Path(name)) for name in names)
    assert "configs/link.yaml" not in names
    assert len(checksum.read_text().split()[0]) == 64
    assert archive.name == "bridge-tree-evidence-v3.tar.gz"
    manifest = json.loads((archive.parent / "package_manifest.json").read_text())
    assert manifest["method_release"] == "evidence_bridge_v3"
    assert old_archive.read_bytes() == b"previously distributed v2 archive"


def test_completion_cohorts_preserve_unknown_and_do_not_count_retries(tmp_path):
    from bridgetree.evidence_diagnostics import evidence_bridge_summary, reliability_cohorts

    statuses = ["normal", "truncated", "partially_mapped", "truncated_and_partially_mapped"]
    rows = []
    for index, status in enumerate(statuses):
        diagnostics = {
            "reliability_status": status,
            "selection_input_truncated": "truncated" in status,
            "partially_mapped": "partially_mapped" in status,
            "unavailable_unit_count": index,
        }
        summary = evidence_bridge_summary({"evidence_selection": {"diagnostics": diagnostics}}, {}, [])
        assert summary["reliability"] == diagnostics
        rows.append({
            "status": "success", "correct": index % 2 == 0, "attempt": 4,
            "diagnostics": {"evidence_bridge_summary": summary},
            "costs": {"evidence_calls": index + 1, "missing_metric": None},
        })
    rows.extend([
        {"status": "success", "correct": False, "diagnostics": {}, "costs": {}},
        {"status": "error", "costs": {"evidence_calls": 24}},
    ])
    result = reliability_cohorts(rows)
    assert (result["successful_tasks"], result["failed_tasks"]) == (5, 1)
    assert sum(value["tasks"] for value in result["completion_cohorts"].values()) == 5
    for index, name in enumerate(statuses):
        group = result["completion_cohorts"][name]
        assert group["tasks"] == 1
        assert group["accuracy"] == (1.0 if index % 2 == 0 else 0.0)
        assert group["cost_metrics"]["evidence_calls"]["sum"] == index + 1
        assert "missing_metric" not in group["cost_metrics"]
    assert result["failure_cost_metrics"]["evidence_calls"]["sum"] == 24


def test_standard_summary_includes_current_evidence_completion_cohorts():
    from bridgetree.dependency_experiment import DependencyOutcome, DependencyTask, summarize_dependency_outcomes

    task = DependencyTask("rev", "32k", "persona", "q", "evidence_bridge", "cfg", "data", "source", "protocol")
    outcome = DependencyOutcome(
        task, "success", 3, 0, 1, prediction="(a)", correct=True,
        diagnostics={"evidence_bridge_summary": {"reliability": {"reliability_status": "partially_mapped"}}},
        costs={"evidence_calls": 6},
    )
    summary = summarize_dependency_outcomes([task], [outcome])
    cohorts = summary["methods"][0]["evidence_reliability"]["completion_cohorts"]
    assert cohorts["partially_mapped"]["tasks"] == 1
    assert cohorts["normal"]["tasks"] == 0
    assert cohorts["partially_mapped"]["cost_metrics"]["evidence_calls"]["sum"] == 6


def test_new_source_modules_affect_identity_with_git_and_in_extracted_package(tmp_path, monkeypatch):
    from bridgetree import protocol

    root = tmp_path / "repo"
    names = ("src/bridgetree/evidence_protocol.py", "src/bridgetree/evidence_spans.py")
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("version = 1\n")
    monkeypatch.setattr(protocol, "__file__", str(root / "src/bridgetree/protocol.py"))
    git_available = True

    def git_files(*args, **kwargs):
        return SimpleNamespace(returncode=0 if git_available else 1, stdout="\n".join(names))

    monkeypatch.setattr(protocol.subprocess, "run", git_files)
    before = protocol._source_package_snapshot()
    git_available = False
    assert protocol._source_package_snapshot() == before
    for name in names:
        (root / name).write_text("version = 2\n")
        after = protocol._source_package_snapshot()
        assert after != before
        git_available = True
        assert protocol._source_package_snapshot() == after
        git_available = False
        before = after


def test_log_export_includes_raw_artifacts_but_not_project_secrets(tmp_path):
    module = load_script("export_evidence_bridge_logs")
    run = tmp_path / "run"
    run.mkdir()
    (run / "planned_tasks.jsonl").write_text('{"task_id":"a"}\n')
    for name in ("outcomes/a.json", "candidate_pool/a.json", "evidence_live/a.json", "modules/evidence.jsonl"):
        path = run / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('{"raw_response":"evidence fixture"}\n')
    private = run / "credentials.local.yaml"
    private.write_text("secret-value")
    (run / "candidate_pool/private.json").symlink_to(private)
    archive, checksum = module.export_logs(run, tmp_path / "export")
    with tarfile.open(archive) as handle:
        names = handle.getnames()
        assert "run/evidence_live/a.json" in names
        assert not any("private" in name or "credential" in name for name in names)
        manifest = json.load(handle.extractfile("export_manifest.json"))
        assert manifest["transactional_snapshot"] is False
        assert manifest["skipped"] == [{"path": "candidate_pool/private.json", "reason": "symlink"}]
        for record in manifest["files"]:
            payload = handle.extractfile("run/" + record["path"]).read()
            assert hashlib.sha256(payload).hexdigest() == record["sha256"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == checksum.read_text().split()[0]
    assert archive.stat().st_mode & 0o777 == 0o600


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


@pytest.mark.parametrize("custom_paths", [False, True])
def test_real_detached_start_stop_resume_and_linux_bootstrap(tmp_path, custom_paths):
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
    (repo / "scripts/probe_evidence_protocol.py").write_text(
        "import argparse,json,os\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--override-config');"
        "p.add_argument('--output');a=p.parse_args();"
        "Path(a.output).write_text(json.dumps(vars(a)));"
        "raise SystemExit(1 if os.environ.get('FAKE_PROTOCOL_INVALID') else 0)\n"
    )
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
    state = tmp_path / "state" if custom_paths else repo / "outputs/background-evidence-bridge-v3"
    run_root = tmp_path / "runs" if custom_paths else repo / "outputs/evidence-bridge-v3"
    env = {
        **{key: value for key, value in os.environ.items() if key not in {"BACKGROUND_STATE_DIR", "OUTPUT_DIR"}},
        "BRIDGETREE_SETUP_PYTHON": sys.executable,
        "BRIDGETREE_BASE_PYTHON": sys.executable,
        "BRIDGETREE_VENV_DIR": str(venv),
        "BRIDGETREE_SKIP_INSTALL": "true",
        "BRIDGETREE_ALLOW_NON_LINUX": "true",
        "BRIDGETREE_DEPLOYMENT_CONFIG": str(deployment),
    }
    if custom_paths:
        env.update(BACKGROUND_STATE_DIR=str(state), OUTPUT_DIR=str(run_root))

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
        probe = json.loads((state / "evidence_protocol_probe.json").read_text())
        assert probe["override_config"] == str(deployment)
        status = poll(lambda s: s["state"] == "running")
        run = Path(status["run_dir"])
        assert run.parent == run_root
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
        del env["FAKE_PREFLIGHT_INVALID"]
        env["FAKE_PROTOCOL_INVALID"] = "1"
        invalid_protocol = subprocess.run(
            ["bash", "scripts/start_evidence_bridge_linux.sh"], cwd=repo, env=env,
            capture_output=True, text=True,
        )
        assert invalid_protocol.returncode != 0
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


def test_v3_default_management_does_not_read_v1_or_v2_state(tmp_path):
    repo = tmp_path / "repo"
    for name in ("scripts/evidence_bridge_control.py", "src/bridgetree/background.py"):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    old_states = []
    for suffix, run_dir in (("", "/v1-run"), ("-v2", "/v2-run")):
        old = repo / f"outputs/background-evidence-bridge{suffix}"
        old.mkdir(parents=True)
        state_file = old / "evidence_bridge.status.json"
        state_file.write_text(json.dumps({"state": "interrupted", "run_dir": run_dir}))
        old_states.append((state_file, run_dir))
    env = {key: value for key, value in os.environ.items() if key not in {"BACKGROUND_STATE_DIR", "OUTPUT_DIR"}}
    result = subprocess.run(
        [sys.executable, "-S", "scripts/evidence_bridge_control.py", "status"],
        cwd=repo, capture_output=True, text=True, env=env, check=True,
    )
    assert json.loads(result.stdout)["state"] == "not_started"
    assert all(json.loads(path.read_text())["run_dir"] == run_dir for path, run_dir in old_states)
