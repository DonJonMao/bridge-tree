import sys
import tarfile
from pathlib import Path

from bridgetree.server_bundle import (
    PROJECT_NAME,
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
    assert "scripts/start_effect_first_background.sh" in selected
    assert "scripts/start_train_32k_background.sh" in selected
    assert "src/bridgetree/background.py" in selected
    assert "src/bridgetree/guided_retriever.py" in selected
    assert "data/raw/personamem-v1/questions_32k.csv" in selected
    assert not any(".venv" in path or "outputs/" in path or "__pycache__" in path for path in selected)

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
