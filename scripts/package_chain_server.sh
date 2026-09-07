#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:-$repo_dir/dist/chain-server}"
mkdir -p "$out"
tar -czf "$out/bridge-tree-chain.tar.gz" --exclude='*.pyc' --exclude='.git' src configs scripts data/processed pyproject.toml requirements.txt README.md
echo "$out/bridge-tree-chain.tar.gz"
