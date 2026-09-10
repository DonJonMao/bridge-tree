#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
action="${1:-start}"
if [[ $# -gt 0 ]]; then
  shift
fi
config_was_supplied=false
if [[ $# -gt 0 ]]; then
  config="$1"
  config_was_supplied=true
else
  config="configs/chain_full.yaml"
fi
state_dir="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background}"
run_root="${OUTPUT_DIR:-$repo_dir/outputs/chain}"
if [[ -n "${BRIDGETREE_BASE_PYTHON:-}" ]]; then
  python_bin="$BRIDGETREE_BASE_PYTHON"
elif [[ -x "$repo_dir/.venv/bin/python" ]]; then
  python_bin="$repo_dir/.venv/bin/python"
else
  python_bin="python3"
fi
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
manager="$repo_dir/scripts/background_entrypoint.py"
job="chain_full"

launch_worker() {
  local run_dir="$1"
  local mode="$2"
  local run_prefix
  local worker_args
  run_prefix="$(basename "$run_dir")"
  worker_args=(
    "$python_bin" "$repo_dir/scripts/chain_worker.py"
    --config "$config"
    --output-dir "$run_dir"
  )
  if [[ "$mode" == "resume" ]]; then
    worker_args+=(--resume)
  fi
  exec "$python_bin" "$manager" start \
    --job "$job" \
    --state-dir "$state_dir" \
    --cwd "$repo_dir" \
    --run-root "$(dirname "$run_dir")" \
    --run-prefix "$run_prefix" \
    --exact-run-dir "$run_dir" \
    --artifact summary.json=chain_full.summary.json \
    --artifact progress.json=chain_full.progress.json \
    --artifact completion.json=chain_full.completion.json \
    -- "${worker_args[@]}"
}

case "$action" in
  preflight)
    run_id="preflight_$(date +%Y%m%d_%H%M%S)_$$"
    exec "$python_bin" "$repo_dir/scripts/chain_worker.py" \
      --config "$config" \
      --output-dir "$run_root/$run_id" \
      --preflight-only
    ;;
  start)
    run_id="dependency_$(date +%Y%m%d_%H%M%S)_$$"
    run_dir="$run_root/$run_id"
    mkdir -p "$run_root"
    launch_worker "$run_dir" start
    ;;
  status)
    exec "$python_bin" "$manager" status --job "$job" --state-dir "$state_dir"
    ;;
  log)
    log_file="$state_dir/$job.log"
    if [[ ! -f "$log_file" ]]; then
      echo "no Chain log exists yet: $log_file" >&2
      exit 1
    fi
    exec tail -n 100 -F "$log_file"
    ;;
  module-log)
    module_name="${1:-effectiveness}"
    case "$module_name" in
      effectiveness|effectiveness-current|scoring|activation|proposal|state|stop|selection|context|cost)
        ;;
      *)
        echo "unknown Chain module log: $module_name" >&2
        echo "allowed: effectiveness effectiveness-current scoring activation proposal state stop selection context cost" >&2
        exit 2
        ;;
    esac
    run_dir_file="$state_dir/$job.run_dir"
    if [[ ! -s "$run_dir_file" ]]; then
      echo "no recorded Chain run directory; start or resume a run first" >&2
      exit 1
    fi
    IFS= read -r run_dir < "$run_dir_file"
    if [[ "$module_name" == "effectiveness-current" ]]; then
      module_log="$run_dir/modules/effectiveness.current.jsonl"
    else
      module_log="$run_dir/modules/$module_name.jsonl"
    fi
    if [[ -z "$run_dir" || ! -f "$module_log" ]]; then
      echo "Chain module log is unavailable: $module_log" >&2
      exit 1
    fi
    exec tail -n 100 -F "$module_log"
    ;;
  resume)
    run_dir_file="$state_dir/$job.run_dir"
    if [[ ! -s "$run_dir_file" ]]; then
      echo "cannot resume: no recorded Chain run directory" >&2
      exit 1
    fi
    IFS= read -r run_dir < "$run_dir_file"
    if [[ -z "$run_dir" || ! -d "$run_dir" ]]; then
      echo "cannot resume: recorded run directory is unavailable: $run_dir" >&2
      exit 1
    fi
    if [[ "$config_was_supplied" == false ]]; then
      spec_file="$state_dir/$job.spec.json"
      original_config="$($python_bin - "$spec_file" <<'PY' 2>/dev/null || true
import json
import sys

try:
    command = json.load(open(sys.argv[1], encoding="utf-8")).get("command", [])
    position = command.index("--config")
    value = command[position + 1]
except (OSError, ValueError, IndexError, TypeError):
    value = ""
print(value)
PY
)"
      if [[ -n "$original_config" ]]; then
        config="$original_config"
      fi
    fi
    launch_worker "$run_dir" resume
    ;;
  stop)
    status_file="$state_dir/$job.status.json"
    pid="$($python_bin - "$status_file" <<'PY' 2>/dev/null || true
import json
import os
import sys
import time

deadline = time.monotonic() + 5.0
value = None
while True:
    try:
        status = json.load(open(sys.argv[1], encoding="utf-8"))
        candidate = status.get("pid")
        state = status.get("state")
    except (OSError, ValueError):
        break
    if not isinstance(candidate, int) or candidate <= 0:
        break
    try:
        os.kill(candidate, 0)
    except OSError:
        break
    if state == "running":
        value = candidate
        break
    if state != "starting" or time.monotonic() >= deadline:
        break
    time.sleep(0.05)
print(value if isinstance(value, int) and value > 0 else "")
PY
)"
    if [[ -z "$pid" ]]; then
      echo "no active Chain process found"
      exit 0
    fi
    kill -TERM "$pid" 2>/dev/null || true
    echo "graceful stop signal sent to Chain monitor $pid"
    ;;
  *)
    echo "usage: $0 {preflight|start|status|log|resume|stop} [config]" >&2
    echo "       $0 module-log [effectiveness|effectiveness-current|scoring|activation|proposal|state|stop|selection|context|cost]" >&2
    exit 2
    ;;
esac
