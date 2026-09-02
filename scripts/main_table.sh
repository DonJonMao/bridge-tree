#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runner="$repo_dir/scripts/run_personamem.sh"
seeds="${SEEDS:-41 42 43}"
methods="${METHODS:-dense dense_rerank rfmem_familiarity rfmem_recollection rfmem cluster_prf bridgetree}"
group_dir="${OUTPUT_DIR:-$repo_dir/outputs/main-table/main_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$group_dir"

for method in $methods; do
  for seed in $seeds; do
    echo "[BridgeTree main table] method=$method seed=$seed"
    METHOD="$method" SEED="$seed" GENERATE="${GENERATE:-true}" \
      "$runner" --output-dir "$group_dir" --run-label "${method}_seed${seed}" "$@"
  done
done

python_bin="${BRIDGETREE_PYTHON:-$repo_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="python3"
fi
PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$python_bin" -m bridgetree.cli aggregate --input-dir "$group_dir" --reference-label bridgetree
