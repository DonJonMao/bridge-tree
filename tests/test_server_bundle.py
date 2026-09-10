import hashlib
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from bridgetree.server_bundle import (
    PROJECT_NAME,
    _excluded,
    build_server_bundle,
    server_bundle_files,
    verify_bundle_offline_launcher,
    verify_server_bundle,
)


def test_server_bundle_is_scoped_hashed_and_runs_after_extraction(tmp_path):
    repository_root = Path(__file__).resolve().parents[1]
    selected = [path.relative_to(repository_root).as_posix() for path in server_bundle_files(repository_root)]
    assert "scripts/train_32k.sh" in selected
    assert "configs/train.yaml" in selected
    assert "configs/personamem32k_effect_first.yaml" in selected
    assert "scripts/run_effect_first_validation.sh" in selected
    assert "scripts/background_entrypoint.py" in selected
    assert "scripts/run_chain.sh" in selected
    assert "scripts/start_chain_linux.sh" in selected
    assert "scripts/start_effect_first_background.sh" in selected
    assert "scripts/start_train_32k_background.sh" in selected
    assert "src/bridgetree/background.py" in selected
    assert "src/bridgetree/guided_retriever.py" in selected
    assert "reference/semantic_core_reference.py" in selected
    assert "data/raw/personamem-v1/questions_32k.csv" in selected
    assert not any(".venv" in path or "outputs/" in path or "__pycache__" in path for path in selected)
    assert "configs/credentials.local.yaml" not in selected
    assert not any(path.startswith("data/protocol/") for path in selected)

    result = build_server_bundle(repository_root, tmp_path)
    archive = Path(result["archive"])
    checksum = Path(result["checksum_file"])
    assert archive.is_file()
    assert checksum.read_text(encoding="utf-8") == f"{result['archive_sha256']}  {archive.name}\n"
    assert result["verified"] is True
    assert result["launcher_executable"] is True
    assert verify_server_bundle(archive)["file_count"] == result["file_count"]

    with tarfile.open(archive, "r:gz") as handle:
        names = {member.name for member in handle.getmembers()}
    assert f"{PROJECT_NAME}/SERVER_BUNDLE_MANIFEST.json" in names
    assert f"{PROJECT_NAME}/scripts/train_32k.sh" in names
    assert not any("/.git/" in name or "/.venv/" in name or "/outputs/" in name for name in names)

    offline = verify_bundle_offline_launcher(archive, sys.executable)
    assert offline == {"offline_launcher_verified": True}


def test_generic_server_bundle_excludes_private_and_transient_paths():
    excluded = (
        "configs/credentials.local.yaml",
        "configs/service-credentials.json",
        ".env",
        "configs/.env.production",
        "configs/private.key",
        "configs/private.pem",
        "data/protocol/chain_full.json",
        "data/processed/32k/.contexts.jsonl.interrupted.tmp",
    )
    assert all(_excluded(Path(value)) for value in excluded)
    assert not _excluded(Path("configs/chain_full.yaml"))
    assert not _excluded(Path("data/processed/personamem-v1/32k/contexts.jsonl"))


def test_chain_shell_bundle_excludes_credentials_and_preparation_staging(tmp_path):
    repository_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "repository"
    for directory in (
        "src",
        "configs",
        "scripts",
        "tests",
        "docs",
        "reference",
        "data/raw",
        "data/processed/32k",
    ):
        (fixture_root / directory).mkdir(parents=True, exist_ok=True)
    for filename in (
        "pyproject.toml",
        "requirements.txt",
        "requirements-ascend910b.txt",
        "README.md",
        "data/README.md",
    ):
        path = fixture_root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {filename}\n", encoding="utf-8")

    script = fixture_root / "scripts/package_chain_server.sh"
    shutil.copy2(repository_root / "scripts/package_chain_server.sh", script)
    (fixture_root / "src/kept.py").write_text("KEPT = True\n", encoding="utf-8")
    (fixture_root / "reference/kept.py").write_text("KEPT = True\n", encoding="utf-8")
    (fixture_root / "src/._kept.py").write_text("AppleDouble metadata\n", encoding="utf-8")
    (fixture_root / "configs/credentials.local.yaml").write_text(
        "api_key: must-not-ship\n", encoding="utf-8"
    )
    (fixture_root / "configs/service-credential.json").write_text(
        '{"api_key": "must-not-ship"}\n', encoding="utf-8"
    )
    staging = fixture_root / "data/processed/32k/.contexts.jsonl.interrupted.tmp"
    staging.write_text("partial data must not ship\n", encoding="utf-8")

    destination = tmp_path / "bundle"
    subprocess.run(["bash", str(script), str(destination)], check=True, capture_output=True)
    archive = destination / "bridge-tree-chain.tar.gz"
    checksum = destination / "bridge-tree-chain.tar.gz.sha256"
    checksum_line = checksum.read_text(encoding="utf-8")
    assert checksum_line == (
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}"
        "  bridge-tree-chain.tar.gz\n"
    )
    with tarfile.open(archive, "r:gz") as handle:
        names = {member.name for member in handle.getmembers()}

    assert "src/kept.py" in names
    assert "reference/kept.py" in names
    assert "src/._kept.py" not in names
    assert "configs/credentials.local.yaml" not in names
    assert "configs/service-credential.json" not in names
    assert staging.relative_to(fixture_root).as_posix() not in names
    assert not any(name.endswith(".tmp") for name in names)
