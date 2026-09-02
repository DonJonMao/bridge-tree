#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

python_bin="${BRIDGETREE_PYTHON:-$repo_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="python3"
fi

CONFIG="${CONFIG:-configs/default.yaml}"
OVERRIDE_CONFIG="${OVERRIDE_CONFIG:-}"
METHOD="${METHOD:-bridgetree}"
INITIAL_WIDTH="${INITIAL_WIDTH:-12}"
BRANCH_WIDTH="${BRANCH_WIDTH:-8}"
CONTEXT_SIZE="${CONTEXT_SIZE:-5}"
SEARCH_BUDGET="${SEARCH_BUDGET:-100}"
MAX_ANN_CALLS="${MAX_ANN_CALLS:-32}"
MAX_CANDIDATE_EXPOSURE="${MAX_CANDIDATE_EXPOSURE:-100}"
MAX_DEPTH="${MAX_DEPTH:-2}"
CLUSTER_MODE="${CLUSTER_MODE:-fixed}"
CLUSTER_COUNT="${CLUSTER_COUNT:-4}"
MAX_CLUSTERS="${MAX_CLUSTERS:-8}"
MIN_CLUSTER_SIZE="${MIN_CLUSTER_SIZE:-1}"
SEARCH_ORDER="${SEARCH_ORDER:-best_first}"
FEATURE_MODE="${FEATURE_MODE:-rho}"
SELECTION_MODE="${SELECTION_MODE:-rho_logdet}"
STOP_MODE="${STOP_MODE:-budget}"
DIAGNOSTIC_LEVEL="${DIAGNOSTIC_LEVEL:-light}"
ROOT_ANCHOR_WEIGHT="${ROOT_ANCHOR_WEIGHT:-0}"
SEED="${SEED:-42}"
MEMORY_GRANULARITY="${MEMORY_GRANULARITY:-user_assistant_pair}"
INCLUDE_SYSTEM_PERSONA="${INCLUDE_SYSTEM_PERSONA:-true}"
GENERATE="${GENERATE:-false}"

system_flag="--include-system-persona"
if [[ "$INCLUDE_SYSTEM_PERSONA" != "true" ]]; then
  system_flag="--no-include-system-persona"
fi
generate_flag="--no-generate"
if [[ "$GENERATE" == "true" ]]; then
  generate_flag="--generate"
fi
config_args=(--config "$CONFIG")
if [[ -n "$OVERRIDE_CONFIG" ]]; then
  config_args+=(--override-config "$OVERRIDE_CONFIG")
fi

export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python_bin" -m bridgetree.cli run \
  "${config_args[@]}" \
  --method "$METHOD" \
  --initial-width "$INITIAL_WIDTH" \
  --branch-width "$BRANCH_WIDTH" \
  --context-size "$CONTEXT_SIZE" \
  --search-budget "$SEARCH_BUDGET" \
  --max-ann-calls "$MAX_ANN_CALLS" \
  --max-candidate-exposure "$MAX_CANDIDATE_EXPOSURE" \
  --max-depth "$MAX_DEPTH" \
  --cluster-mode "$CLUSTER_MODE" \
  --cluster-count "$CLUSTER_COUNT" \
  --max-clusters "$MAX_CLUSTERS" \
  --min-cluster-size "$MIN_CLUSTER_SIZE" \
  --search-order "$SEARCH_ORDER" \
  --feature-mode "$FEATURE_MODE" \
  --selection-mode "$SELECTION_MODE" \
  --stop-mode "$STOP_MODE" \
  --diagnostic-level "$DIAGNOSTIC_LEVEL" \
  --root-anchor-weight "$ROOT_ANCHOR_WEIGHT" \
  --seed "$SEED" \
  --memory-granularity "$MEMORY_GRANULARITY" \
  "$system_flag" \
  "$generate_flag" \
  "$@"
