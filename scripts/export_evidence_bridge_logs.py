#!/usr/bin/env python3
"""Export a bounded run-artifact snapshot, including raw evidence requests/responses."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import tempfile
import time
from pathlib import Path

ROOT_FILES = (
    "run_manifest.json", "resolved_config.json", "planned_tasks.jsonl",
    "summary.json", "progress.json", "metrics.csv", "completion.json", "train.log",
    "mechanism_summary.json", "mechanism_summary.md", "predictions.jsonl", "failures.jsonl",
    "events.jsonl", "service_probe.json", "service_probes.jsonl",
)
DIRECTORIES = ("outcomes", "candidate_pool", "evidence_live", "visible_memories", "modules", "reports")


class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size):
        value = self.stream.read(size)
        self.digest.update(value)
        return value


def export_logs(run: Path, destination: Path) -> tuple[Path, Path]:
    run = run.resolve()
    if not (run / "planned_tasks.jsonl").is_file():
        raise ValueError(f"no frozen task plan under {run}")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    name = f"evidence_logs_{run.name}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.tar.gz"
    archive = destination / name
    if archive.exists():
        raise FileExistsError(archive)
    paths = [run / name for name in ROOT_FILES if (run / name).is_file()]
    for directory in DIRECTORIES:
        root = run / directory
        if root.is_dir() and not root.is_symlink():
            paths.extend(sorted(path for path in root.rglob("*") if path.is_file()))
    started = time.time()
    records = []
    skipped = []
    fd, temporary = tempfile.mkstemp(prefix=".evidence-export-", suffix=".tmp", dir=destination)
    os.close(fd)
    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as handle:
            for path in paths:
                relative = path.relative_to(run)
                if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != run):
                    skipped.append({"path": str(relative), "reason": "symlink"})
                    continue
                # Open once: atomic writer replacement cannot mix old/new JSON bytes.
                # For growing JSONL, read only the size observed at open time.
                with path.open("rb") as stream:
                    before = os.fstat(stream.fileno())
                    info = tarfile.TarInfo(f"run/{relative.as_posix()}")
                    info.size = before.st_size
                    info.mode = 0o600
                    info.mtime = before.st_mtime
                    reader = HashedReader(stream)
                    handle.addfile(info, reader)
                    after = os.fstat(stream.fileno())
                records.append({
                    "path": str(relative), "bytes": before.st_size, "sha256": reader.digest.hexdigest(),
                    "changed_while_reading": (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns),
                })
            manifest = {
                "schema_version": 1, "run_name": run.name, "started_at_epoch": started,
                "finished_at_epoch": time.time(), "transactional_snapshot": False,
                "source": "allowlisted run artifacts only; no project configuration files or environment",
                "note": "Running exports may end JSONL files mid-record. Current outcome JSON is authoritative.",
                "files": records, "skipped": skipped,
            }
            data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            info = tarfile.TarInfo("export_manifest.json")
            info.size = len(data)
            info.mode = 0o600
            handle.addfile(info, io.BytesIO(data))
        os.replace(temporary, archive)
    finally:
        Path(temporary).unlink(missing_ok=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8")
    checksum.chmod(0o600)
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/exports")
    args = parser.parse_args()
    for path in export_logs(args.run_dir.expanduser(), args.destination.expanduser()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
