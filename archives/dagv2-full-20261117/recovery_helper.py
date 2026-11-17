#!/usr/bin/env python3
"""Verify restored dagv2 directories; optionally repair archived link topology.

Default operation only reads the restored data. Repair flags are explicit.
Every manifest path and every ancestor directory is checked without following
symlinks. Absolute links outside the five archived directories are never changed.
"""
import argparse
import collections
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import posixpath
import stat
import sys
import time
import uuid


ROOT_NAMES = {
    "dagv2_analysis", "dagv2_deploy", "dagv2-personamem-v4",
    "dagv2-prefeval-v4-fix3", "dagv2-webwalker-v4",
}


def validate_path(value):
    if (not isinstance(value, str) or not value or "\0" in value
            or value.startswith("/") or posixpath.normpath(value) != value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or value.split("/")[0] not in ROOT_NAMES):
        raise ValueError("unsafe or unsupported manifest path")
    return value


class SafeRoot:
    def __init__(self, root):
        self.path = Path(root).resolve(strict=True)
        self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.fd)

    @contextmanager
    def parent(self, path):
        parts = validate_path(path).split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                new_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = new_fd
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def lstat(self, path):
        with self.parent(path) as (fd, name):
            return os.stat(name, dir_fd=fd, follow_symlinks=False)

    def readlink(self, path):
        with self.parent(path) as (fd, name):
            return os.readlink(name, dir_fd=fd)

    def digest(self, path, observed):
        with self.parent(path) as (parent_fd, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino):
                raise ValueError("file changed while opening")
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
            after = os.fstat(fd)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("file changed while hashing")
            return total, digest.hexdigest()
        finally:
            os.close(fd)

    def listdir(self, path):
        with self.parent(path) as (parent_fd, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            return set(os.listdir(fd))
        finally:
            os.close(fd)

    def set_directory_mtime(self, path, mtime_ns):
        with self.parent(path) as (parent_fd, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            before = os.fstat(fd)
            os.utime(fd, ns=(before.st_atime_ns, mtime_ns))
        finally:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="parent of the restored five directories")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--original-root", default="/Users/mao/projects")
    parser.add_argument("--source-root", action="append", choices=sorted(ROOT_NAMES))
    parser.add_argument("--restore-hardlinks", action="store_true")
    parser.add_argument("--relocate-absolute-symlinks", action="store_true")
    parser.add_argument("--report", help="optional JSON report outside the five restored directories")
    args = parser.parse_args()
    started = time.time()
    manifest_path = Path(args.manifest)
    entries = {}
    for line in manifest_path.open():
        entry = json.loads(line)
        path = validate_path(entry["path"])
        if path in entries:
            parser.error("duplicate manifest path")
        if entry.get("type") not in {"file", "directory", "symlink"}:
            parser.error("unsupported manifest entry type")
        entries[path] = entry
    selected = set(args.source_root or ROOT_NAMES)
    entries = {p: e for p, e in entries.items() if p.split("/")[0] in selected}
    if not entries:
        parser.error("no selected manifest entries")
    for name in {path.split("/")[0] for path in entries}:
        if name not in entries or entries[name]["type"] != "directory":
            parser.error("each selected source root must be a manifest directory")
    for path, entry in entries.items():
        parts = path.split("/")
        for length in range(1, len(parts)):
            parent = "/".join(parts[:length])
            if parent not in entries or entries[parent]["type"] != "directory":
                parser.error("manifest ancestor is missing or is not a directory")
    original_root = posixpath.normpath(args.original_root)
    if not original_root.startswith("/"):
        parser.error("--original-root must be absolute")
    safe = SafeRoot(args.root)
    if args.report:
        report_path = Path(args.report).resolve(strict=False)
        for name in ROOT_NAMES:
            if report_path == safe.path / name or safe.path / name in report_path.parents:
                parser.error("--report must be outside the five restored directories")
    errors = []
    error_count = 0
    checked_files = 0
    checked_bytes = 0
    current = {}
    symlink_states = collections.Counter()
    expected_children = collections.defaultdict(set)
    for path in entries:
        if "/" in path:
            parent, child = path.rsplit("/", 1)
            expected_children[parent].add(child)

    def fail(path, problem):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append({"path": path, "problem": problem})

    def relocated_target(target):
        if not posixpath.isabs(target):
            return None
        normalized = posixpath.normpath(target)
        prefix = original_root.rstrip("/") + "/"
        if not normalized.startswith(prefix):
            return None
        relative = normalized[len(prefix):]
        if relative.split("/")[0] not in ROOT_NAMES:
            return None
        return str(safe.path / relative)

    def verify_path(path, count=True):
        nonlocal checked_files, checked_bytes
        entry = entries[path]
        try:
            observed = safe.lstat(path)
            current[path] = observed
            kind = ("symlink" if stat.S_ISLNK(observed.st_mode) else "directory"
                    if stat.S_ISDIR(observed.st_mode) else "file"
                    if stat.S_ISREG(observed.st_mode) else "unsupported")
            if kind != entry["type"]:
                fail(path, "file type differs")
                return
            for key, actual in (("mode", stat.S_IMODE(observed.st_mode)), ("uid", observed.st_uid),
                                ("gid", observed.st_gid), ("mtime_ns", observed.st_mtime_ns)):
                if actual != entry[key]:
                    fail(path, key + " differs")
            if kind == "file":
                size, digest = safe.digest(path, observed)
                if count:
                    checked_files += 1
                    checked_bytes += size
                if size != entry["size"]:
                    fail(path, "file size differs")
                if digest != entry["sha256"]:
                    fail(path, "file SHA-256 differs")
            elif kind == "symlink":
                target = safe.readlink(path)
                relocated = relocated_target(entry["target"])
                if target == entry["target"]:
                    if count:
                        symlink_states["original"] += 1
                elif relocated is not None and target == relocated:
                    if count:
                        symlink_states["relocated"] += 1
                else:
                    fail(path, "symlink target differs from original and valid relocated target")
            else:
                actual = safe.listdir(path)
                wanted = expected_children[path]
                for name in sorted(actual - wanted):
                    fail(path + "/" + name, "unexpected filesystem entry")
                for name in sorted(wanted - actual):
                    fail(path + "/" + name, "missing filesystem entry")
        except (OSError, ValueError) as error:
            fail(path, type(error).__name__ + ": " + str(error))

    groups = collections.defaultdict(list)
    for path, entry in entries.items():
        if entry["type"] == "file" and entry.get("nlink", 1) > 1:
            groups[(entry["device"], entry["inode"])].append(path)
    groups = [sorted(paths) for paths in groups.values() if len(paths) > 1]
    for paths in groups:
        identity = {(entries[p]["size"], entries[p]["sha256"], entries[p]["mode"],
                     entries[p]["mtime_ns"], entries[p]["uid"], entries[p]["gid"]) for p in paths}
        if len(identity) != 1:
            parser.error("hardlink group has inconsistent manifest metadata")

    touched_dirs = set()
    changed_paths = set()
    actions = {"hardlinks_recreated": 0, "absolute_symlinks_relocated": 0}
    next_progress = 1000
    try:
        for path in sorted(entries):
            verify_path(path)
            if checked_files >= next_progress:
                print(json.dumps({"phase": "verify", "files": checked_files, "bytes": checked_bytes}), flush=True)
                next_progress += 1000
        initial_errors = error_count
        if not initial_errors and args.restore_hardlinks:
            for paths in groups:
                canonical = paths[0]
                for destination in paths[1:]:
                    source_stat = safe.lstat(canonical)
                    destination_stat = safe.lstat(destination)
                    if (source_stat.st_dev, source_stat.st_ino) == (destination_stat.st_dev, destination_stat.st_ino):
                        continue
                    if safe.digest(canonical, source_stat) != (entries[canonical]["size"], entries[canonical]["sha256"]):
                        raise ValueError("hardlink source changed after verification")
                    if safe.digest(destination, destination_stat) != (entries[destination]["size"], entries[destination]["sha256"]):
                        raise ValueError("hardlink destination changed after verification")
                    parent = destination.rsplit("/", 1)[0]
                    touched_dirs.add(parent)
                    temporary = ".dagv2-hardlink-" + uuid.uuid4().hex
                    with safe.parent(canonical) as (source_fd, source_name), safe.parent(destination) as (destination_fd, destination_name):
                        try:
                            os.link(source_name, temporary, src_dir_fd=source_fd, dst_dir_fd=destination_fd, follow_symlinks=False)
                            temporary_stat = os.stat(temporary, dir_fd=destination_fd, follow_symlinks=False)
                            if not stat.S_ISREG(temporary_stat.st_mode) or (temporary_stat.st_dev, temporary_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino):
                                raise ValueError("hardlink source changed during replacement")
                            os.replace(temporary, destination_name, src_dir_fd=destination_fd, dst_dir_fd=destination_fd)
                        finally:
                            try:
                                os.unlink(temporary, dir_fd=destination_fd)
                            except FileNotFoundError:
                                pass
                    changed_paths.update(paths)
                    actions["hardlinks_recreated"] += 1
        if not initial_errors and args.relocate_absolute_symlinks:
            for path, entry in entries.items():
                if entry["type"] != "symlink":
                    continue
                desired = relocated_target(entry["target"])
                if desired is None or desired == entry["target"] or safe.readlink(path) == desired:
                    continue
                before = safe.lstat(path)
                if not stat.S_ISLNK(before.st_mode) or safe.readlink(path) != entry["target"]:
                    raise ValueError("symlink changed after verification")
                parent = path.rsplit("/", 1)[0]
                touched_dirs.add(parent)
                temporary = ".dagv2-symlink-" + uuid.uuid4().hex
                with safe.parent(path) as (fd, name):
                    try:
                        os.symlink(desired, temporary, dir_fd=fd)
                        temp_stat = os.stat(temporary, dir_fd=fd, follow_symlinks=False)
                        if stat.S_IMODE(temp_stat.st_mode) != entry["mode"]:
                            os.chmod(temporary, entry["mode"], dir_fd=fd, follow_symlinks=False)
                        if (temp_stat.st_uid, temp_stat.st_gid) != (entry["uid"], entry["gid"]):
                            os.chown(temporary, entry["uid"], entry["gid"], dir_fd=fd, follow_symlinks=False)
                        os.utime(temporary, ns=(before.st_atime_ns, entry["mtime_ns"]), dir_fd=fd, follow_symlinks=False)
                        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
                    finally:
                        try:
                            os.unlink(temporary, dir_fd=fd)
                        except FileNotFoundError:
                            pass
                changed_paths.add(path)
                actions["absolute_symlinks_relocated"] += 1
    except (OSError, ValueError) as error:
        fail("", "repair stopped: " + type(error).__name__ + ": " + str(error))
    finally:
        for parent in touched_dirs:
            try:
                safe.set_directory_mtime(parent, entries[parent]["mtime_ns"])
            except (OSError, ValueError) as error:
                fail(parent, "could not preserve parent directory mtime: " + str(error))
    if changed_paths:
        for path in sorted(changed_paths | touched_dirs):
            verify_path(path, count=False)
    incomplete_groups = []
    for paths in groups:
        try:
            identities = {(safe.lstat(p).st_dev, safe.lstat(p).st_ino) for p in paths}
            if len(identities) != 1:
                incomplete_groups.append(paths)
        except OSError:
            incomplete_groups.append(paths)
    for paths in incomplete_groups:
        fail(paths[0], "hardlink topology differs; --restore-hardlinks can reconstruct this group")
    safe.close()
    result = {"success": error_count == 0, "entries": len(entries),
              "verified_files": checked_files, "verified_bytes": checked_bytes,
              "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "hardlink_groups": len(groups), "hardlink_groups_needing_repair": len(incomplete_groups),
              "symlink_states_before_repair": dict(symlink_states), "actions": actions,
              "errors": error_count, "first_errors": errors,
              "seconds": round(time.time() - started, 3)}
    if args.report:
        Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
