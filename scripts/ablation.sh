#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runner="$repo_dir/scripts/run_personamem.sh"
seeds="${SEEDS:-41 42 43}"

run_config() {
  local label="$1"
  local cluster_mode="$2"
  local search_order="$3"
  local feature_mode="$4"
  local selection_mode="$5"
  local stop_mode="$6"
  local max_depth="$7"
  shift 7
  for seed in $seeds; do
    echo "[BridgeTree ablation] label=$label seed=$seed"
    CLUSTER_MODE="$cluster_mode" \
    SEARCH_ORDER="$search_order" \
    FEATURE_MODE="$feature_mode" \
    SELECTION_MODE="$selection_mode" \
    STOP_MODE="$stop_mode" \
    MAX_DEPTH="$max_depth" \
    SEED="$seed" \
      "$runner" --run-label "${label}_seed${seed}" "$@"
  done
}

run_config "core" fixed best_first rho rho_logdet budget 2 "$@"
run_config "path" fixed best_first path_conditioned path_logdet budget 2 "$@"
run_config "certificate" fixed best_first path_conditioned path_logdet certificate_or_budget 2 "$@"
run_config "full_current" effective_rank best_first path_conditioned path_logdet certificate_or_budget 3 "$@"
run_config "no_cluster" none best_first rho rho_logdet budget 2 "$@"
run_config "bfs" fixed bfs rho rho_logdet budget 2 "$@"
run_config "depth1" fixed best_first rho rho_logdet budget 1 "$@"
run_config "depth2" fixed best_first rho rho_logdet budget 2 "$@"
run_config "depth3" fixed best_first rho rho_logdet budget 3 "$@"
