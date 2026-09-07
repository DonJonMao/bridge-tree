#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$repo_dir"
action="${1:-start}"; shift || true
config="${1:-configs/chain_full.yaml}"
state_dir="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background}"
run_root="${OUTPUT_DIR:-$repo_dir/outputs/chain}"
python_bin="${BRIDGETREE_BASE_PYTHON:-python3}"
manager="$repo_dir/scripts/background_entrypoint.py"
case "$action" in
  start) run_id="chain_$(date +%Y%m%d_%H%M%S)"; exec "$python_bin" "$manager" start --job chain_full --state-dir "$state_dir" --cwd "$repo_dir" --run-root "$run_root" --run-prefix "$run_id" -- python3 "$repo_dir/scripts/chain_worker.py" --config "$config" --output-dir "$run_root/$run_id" ;;
  status) exec "$python_bin" "$manager" status --job chain_full --state-dir "$state_dir" ;;
  log) tail -f "$state_dir/chain_full.log" ;;
  resume) exec "$0" start "$config" ;;
  stop) status_file="$state_dir/chain_full.status.json"; pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pid", ""))' "$status_file" 2>/dev/null || true)"; [[ -z "$pid" ]] || kill "$pid" || true ;;
  *) echo "usage: $0 {start|status|log|resume|stop} [config]" >&2; exit 2 ;;
esac
