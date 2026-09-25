#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
if [[ -n "${BRIDGETREE_BASE_PYTHON:-}" ]]; then
  python_bin="$BRIDGETREE_BASE_PYTHON"
elif [[ -x "$repo_dir/.venv/bin/python" ]]; then
  python_bin="$repo_dir/.venv/bin/python"
else
  python_bin=python3
fi
exec "$python_bin" "$repo_dir/scripts/evidence_bridge_control.py" "$@"
