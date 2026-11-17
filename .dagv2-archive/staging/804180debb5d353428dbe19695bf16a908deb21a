#!/usr/bin/env bash
set -euo pipefail
PREFEVAL_RELEASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PREFEVAL_PYTHON="${DAGBT_PYTHON:-$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python}"
if [[ ! -x "$PREFEVAL_PYTHON" ]]; then
  printf '%s\n' '找不到 Python；请设置 DAGBT_PYTHON 为已有 dagbt 环境的 python 完整路径。' >&2
  exit 1
fi
cd "$PREFEVAL_RELEASE_ROOT"
export NO_PROXY='*' no_proxy='*'
if [[ "${1:-}" == install ]]; then
  shift
  exec "$PREFEVAL_PYTHON" scripts/install_prefeval_v4.py "$@"
fi
exec "$PREFEVAL_PYTHON" -u scripts/prefeval_v4.py "$@"
