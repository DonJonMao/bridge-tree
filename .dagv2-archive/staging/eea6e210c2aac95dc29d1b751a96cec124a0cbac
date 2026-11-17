#!/usr/bin/env bash
set -euo pipefail
TASK_BUNDLE="$(cd "$(dirname "$0")" && pwd)"
TASK_TARGET="${1:-${DAGBT_TARGET:-$HOME/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2}}"
TASK_PYTHON="${DAGBT_PYTHON:-}"
if [[ -z "$TASK_PYTHON" ]]; then
  if [[ -x "$TASK_TARGET/.venv/bin/python" ]]; then
    TASK_PYTHON="$TASK_TARGET/.venv/bin/python"
  elif [[ -x "$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python" ]]; then
    TASK_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
  else
    TASK_PYTHON="python3"
  fi
fi
"$TASK_PYTHON" "$TASK_BUNDLE/install_webwalker.py" --target "$TASK_TARGET" --base "${DAGBT_PERSONAMEM_BASE:-$HOME/dagbt_runs/20261014_personamem_v4_experiment/dagv2}"
cd "$TASK_TARGET"
if [[ "${2:-with-browser}" != "--no-browser" ]]; then
  "$TASK_PYTHON" scripts/install_webwalker_browser.py --target "$TASK_TARGET"
fi
DAGBT_PYTHON="$TASK_PYTHON" bash scripts/run_webwalker.sh offline
DAGBT_PYTHON="$TASK_PYTHON" bash scripts/run_webwalker.sh full
