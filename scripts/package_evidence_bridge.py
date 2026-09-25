#!/usr/bin/env python3
"""Portable source/data/document package; caches and private files never enter."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PDF = "output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf"
ROOTS = (
    "src",
    "reference",
    "configs",
    "scripts",
    "tests",
    "docs",
    "data/raw",
    "data/processed",
    "data/README.md",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "reports/2026-09-23-mechanism-research",
    PDF,
)
REQUIRED = (
    "configs/evidence_bridge.yaml",
    "docs/evidence_bridge_implementation.md",
    "docs/evidence_bridge_runbook.md",
    "scripts/start_evidence_bridge_linux.sh",
    PDF,
    "data/raw/personamem-v1/questions_32k.csv",
    "data/raw/personamem-v1/shared_contexts_32k.jsonl",
    "data/processed/personamem-v1/32k/manifest.json",
    "data/processed/personamem-v1/32k/queries.jsonl",
    "data/processed/personamem-v1/32k/contexts.jsonl",
)


def excluded(path: Path) -> bool:
    bad_dirs = {".git", ".venv", "outputs", "__pycache__", ".pytest_cache", ".ruff_cache", "cache", "caches", ".cache"}
    for part in path.parts:
        value = part.lower()
        if part in bad_dirs or value.endswith(".egg-info") or value.startswith("._"):
            return True
        if any(term in value for term in ("credential", ".local.", ".private.", "secret")):
            return True
        if value in {".ds_store", ".env"} or value.startswith(".env."):
            return True
    return path.suffix.lower() in {".pyc", ".pyo", ".key", ".pem", ".p12", ".pfx", ".tmp"}


def package(repo: Path, destination: Path) -> tuple[Path, Path]:
    for name in REQUIRED:
        if not (repo / name).is_file():
            raise FileNotFoundError(f"required package artifact missing: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "bridge-tree-evidence.tar.gz"
    files = []
    for name in ROOTS:
        root = repo / name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*") if root.is_dir() else [root]):
            relative = path.relative_to(repo)
            if path.is_symlink() or not path.is_file() or excluded(relative):
                continue
            files.append((path, relative))
    with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as handle:
        for path, relative in files:
            handle.add(path, arcname=relative.as_posix(), recursive=False)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    manifest = {
        "archive": archive.name,
        "sha256": digest,
        "files": [str(p) for _, p in files],
        "excludes": "local credentials, virtualenvs, caches, old outputs, symlinks",
        "raw_and_processed_32k_included": True,
        "pdf_included": PDF,
    }
    (destination / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    for path in package(REPO, args.destination.expanduser().resolve()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
