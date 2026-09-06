#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runner="$repo_dir/scripts/run_personamem.sh"
seeds="${SEEDS:-41 42 43}"
group_dir="${OUTPUT_DIR:-$repo_dir/outputs/ablations/ablation_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$group_dir"

run_config_tmic() {
  local label="$1"
  local cluster_mode="$2"
  local search_order="$3"
  local feature_mode="$4"
  local selection_mode="$5"
  local stop_mode="$6"
  local max_depth="$7"
  local temporal_measure="$8"
  local measure_propagation="$9"
  local state_information="${10}"
  local information_certificate="${11}"
  shift 11
  for seed in $seeds; do
    echo "[BridgeTree ablation] label=$label seed=$seed"
    CLUSTER_MODE="$cluster_mode" \
    SEARCH_ORDER="$search_order" \
    FEATURE_MODE="$feature_mode" \
    SELECTION_MODE="$selection_mode" \
    STOP_MODE="$stop_mode" \
    MAX_DEPTH="$max_depth" \
    TEMPORAL_MEASURE="$temporal_measure" \
    MEASURE_PROPAGATION="$measure_propagation" \
    STATE_INFORMATION="$state_information" \
    INFORMATION_CERTIFICATE="$information_certificate" \
    SEED="$seed" \
      "$runner" --output-dir "$group_dir" --run-label "${label}_seed${seed}" "$@"
  done
}

# Legacy ablations must be insulated from ambient TMIC environment variables;
# otherwise a shell-level TEMPORAL_MEASURE=true, for example, would silently
# turn the nominal ``core`` row into a different architecture.
run_config() {
  run_config_tmic "$1" "$2" "$3" "$4" "$5" "$6" "$7" false false false false "${@:8}"
}

run_config "core" fixed best_first rho rho_logdet budget 2 "$@"
run_config "path" fixed best_first path_conditioned path_logdet budget 2 "$@"
run_config "certificate" fixed best_first path_conditioned path_logdet certificate_or_budget 2 "$@"
run_config "full_current" effective_rank best_first path_conditioned path_logdet certificate_or_budget 3 "$@"
run_config "no_cluster" none best_first rho rho_logdet budget 2 "$@"
run_config "effective_rank" effective_rank best_first rho rho_logdet budget 2 "$@"
run_config "bfs" fixed bfs rho rho_logdet budget 2 "$@"
run_config "rho_topk" fixed best_first rho rho_topk budget 2 "$@"
run_config "mmr" fixed best_first rho mmr budget 2 "$@"
run_config "depth1" fixed best_first rho rho_logdet budget 1 "$@"
run_config "depth2" fixed best_first rho rho_logdet budget 2 "$@"
run_config "depth3" fixed best_first rho rho_logdet budget 3 "$@"

# Formal TMIC labels (the matrix runner also exposes these as A0--A4).  Keep
# them as explicit script configurations for reproducibility; callers can
# disable this tail with RUN_TMIC_MATRIX=false when only legacy ablations are
# desired.
if [[ "${RUN_TMIC_MATRIX:-true}" == "true" ]]; then
  run_config_tmic "A0" fixed best_first path_conditioned path_logdet budget 2 false false false false "$@"
  run_config_tmic "A1" fixed best_first path_conditioned path_logdet budget 2 true false false false "$@"
  run_config_tmic "A2" fixed best_first path_conditioned path_logdet budget 2 true true false false "$@"
  run_config_tmic "A3" fixed best_first path_conditioned path_logdet budget 2 true true true false "$@"
  run_config_tmic "A4" fixed best_first path_conditioned path_logdet certificate_or_budget 2 true true true true "$@"
fi

python_bin="${BRIDGETREE_PYTHON:-$repo_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="python3"
fi
PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$python_bin" -m bridgetree.cli aggregate --input-dir "$group_dir" --reference-label core
