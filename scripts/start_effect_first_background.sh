#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

action="${1:-start}"
if (( $# > 0 )); then
  shift
fi
state_dir="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background}"
manager_python="${BACKGROUND_PYTHON:-${BRIDGETREE_BASE_PYTHON:-python3}}"
manager_script="$repo_dir/scripts/background_entrypoint.py"

case "$action" in
  start)
    run_root="${OUTPUT_DIR:-$repo_dir/outputs/effect-first-validation}"
    exec "$manager_python" "$manager_script" start \
      --job effect_first \
      --state-dir "$state_dir" \
      --cwd "$repo_dir" \
      --run-root "$run_root" \
      --run-prefix effect_validation_ \
      --artifact effect_summary.json=effect_first.summary.json \
      --artifact effect_results.csv=effect_first.results.csv \
      --artifact paired_results.json=effect_first.paired_results.json \
      -- bash "$repo_dir/scripts/run_effect_first_validation.sh" "$@"
    ;;
  status)
    exec "$manager_python" "$manager_script" status --job effect_first --state-dir "$state_dir"
    ;;
  log)
    lines="${LINES:-100}"
    log_file="$state_dir/effect_first.log"
    if [[ ! -f "$log_file" ]]; then
      echo "effect-first background log does not exist yet: $log_file" >&2
      exit 1
    fi
    exec tail -n "$lines" "$log_file"
    ;;
  *)
    echo "usage: $0 [start|status|log] [effect-first CLI overrides]" >&2
    exit 2
    ;;
esac
