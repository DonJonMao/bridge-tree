#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:-$repo_dir/dist/chain-server}"
mkdir -p "$out"
out="$(cd "$out" && pwd)"
archive="$out/bridge-tree-chain.tar.gz"
(
  cd "$repo_dir"
  COPYFILE_DISABLE=1 tar -czf "$archive" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='.mypy_cache' \
    --exclude='.cache' \
    --exclude='cache' \
    --exclude='caches' \
    --exclude='*.egg-info' \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='outputs' \
    --exclude='configs/credentials.local.yaml' \
    --exclude='*credential*.yaml' \
    --exclude='*credential*.yml' \
    --exclude='*credential*.json' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='*.pem' \
    --exclude='*.key' \
    --exclude='*.p12' \
    --exclude='*.pfx' \
    --exclude='*.tmp' \
    src reference configs scripts tests docs data/raw data/processed data/README.md \
    pyproject.toml requirements.txt requirements-ascend910b.txt README.md
)
if command -v sha256sum >/dev/null 2>&1; then
  archive_sha256="$(sha256sum "$archive" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  archive_sha256="$(shasum -a 256 "$archive" | awk '{print $1}')"
else
  echo "sha256sum or shasum is required to checksum the server archive" >&2
  exit 1
fi
printf '%s  %s\n' "$archive_sha256" "$(basename "$archive")" > "$archive.sha256"
printf '%s\n%s\n' "$archive" "$archive.sha256"
