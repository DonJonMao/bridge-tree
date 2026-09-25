#!/usr/bin/env bash
# One command: install remote-inference dependencies, verify data, detach run.
set -euo pipefail
umask 077
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
config="${1:-configs/evidence_bridge.yaml}"
setup_python="${BRIDGETREE_SETUP_PYTHON:-python3}"
venv_dir="${BRIDGETREE_VENV_DIR:-$repo_dir/.venv}"
skip_install="${BRIDGETREE_SKIP_INSTALL:-false}"
allow_non_linux="${BRIDGETREE_ALLOW_NON_LINUX:-false}"
case "$skip_install:$allow_non_linux" in
  true:true|true:false|false:true|false:false) ;;
  *) echo "BRIDGETREE_SKIP_INSTALL / BRIDGETREE_ALLOW_NON_LINUX must be true or false" >&2; exit 2 ;;
esac
if [[ "$(uname -s)" != Linux && "$allow_non_linux" != true ]]; then
  echo "This launcher targets Linux" >&2
  exit 1
fi
test -f "$config" || { echo "Missing config: $config" >&2; exit 1; }
"$setup_python" -c 'import sys; assert sys.version_info >= (3,9), "Python >=3.9 required"'
export BACKGROUND_STATE_DIR="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background-evidence-bridge}"
export OUTPUT_DIR="${OUTPUT_DIR:-$repo_dir/outputs/evidence-bridge}"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
status_json="$(BRIDGETREE_BASE_PYTHON="$setup_python" bash scripts/run_evidence_bridge.sh status)"
state="$("$setup_python" -c 'import json,sys; print(json.load(sys.stdin)["state"])' <<<"$status_json")"
case "$state" in
  starting|running) printf '%s\n' "$status_json"; exit 0 ;;
  interrupted|failed)
    echo "Previous run is resumable. Use: bash scripts/run_evidence_bridge.sh resume" >&2
    exit 1 ;;
esac
if [[ ! -e "$venv_dir" ]]; then
  "$setup_python" -m venv "$venv_dir"
fi
test -f "$venv_dir/pyvenv.cfg" && test -x "$venv_dir/bin/python" || {
  echo "Invalid virtual environment: $venv_dir" >&2; exit 1;
}
export BRIDGETREE_BASE_PYTHON="$(cd "$venv_dir" && pwd)/bin/python"
if [[ "$skip_install" == false ]]; then
  "$BRIDGETREE_BASE_PYTHON" -m pip install --disable-pip-version-check -e "$repo_dir"
fi
"$BRIDGETREE_BASE_PYTHON" -c 'import bridgetree, numpy, yaml'
preflight_json="$(bash scripts/run_evidence_bridge.sh preflight "$config")"
printf '%s\n' "$preflight_json"
"$BRIDGETREE_BASE_PYTHON" -c '
import json, sys
v=json.load(sys.stdin)
d=v.get("dataset",{})
methods=v.get("methods",[])
checks = [v.get("status")=="preflight_complete", v.get("model_calls")==0,
          v.get("inference_complete") is False, d.get("questions")==589,
          d.get("synthetic") is False, d.get("split")=="32k",
          d.get("dataset_revision")=="fd7c30f071d5c2ee2a211506783be222d7b6002e",
          "evidence_bridge" in methods, v.get("expected_tasks")==589*len(methods),
          v.get("summary",{}).get("pending_tasks")==589*len(methods)]
if not all(checks): raise SystemExit("full 32k data-only preflight failed; experiment not started")
' <<<"$preflight_json"
bash scripts/run_evidence_bridge.sh start "$config"
printf '%s\n' \
  "Detached inference submitted; closing SSH will not stop it." \
  "Mode: train_free; optimizer_steps=0; weights_updated=false." \
  "Manage: bash scripts/run_evidence_bridge.sh {status|log|summary|stop|resume}" \
  "Modules: bash scripts/run_evidence_bridge.sh module-log scheduler" \
  "Retain custom BACKGROUND_STATE_DIR and BRIDGETREE_BASE_PYTHON for management commands."
