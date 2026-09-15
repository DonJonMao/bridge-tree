#!/usr/bin/env bash
set -euo pipefail
umask 077
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_dir"
if [[ -n "${BRIDGETREE_BASE_PYTHON:-}" ]]; then
  python_bin="$BRIDGETREE_BASE_PYTHON"
elif [[ -x "$repo_dir/.venv-diagnostics/bin/python" ]]; then
  python_bin="$repo_dir/.venv-diagnostics/bin/python"
elif [[ -x "$repo_dir/.venv/bin/python" ]]; then
  python_bin="$repo_dir/.venv/bin/python"
else
  python_bin="python3"
fi
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
if [[ $# -eq 0 ]]; then
  set -- start
fi
exec "$python_bin" -u -m bridgetree.diagnostic_background "$@"
