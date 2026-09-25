#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${BRIDGETREE_BASE_PYTHON:-python3}"
exec "$python_bin" "$repo_dir/scripts/package_evidence_bridge.py" "${1:-$repo_dir/dist/evidence-bridge-server}"
