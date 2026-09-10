from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_module_log_resolves_recorded_run_and_rejects_unknown_names(tmp_path):
    state_dir = tmp_path / "state"
    run_dir = tmp_path / "runs" / "dependency_exact"
    module_dir = run_dir / "modules"
    shim_dir = tmp_path / "bin"
    state_dir.mkdir()
    module_dir.mkdir(parents=True)
    shim_dir.mkdir()
    (module_dir / "effectiveness.jsonl").write_text("{}\n", encoding="utf-8")
    (state_dir / "chain_full.run_dir").write_text(
        f"{run_dir}\n", encoding="utf-8"
    )
    tail = shim_dir / "tail"
    tail.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*"\n', encoding="utf-8")
    tail.chmod(0o755)
    environment = {
        **os.environ,
        "BACKGROUND_STATE_DIR": str(state_dir),
        "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    followed = subprocess.run(
        ["bash", "scripts/run_chain.sh", "module-log", "effectiveness"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert followed.stdout.strip() == (
        f"-n 100 -F {module_dir / 'effectiveness.jsonl'}"
    )

    rejected = subprocess.run(
        ["bash", "scripts/run_chain.sh", "module-log", "../secrets"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert "unknown Chain module log" in rejected.stderr


def test_linux_launcher_preflights_before_detached_start_without_service_calls(
    tmp_path,
):
    fixture_root = tmp_path / "repository"
    (fixture_root / "scripts").mkdir(parents=True)
    (fixture_root / "configs").mkdir()
    (fixture_root / "src" / "bridgetree").mkdir(parents=True)
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "start_chain_linux.sh",
        fixture_root / "scripts" / "start_chain_linux.sh",
    )
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "run_chain.sh",
        fixture_root / "scripts" / "run_chain.sh",
    )
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "background_entrypoint.py",
        fixture_root / "scripts" / "background_entrypoint.py",
    )
    shutil.copy2(
        REPOSITORY_ROOT / "src" / "bridgetree" / "background.py",
        fixture_root / "src" / "bridgetree" / "background.py",
    )
    (fixture_root / "configs" / "chain_full.yaml").write_text(
        "fixture: true\n", encoding="utf-8"
    )
    fake_venv = tmp_path / "venv"
    fake_bin = fake_venv / "bin"
    fake_bin.mkdir(parents=True)
    invocation_log = tmp_path / "python-invocations.log"
    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >> "$FAKE_PYTHON_LOG"\n'
        'case "$*" in\n'
        '  *"background_entrypoint.py status"*)\n'
        "    printf '%s\\n' \"$FAKE_STATUS_JSON\" ;;\n"
        '  *"chain_worker.py"*"--preflight-only"*)\n'
        "    printf '%s\\n' \"$FAKE_PREFLIGHT_JSON\" ;;\n"
        '  *"background_entrypoint.py start"*)\n'
        "    printf '%s\\n' \"$FAKE_START_JSON\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    (fake_venv / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
    fake_python.chmod(0o755)
    output_dir = tmp_path / "outputs"
    methods = [
        "dense",
        "dense_rerank",
        "activation",
        "context_marginal",
        "activation_fixed_pool",
    ]
    environment = {
        **os.environ,
        "BRIDGETREE_SETUP_PYTHON": sys.executable,
        "BRIDGETREE_VENV_DIR": str(fake_venv),
        "BRIDGETREE_SKIP_INSTALL": "true",
        "BRIDGETREE_ALLOW_NON_LINUX": "true",
        "BRIDGETREE_MIN_FREE_GB": "0",
        "BACKGROUND_STATE_DIR": str(tmp_path / "state"),
        "OUTPUT_DIR": str(output_dir),
        "FAKE_PYTHON_LOG": str(invocation_log),
        "FAKE_PREFLIGHT_JSON": (
            '{"status":"preflight_complete","dataset":{'
            '"questions":589,"synthetic":false,"split":"32k",'
            '"dataset_revision":"fd7c30f071d5c2ee2a211506783be222d7b6002e"},'
            '"expected_tasks":2945,"model_calls":0,"inference_complete":false,'
            f'"methods":{json.dumps(methods)},'
            '"summary":{"pending_tasks":2945}}'
        ),
        "FAKE_START_JSON": (
            '{"state":"starting","launch_result":"started",'
            '"monitor_ready":true,"run_dir":"/tmp/fake-dependency-run"}'
        ),
    }

    completed = subprocess.run(
        ["bash", "scripts/start_chain_linux.sh", "configs/chain_full.yaml"],
        cwd=fixture_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    invocations = invocation_log.read_text(encoding="utf-8").splitlines()
    preflight_index = next(
        index
        for index, line in enumerate(invocations)
        if "chain_worker.py" in line and "--preflight-only" in line
    )
    start_index = next(
        index
        for index, line in enumerate(invocations)
        if "background_entrypoint.py start" in line
    )
    assert preflight_index < start_index
    assert "Detached run submitted" in completed.stdout
    assert "optimizer_steps=0, weights_updated=false" in completed.stdout
    assert any("--exact-run-dir" in line for line in invocations[start_index:])

    starts_before = sum(
        "background_entrypoint.py start" in line for line in invocations
    )
    invalid_environment = {**environment, "FAKE_PREFLIGHT_JSON": "{}"}
    invalid = subprocess.run(
        ["bash", "scripts/start_chain_linux.sh", "configs/chain_full.yaml"],
        cwd=fixture_root,
        env=invalid_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
    assert "full data-only preflight contract failed" in invalid.stderr
    after_invalid = invocation_log.read_text(encoding="utf-8").splitlines()
    assert sum(
        "background_entrypoint.py start" in line for line in after_invalid
    ) == starts_before

    preflights_before = sum("chain_worker.py" in line for line in after_invalid)
    state_dir = Path(environment["BACKGROUND_STATE_DIR"])
    state_dir.mkdir(exist_ok=True)
    (state_dir / "chain_full.status.json").write_text(
        json.dumps({"job": "chain_full", "state": "running", "pid": os.getpid()}),
        encoding="utf-8",
    )
    active = subprocess.run(
        ["bash", "scripts/start_chain_linux.sh", "configs/chain_full.yaml"],
        cwd=fixture_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert active.returncode != 0
    assert "already active" in active.stderr
    after_active = invocation_log.read_text(encoding="utf-8").splitlines()
    assert sum("chain_worker.py" in line for line in after_active) == preflights_before


def test_linux_launch_scripts_are_executable_and_parse_as_bash():
    for name in ("scripts/start_chain_linux.sh", "scripts/run_chain.sh"):
        path = REPOSITORY_ROOT / name
        assert path.stat().st_mode & 0o111
        subprocess.run(["bash", "-n", str(path)], check=True)
