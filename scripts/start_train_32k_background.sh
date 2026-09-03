#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

action="${1:-start}"
if (( $# > 0 )); then
  shift
fi
if (( $# > 0 )); then
  echo "the formal 32K launcher uses environment overrides and accepts no trailing arguments" >&2
  exit 2
fi
state_dir="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background}"
manager_python="${BACKGROUND_PYTHON:-${BRIDGETREE_BASE_PYTHON:-python3}}"
manager_script="$repo_dir/scripts/background_entrypoint.py"

case "$action" in
  start)
    run_root="${OUTPUT_DIR:-$repo_dir/outputs/tuning-32k}"
    exec "$manager_python" "$manager_script" start \
      --job train_32k \
      --state-dir "$state_dir" \
      --cwd "$repo_dir" \
      --run-root "$run_root" \
      --run-prefix tune_ \
      --artifact final_summary.json=train_32k.summary.json \
      --artifact completion_audit.json=train_32k.audit.json \
      --artifact best_config.json=train_32k.best_config.json \
      -- bash "$repo_dir/scripts/train_32k.sh"
    ;;
  status)
    exec "$manager_python" "$manager_script" status --job train_32k --state-dir "$state_dir"
    ;;
  log)
    lines="${LINES:-100}"
    log_file="$state_dir/train_32k.log"
    if [[ ! -f "$log_file" ]]; then
      echo "formal 32K background log does not exist yet: $log_file" >&2
      exit 1
    fi
    exec tail -n "$lines" "$log_file"
    ;;
  *)
    echo "usage: $0 [start|status|log]" >&2
    exit 2
    ;;
esac
