#!/usr/bin/env python3
"""Restore or verify the browsable dagv2 source archive, without following links.

Default --verify-only reads a restored tree.  --restore is required to write.
--verify-remote checks the immutable GitHub copy and never writes source data.
--from-remote --restore restores directly from that copy without cloning it.
Encrypted metadata stays in memory; individual AES-GCM chunks are authenticated
before plaintext is yielded.  The original per-file checksum comes from the
authenticated, encrypted source manifest, including for private originals.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from contextlib import contextmanager
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import sys
import time
from typing import Any, Iterator
import urllib.error
import urllib.parse
import urllib.request
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


ROOT_NAMES = frozenset({
    "dagv2_analysis", "dagv2_deploy", "dagv2-personamem-v4",
    "dagv2-prefeval-v4-fix3", "dagv2-webwalker-v4",
})
DEFAULT_INDEX = "archives/dagv2-full-20261117/restore-index.json"
RAW_BASE = "https://raw.githubusercontent.com/DonJonMao/bridge-tree"
BLOCK = 1 << 20
MAX_CHUNK = 128 << 20
MAX_METADATA = 128 << 20
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ArchiveError(ValueError):
    pass


def _darwin_xattr(operation, target, name=None, value=None, *, follow_symlinks=True):
    """Apple's bundled Python can omit os.*xattr; use the system calls directly."""
    if sys.platform != "darwin":
        raise ArchiveError("extended attributes are unsupported by this Python platform")
    libc = ctypes.CDLL(None, use_errno=True)
    is_fd = isinstance(target, int)
    first = target if is_fd else os.fsencode(target)
    first_type = ctypes.c_int if is_fd else ctypes.c_char_p
    options = 0 if is_fd or follow_symlinks else 1  # XATTR_NOFOLLOW
    function = getattr(libc, ("f" if is_fd else "") + operation + "xattr")
    if operation == "list":
        function.argtypes = [first_type, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        function.restype = ctypes.c_ssize_t
        args = [first, None, 0, options]
    else:
        function.argtypes = [first_type, ctypes.c_char_p, ctypes.c_void_p,
                             ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
        function.restype = ctypes.c_int if operation == "set" else ctypes.c_ssize_t
        args = [first, os.fsencode(name), None, 0, 0, options]
    if operation == "set":
        buffer = ctypes.create_string_buffer(value, len(value) + 1)
        args[2:4] = [ctypes.cast(buffer, ctypes.c_void_p), len(value)]
        count = function(*args)
        if count < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        return None
    count = function(*args)
    if count < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    if not count:
        return [] if operation == "list" else b""
    buffer = ctypes.create_string_buffer(count)
    if operation == "list":
        args[1:3] = [ctypes.cast(buffer, ctypes.c_void_p), count]
    else:
        args[2:4] = [ctypes.cast(buffer, ctypes.c_void_p), count]
    count = function(*args)
    if count < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    data = buffer.raw[:count]
    return [os.fsdecode(v) for v in data.split(b"\0") if v] if operation == "list" else data


def get_xattr(target, name, *, follow_symlinks=True):
    if hasattr(os, "getxattr"):
        if isinstance(target, int):
            return os.getxattr(target, name)
        return os.getxattr(target, name, follow_symlinks=follow_symlinks)
    return _darwin_xattr("get", target, name, follow_symlinks=follow_symlinks)


def set_xattr(target, name, value, *, follow_symlinks=True):
    if hasattr(os, "setxattr"):
        if isinstance(target, int):
            return os.setxattr(target, name, value)
        return os.setxattr(target, name, value, follow_symlinks=follow_symlinks)
    return _darwin_xattr("set", target, name, value, follow_symlinks=follow_symlinks)


def list_xattrs(target, *, follow_symlinks=True):
    if hasattr(os, "listxattr"):
        if isinstance(target, int):
            return os.listxattr(target)
        return os.listxattr(target, follow_symlinks=follow_symlinks)
    return _darwin_xattr("list", target, follow_symlinks=follow_symlinks)


@contextmanager
def symlink_xattr_target(parent_fd, name):
    if sys.platform == "darwin":
        # O_SYMLINK opens the link inode itself. Darwin rejects combining this
        # flag with O_NOFOLLOW; fstat below still ensures we never get its target.
        fd = os.open(name, getattr(os, "O_SYMLINK", 0x00200000), dir_fd=parent_fd)
        try:
            if not stat.S_ISLNK(os.fstat(fd).st_mode):
                raise ArchiveError("symlink changed while opening its attributes")
            yield fd
        finally:
            os.close(fd)
    else:
        # Linux exposes stable directory descriptors through procfs.
        if not Path("/proc/self/fd").exists():
            raise ArchiveError("safe symlink xattr access is unsupported on this platform")
        yield f"/proc/self/fd/{parent_fd}/{name}"


def validate_relative(value: Any) -> str:
    if (not isinstance(value, str) or not value or "\0" in value
            or "\\" in value or value.startswith("/")
            or posixpath.normpath(value) != value
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ArchiveError("unsafe relative archive path")
    return value


def validate_source_path(value: Any, roots=ROOT_NAMES) -> str:
    value = validate_relative(value)
    if value.split("/")[0] not in roots:
        raise ArchiveError("source path is outside the declared roots")
    return value


def validate_repo_path(value: Any) -> str:
    value = validate_relative(value)
    if any(p.rstrip(" .").casefold() == ".git" or p.casefold().startswith(".git:")
           for p in value.split("/")):
        raise ArchiveError("repository reads may not access Git administration paths")
    return value


def decode64(value: Any, label: str) -> bytes:
    try:
        if not isinstance(value, str):
            raise ValueError()
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ArchiveError("invalid base64 " + label) from exc


class SafeTree:
    """Directory-fd traversal: no child or ancestor symlink is followed."""

    def __init__(self, path: str | Path):
        self.path = Path(path).absolute()
        self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.fd)

    @contextmanager
    def parent(self, path: str, *, create: bool = False):
        parts = validate_relative(path).split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    @contextmanager
    def open(self, path: str):
        with self.parent(path) as (parent_fd, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ArchiveError("expected a regular file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                yield stream
        finally:
            os.close(fd)

    def lstat(self, path: str):
        with self.parent(path) as (fd, name):
            return os.stat(name, dir_fd=fd, follow_symlinks=False)

    def readlink(self, path: str) -> str:
        with self.parent(path) as (fd, name):
            return os.readlink(name, dir_fd=fd)

    def mkdir(self, path: str):
        with self.parent(path, create=True) as (parent_fd, name):
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=parent_fd)
            try:
                # Restoring children must remain possible until directory metadata
                # is applied bottom-up, even if the original mode is read-only.
                os.fchmod(fd, stat.S_IMODE(os.fstat(fd).st_mode) | 0o700)
            finally:
                os.close(fd)

    def atomic_file(self, path: str, blocks: Iterator[bytes], expected: dict):
        with self.parent(path, create=True) as (parent_fd, name):
            temporary = ".dagv2-restore-" + uuid.uuid4().hex
            fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent_fd)
            try:
                digest = hashlib.sha256()
                total = 0
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    for block in blocks:
                        digest.update(block)
                        total += len(block)
                        if total > expected["size"]:
                            raise ArchiveError("reconstructed file is larger than its manifest")
                        # Preserve logical zero runs as holes instead of allocating
                        # the full size of sparse vector files.
                        if block and not any(block):
                            stream.seek(len(block), io.SEEK_CUR)
                        else:
                            stream.write(block)
                    stream.truncate(total)
                    stream.flush()
                    os.fsync(fd)
                if total != expected["size"] or digest.hexdigest() != expected["sha256"]:
                    raise ArchiveError("reconstructed file checksum or size differs")
                os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                os.close(fd)
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass

    def symlink(self, path: str, target: str):
        with self.parent(path, create=True) as (parent_fd, name):
            temporary = ".dagv2-symlink-" + uuid.uuid4().hex
            try:
                os.symlink(target, temporary, dir_fd=parent_fd)
                os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass

    def hardlink(self, source: str, target: str):
        with self.parent(source) as (src_fd, src_name), self.parent(target) as (dst_fd, dst_name):
            observed = os.stat(src_name, dir_fd=src_fd, follow_symlinks=False)
            if not stat.S_ISREG(observed.st_mode):
                raise ArchiveError("hardlink source is not a regular file")
            temporary = ".dagv2-hardlink-" + uuid.uuid4().hex
            try:
                os.link(src_name, temporary, src_dir_fd=src_fd, dst_dir_fd=dst_fd,
                        follow_symlinks=False)
                os.replace(temporary, dst_name, src_dir_fd=dst_fd, dst_dir_fd=dst_fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=dst_fd)
                except FileNotFoundError:
                    pass

    def apply_metadata(self, entry: dict, attributes: dict[str, str], *, ignore_owner=False):
        path = entry["path"]
        with self.parent(path) as (parent_fd, name):
            observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            symlink = entry["type"] == "symlink"
            if symlink:
                if not stat.S_ISLNK(observed.st_mode):
                    raise ArchiveError("metadata target type changed")
                if not ignore_owner and (observed.st_uid, observed.st_gid) != (entry["uid"], entry["gid"]):
                    os.chown(name, entry["uid"], entry["gid"], dir_fd=parent_fd,
                             follow_symlinks=False)
                if stat.S_IMODE(observed.st_mode) != entry["mode"]:
                    os.chmod(name, entry["mode"], dir_fd=parent_fd, follow_symlinks=False)
                if attributes:
                    with symlink_xattr_target(parent_fd, name) as leaf:
                        for attr, encoded in attributes.items():
                            set_xattr(leaf, attr, decode64(encoded, "xattr"), follow_symlinks=False)
                os.utime(name, ns=(observed.st_atime_ns, entry["mtime_ns"]),
                         dir_fd=parent_fd, follow_symlinks=False)
            else:
                flags = os.O_RDONLY | os.O_NOFOLLOW
                if entry["type"] == "directory":
                    flags |= os.O_DIRECTORY
                fd = os.open(name, flags, dir_fd=parent_fd)
                try:
                    observed = os.fstat(fd)
                    if not ignore_owner and (observed.st_uid, observed.st_gid) != (entry["uid"], entry["gid"]):
                        os.fchown(fd, entry["uid"], entry["gid"])
                    for attr, encoded in attributes.items():
                        set_xattr(fd, attr, decode64(encoded, "xattr"))
                    os.fchmod(fd, entry["mode"])
                    os.utime(fd, ns=(observed.st_atime_ns, entry["mtime_ns"]))
                finally:
                    os.close(fd)


class ArchiveReader:
    """Chunk/native-file reader usable by a separate remote tree verifier."""

    def __init__(self, repo_root: str | Path, *, commit: str | None = None,
                 remote: bool = False, raw_base: str = RAW_BASE, timeout=120):
        self.remote = remote
        self.commit = commit
        self.raw_base = raw_base.rstrip("/")
        self.timeout = timeout
        self.local = None if remote else SafeTree(repo_root)
        if remote and (not isinstance(commit, str) or not HEX40.fullmatch(commit)):
            raise ArchiveError("remote reads require a pinned 40-character --commit")

    def close(self):
        if self.local is not None:
            self.local.close()

    @contextmanager
    def open(self, path: str):
        path = validate_repo_path(path)
        if not self.remote:
            with self.local.open(path) as stream:
                yield stream
            return
        url = self.raw_base + "/" + self.commit + "/" + urllib.parse.quote(path, safe="/")
        request = urllib.request.Request(url, headers={"Accept-Encoding": "identity",
                                                       "User-Agent": "dagv2-archive-restore/1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ArchiveError("remote object returned an unexpected status")
                yield response
        except urllib.error.URLError as exc:
            # Do not expose upstream URLs, credentials or response bodies.
            raise ArchiveError("remote object request failed") from exc

    def iter_bytes(self, path: str, *, size: int | None = None,
                   sha256: str | None = None) -> Iterator[bytes]:
        total = 0
        digest = hashlib.sha256()
        with self.open(path) as stream:
            while True:
                block = stream.read(BLOCK)
                if not block:
                    break
                total += len(block)
                if size is not None and total > size:
                    raise ArchiveError("stored object exceeds its declared size")
                digest.update(block)
                yield block
        if size is not None and total != size:
            raise ArchiveError("stored object size differs")
        if sha256 is not None and digest.hexdigest() != sha256:
            raise ArchiveError("stored object SHA-256 differs")

    def read_bytes(self, path: str, *, size: int | None = None,
                   sha256: str | None = None, limit=MAX_CHUNK) -> bytes:
        if size is not None and size > limit:
            raise ArchiveError("stored object exceeds the configured memory limit")
        blocks = []
        total = 0
        for block in self.iter_bytes(path, size=size, sha256=sha256):
            total += len(block)
            if total > limit:
                raise ArchiveError("stored object exceeds the configured memory limit")
            blocks.append(block)
        return b"".join(blocks)


def load_index(reader: ArchiveReader, path: str) -> dict:
    index = json.loads(reader.read_bytes(path, limit=64 << 20))
    if not isinstance(index, dict) or index.get("version") != 1:
        raise ArchiveError("unsupported archive index version")
    roots = index.get("roots")
    if (not isinstance(roots, list) or not roots or len(set(roots)) != len(roots)
            or not set(roots).issubset(ROOT_NAMES)):
        raise ArchiveError("invalid archive source roots")
    entries = index.get("entries")
    if not isinstance(entries, list):
        raise ArchiveError("archive entries must be a list")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ArchiveError("invalid archive entry")
        path = entry.get("path")
        kind = entry.get("kind", "file")
        if kind == "metadata":
            if path not in {"source-manifest.jsonl", "source-xattrs.jsonl"}:
                raise ArchiveError("unsupported archive metadata path")
            if entry.get("storage") != "aes256gcm":
                raise ArchiveError("source metadata must be authenticated and encrypted")
        elif kind == "file":
            validate_source_path(path, set(roots))
        else:
            raise ArchiveError("unsupported archive entry kind")
        if path in seen:
            raise ArchiveError("duplicate archive entry path")
        seen.add(path)
        if entry.get("storage") not in {"parts", "aes256gcm"}:
            raise ArchiveError("unsupported archive entry storage")
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise ArchiveError("invalid archive original size")
        chunks = entry.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ArchiveError("archive entry has no chunks")
        for chunk in chunks:
            validate_repo_path(chunk.get("path"))
            if (not isinstance(chunk.get("size"), int) or chunk["size"] < 0
                    or not isinstance(chunk.get("sha256"), str)
                    or not HEX64.fullmatch(chunk["sha256"])):
                raise ArchiveError("invalid chunk size or checksum")
            if entry["storage"] == "aes256gcm":
                if len(decode64(chunk.get("nonce_b64"), "nonce")) != 12:
                    raise ArchiveError("AES-GCM nonce must be 12 bytes")
                decode64(chunk.get("aad_b64", ""), "AAD")
    if "source-manifest.jsonl" not in seen:
        raise ArchiveError("authenticated source manifest is missing")
    sidecars = index.get("public_sidecars", [])
    if not isinstance(sidecars, list) or len(set(sidecars)) != len(sidecars):
        raise ArchiveError("invalid public sidecar list")
    for sidecar in sidecars:
        validate_source_path(sidecar, set(roots))
    return index


def derive_key(index: dict, password_file: str | Path) -> bytes:
    kdf = index.get("kdf", {})
    if kdf != {"name": "scrypt", "n": 32768, "r": 8, "p": 1}:
        raise ArchiveError("unsupported or unsafe password KDF parameters")
    salt = decode64(index.get("salt_b64"), "salt")
    if len(salt) < 16 or len(salt) > 64:
        raise ArchiveError("archive salt must contain 16 to 64 bytes")
    password = Path(password_file).read_bytes().rstrip(b"\r\n")
    if not password:
        raise ArchiveError("empty archive password")
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password)


def iter_entry(reader: ArchiveReader, entry: dict, key: bytes) -> Iterator[bytes]:
    """Yield one original in bounded blocks; verify each stored chunk hash."""
    total = 0
    digest = hashlib.sha256()
    for chunk in entry["chunks"]:
        if entry["storage"] == "aes256gcm":
            encrypted = reader.read_bytes(chunk["path"], size=chunk["size"],
                                          sha256=chunk["sha256"])
            try:
                plaintext = AESGCM(key).decrypt(decode64(chunk["nonce_b64"], "nonce"),
                                               encrypted, decode64(chunk.get("aad_b64", ""), "AAD"))
            except Exception as exc:
                raise ArchiveError("encrypted chunk authentication failed") from exc
            blocks = (plaintext[offset:offset + BLOCK] for offset in range(0, len(plaintext), BLOCK))
        else:
            blocks = reader.iter_bytes(chunk["path"], size=chunk["size"], sha256=chunk["sha256"])
        for block in blocks:
            total += len(block)
            digest.update(block)
            if total > entry["size"]:
                raise ArchiveError("archive entry exceeds its original size")
            yield block
    if total != entry["size"]:
        raise ArchiveError("archive entry original size differs")
    if "sha256" in entry and digest.hexdigest() != entry["sha256"]:
        raise ArchiveError("archive entry original SHA-256 differs")


def metadata_bytes(reader: ArchiveReader, entry: dict, key: bytes) -> bytes:
    if entry["size"] > MAX_METADATA:
        raise ArchiveError("metadata exceeds the configured memory limit")
    return b"".join(iter_entry(reader, entry, key))


def load_metadata(reader: ArchiveReader, index: dict, key: bytes):
    special = {e["path"]: e for e in index["entries"] if e.get("kind", "file") == "metadata"}
    manifest_raw = metadata_bytes(reader, special["source-manifest.jsonl"], key)
    if ("source_manifest_sha256" in index
            and hashlib.sha256(manifest_raw).hexdigest() != index["source_manifest_sha256"]):
        raise ArchiveError("authenticated manifest checksum differs from the public index")
    manifest: dict[str, dict] = {}
    roots = set(index["roots"])
    for line in manifest_raw.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        path = validate_source_path(entry.get("path"), roots)
        if path in manifest:
            raise ArchiveError("duplicate source manifest path")
        if entry.get("type") not in {"file", "directory", "symlink"}:
            raise ArchiveError("unsupported source manifest object type")
        for field in ("mode", "mtime_ns", "uid", "gid"):
            if not isinstance(entry.get(field), int) or entry[field] < 0:
                raise ArchiveError("invalid source metadata field")
        if not 0 <= entry["mode"] <= 0o7777:
            raise ArchiveError("invalid source permission bits")
        if entry["type"] == "file":
            if (not isinstance(entry.get("size"), int) or entry["size"] < 0
                    or not isinstance(entry.get("sha256"), str)
                    or not HEX64.fullmatch(entry["sha256"])):
                raise ArchiveError("invalid source file checksum or size")
        elif entry["type"] == "symlink":
            if not isinstance(entry.get("target"), str) or "\0" in entry["target"]:
                raise ArchiveError("invalid source symlink target")
        manifest[path] = entry
    for root in roots:
        if root not in manifest or manifest[root]["type"] != "directory":
            raise ArchiveError("source root directory missing from manifest")
    for path in manifest:
        parts = path.split("/")
        for length in range(1, len(parts)):
            ancestor = "/".join(parts[:length])
            if ancestor not in manifest or manifest[ancestor]["type"] != "directory":
                raise ArchiveError("manifest ancestor is missing or not a directory")
    file_entries = {}
    for entry in index["entries"]:
        if entry.get("kind", "file") == "metadata":
            continue
        path = entry["path"]
        if path not in manifest or manifest[path]["type"] != "file":
            raise ArchiveError("archive file entry has no manifest file")
        if entry["size"] != manifest[path]["size"]:
            raise ArchiveError("archive entry and manifest size differ")
        if "sha256" in entry and entry["sha256"] != manifest[path]["sha256"]:
            raise ArchiveError("archive entry and manifest checksum differ")
        file_entries[path] = entry
    attributes: dict[str, dict[str, str]] = {}
    if "source-xattrs.jsonl" in special:
        for line in metadata_bytes(reader, special["source-xattrs.jsonl"], key).splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            path = validate_source_path(entry.get("path"), roots)
            attrs = entry.get("attributes")
            if path not in manifest or path in attributes or not isinstance(attrs, dict):
                raise ArchiveError("invalid source xattr entry")
            for name, value in attrs.items():
                if not isinstance(name, str) or not name or "\0" in name:
                    raise ArchiveError("invalid xattr name")
                decode64(value, "xattr")
            attributes[path] = attrs
    return manifest, attributes, file_entries


def clean_public_sidecars(target, sidecars, archive_index, manifest, file_entries):
    """Remove only unchanged producer-generated sidecars, after restoring content."""
    pending = []
    for path in sidecars:
        validate_source_path(path)
        if path in manifest:
            raise ArchiveError("public sidecar collides with an original source path")
        suffix = ".parts.json" if path.endswith(".parts.json") else ".encrypted.json"
        if not path.endswith(suffix):
            raise ArchiveError("unsupported public sidecar suffix")
        original = path[:-len(suffix)]
        entry = file_entries.get(original)
        expected_storage = "parts" if suffix == ".parts.json" else "aes256gcm"
        if entry is None or entry["storage"] != expected_storage or original not in manifest:
            raise ArchiveError("public sidecar has no matching restored original")
        expected = json.dumps({"archive_index": archive_index, "original_path": original,
                               "storage": entry["storage"], "original_bytes": entry["size"]},
                              ensure_ascii=False, indent=2).encode() + b"\n"
        try:
            observed = target.lstat(path)
        except FileNotFoundError:
            continue  # A successful earlier restore already cleaned this sidecar.
        if not stat.S_ISREG(observed.st_mode):
            raise ArchiveError("public sidecar was replaced with a non-file: " + path)
        with target.open(path) as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(len(expected) + 1)
            after = os.fstat(stream.fileno())
        identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if identity(observed) != identity(opened) or identity(opened) != identity(after) or data != expected:
            raise ArchiveError("public sidecar was edited; refusing to remove it: " + path)
        pending.append((path, identity(observed)))
    # Preflight every sidecar before deleting any, so one edited file leaves all
    # generated sidecars intact for the user to inspect.
    for path, identity in pending:
        with target.parent(path) as (parent_fd, name):
            observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            current = (observed.st_dev, observed.st_ino, observed.st_size,
                       observed.st_mtime_ns, observed.st_ctime_ns)
            if current != identity:
                raise ArchiveError("public sidecar changed before cleanup: " + path)
            os.unlink(name, dir_fd=parent_fd)
    return len(pending)


def hardlink_groups(manifest: dict):
    groups = defaultdict(list)
    for path, entry in manifest.items():
        if entry["type"] == "file" and entry.get("nlink", 1) > 1:
            device, inode = entry.get("device", entry.get("dev")), entry.get("inode")
            if not isinstance(device, int) or not isinstance(inode, int):
                raise ArchiveError("hardlink identity is missing from the source manifest")
            groups[(device, inode)].append(path)
    result = []
    for paths in groups.values():
        if len(paths) < 2:
            continue
        identities = {(manifest[p]["size"], manifest[p]["sha256"], manifest[p]["mode"],
                       manifest[p]["mtime_ns"], manifest[p]["uid"], manifest[p]["gid"]) for p in paths}
        if len(identities) != 1:
            raise ArchiveError("inconsistent hardlink group in source manifest")
        result.append(sorted(paths))
    return result


def file_blocks(reader: ArchiveReader, path: str, manifest: dict,
                file_entries: dict, key: bytes):
    if path in file_entries:
        return iter_entry(reader, file_entries[path], key)
    return reader.iter_bytes(path, size=manifest[path]["size"], sha256=manifest[path]["sha256"])


def digest_blocks(blocks):
    digest = hashlib.sha256()
    size = 0
    for block in blocks:
        digest.update(block)
        size += len(block)
    return size, digest.hexdigest()


def verify_remote(reader, manifest, file_entries, key, *, progress=True):
    files = total = 0
    for path, entry in manifest.items():
        if entry["type"] != "file":
            continue
        size, checksum = digest_blocks(file_blocks(reader, path, manifest, file_entries, key))
        if (size, checksum) != (entry["size"], entry["sha256"]):
            raise ArchiveError("remote original content differs from authenticated manifest: " + path)
        files += 1
        total += size
        if progress and files % 1000 == 0:
            print(json.dumps({"phase": "verify-remote", "files": files, "bytes": total}), flush=True)
    return {"verified_files": files, "verified_bytes": total}


def restore(reader, target, manifest, attributes, file_entries, key, *,
            ignore_owner=False, progress=True, public_sidecars=None,
            archive_index=DEFAULT_INDEX):
    directories = sorted((p for p, e in manifest.items() if e["type"] == "directory"),
                         key=lambda p: (p.count("/"), p))
    groups = hardlink_groups(manifest)
    aliases = {p: group[0] for group in groups for p in group[1:]}
    files = total = links = 0
    for path in directories:
        target.mkdir(path)
    for path, entry in manifest.items():
        if entry["type"] != "file" or path in aliases:
            continue
        if not reader.remote and reader.local.path == target.path and path not in file_entries:
            # Native files in an existing clone need only validation and metadata.
            size, checksum = digest_blocks(reader.iter_bytes(path, size=entry["size"], sha256=entry["sha256"]))
            if (size, checksum) != (entry["size"], entry["sha256"]):
                raise ArchiveError("existing native file differs from manifest")
        else:
            target.atomic_file(path, file_blocks(reader, path, manifest, file_entries, key), entry)
        files += 1
        total += entry["size"]
        if progress and files % 1000 == 0:
            print(json.dumps({"phase": "restore", "files": files, "bytes": total}), flush=True)
    for group in groups:
        for path in group[1:]:
            target.hardlink(group[0], path)
            links += 1
    for path, entry in manifest.items():
        if entry["type"] == "symlink":
            target.symlink(path, entry["target"])
    cleaned = 0
    if (not reader.remote and reader.local.path == target.path
            and public_sidecars):
        cleaned = clean_public_sidecars(target, public_sidecars, archive_index,
                                       manifest, file_entries)
    for path, entry in manifest.items():
        if entry["type"] != "directory":
            target.apply_metadata(entry, attributes.get(path, {}), ignore_owner=ignore_owner)
    for path in reversed(directories):
        target.apply_metadata(manifest[path], attributes.get(path, {}), ignore_owner=ignore_owner)
    return {"restored_files": files, "restored_bytes": total,
            "hardlinks_recreated": links, "public_sidecars_removed": cleaned}


def verify_tree(target, manifest, attributes, *, ignore_owner=False, progress=True):
    files = total = 0
    for path, entry in manifest.items():
        observed = target.lstat(path)
        kind = ("symlink" if stat.S_ISLNK(observed.st_mode) else "directory"
                if stat.S_ISDIR(observed.st_mode) else "file" if stat.S_ISREG(observed.st_mode) else "other")
        if kind != entry["type"]:
            raise ArchiveError("restored object type differs: " + path)
        if stat.S_IMODE(observed.st_mode) != entry["mode"]:
            raise ArchiveError("restored permission bits differ: " + path)
        if observed.st_mtime_ns != entry["mtime_ns"]:
            raise ArchiveError("restored nanosecond mtime differs: " + path)
        if not ignore_owner and (observed.st_uid, observed.st_gid) != (entry["uid"], entry["gid"]):
            raise ArchiveError("restored ownership differs: " + path)
        if kind == "file":
            with target.open(path) as stream:
                size, checksum = digest_blocks(iter(lambda: stream.read(BLOCK), b""))
            if (size, checksum) != (entry["size"], entry["sha256"]):
                raise ArchiveError("restored file content differs: " + path)
            files += 1
            total += size
            if progress and files % 1000 == 0:
                print(json.dumps({"phase": "verify-only", "files": files, "bytes": total}), flush=True)
        elif kind == "symlink" and target.readlink(path) != entry["target"]:
            raise ArchiveError("restored symlink target differs: " + path)
        if attributes.get(path):
            with target.parent(path) as (parent_fd, name):
                if kind == "symlink":
                    with symlink_xattr_target(parent_fd, name) as leaf:
                        for attr, encoded in attributes[path].items():
                            if get_xattr(leaf, attr, follow_symlinks=False) != decode64(encoded, "xattr"):
                                raise ArchiveError("restored xattr differs: " + path)
                else:
                    flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if kind == "directory" else 0)
                    fd = os.open(name, flags, dir_fd=parent_fd)
                    try:
                        for attr, encoded in attributes[path].items():
                            if get_xattr(fd, attr) != decode64(encoded, "xattr"):
                                raise ArchiveError("restored xattr differs: " + path)
                    finally:
                        os.close(fd)
    groups = hardlink_groups(manifest)
    for group in groups:
        if len({(target.lstat(p).st_dev, target.lstat(p).st_ino) for p in group}) != 1:
            raise ArchiveError("restored hardlink topology differs: " + group[0])
    return {"verified_files": files, "verified_bytes": total, "hardlink_groups": len(groups)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--index", default=DEFAULT_INDEX, help="repository-relative restore index")
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--target", type=Path, help="parent of the five restored source directories")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--restore", action="store_true", help="explicitly write restored originals")
    mode.add_argument("--verify-only", action="store_true", help="verify a restored tree (default)")
    mode.add_argument("--verify-remote", action="store_true", help="verify remote originals without writing")
    parser.add_argument("--from-remote", action="store_true",
                        help="read index/chunks/native files remotely; combine with --restore to avoid cloning")
    parser.add_argument("--commit", help="immutable 40-character Git commit for remote verification")
    parser.add_argument("--raw-base", default=RAW_BASE)
    parser.add_argument("--ignore-owner", action="store_true", help="skip owner/group restoration and checks")
    parser.add_argument("--report", type=Path, help="optional aggregate JSON report outside source roots")
    args = parser.parse_args()
    started = time.time()
    reader = target = None
    try:
        reader = ArchiveReader(args.repo_root, remote=args.verify_remote or args.from_remote, commit=args.commit,
                               raw_base=args.raw_base)
        index = load_index(reader, args.index)
        key = derive_key(index, args.password_file)
        manifest, attributes, file_entries = load_metadata(reader, index, key)
        actions = {}
        if args.verify_remote:
            result = verify_remote(reader, manifest, file_entries, key)
        else:
            target_path = (args.target or args.repo_root).absolute()
            if args.restore:
                # Only the explicitly named parent may be created at this stage.
                target_path.mkdir(parents=True, exist_ok=True)
            target = SafeTree(target_path)
            if args.restore:
                actions = restore(reader, target, manifest, attributes, file_entries, key,
                                  ignore_owner=args.ignore_owner,
                                  public_sidecars=index.get("public_sidecars", []),
                                  archive_index=args.index)
            result = verify_tree(target, manifest, attributes, ignore_owner=args.ignore_owner)
        report = {"success": True, "mode": "verify-remote" if args.verify_remote else
                  "restore" if args.restore else "verify-only", "entries": len(manifest),
                  "from_remote": bool(args.from_remote or args.verify_remote),
                  **actions, **result, "seconds": round(time.time() - started, 3)}
    except Exception as exc:
        # Error messages are intentionally limited to type and our own safe messages.
        message = str(exc) if isinstance(exc, ArchiveError) else type(exc).__name__
        report = {"success": False, "error": message, "seconds": round(time.time() - started, 3)}
    finally:
        if target is not None:
            target.close()
        if reader is not None:
            reader.close()
    if args.report:
        report_path = args.report.resolve(strict=False)
        for parent in {args.repo_root.resolve(), (args.target or args.repo_root).resolve()}:
            for root in ROOT_NAMES:
                base = parent / root
                if report_path == base or base in report_path.parents:
                    print(json.dumps({"success": False, "error": "report path is inside source roots"}))
                    return 1
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
