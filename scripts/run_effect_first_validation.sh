#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

python_bin="${BRIDGETREE_PYTHON:-$repo_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="python3"
fi

config="${CONFIG:-configs/default.yaml}"
override_config="${OVERRIDE_CONFIG:-configs/personamem32k_effect_first.yaml}"
output_dir="${OUTPUT_DIR:-outputs/effect-first-validation}"
generate="${GENERATE:-true}"

args=(
  -m bridgetree.cli validate-effect-first
  --config "$config"
  --override-config "$override_config"
  --output-dir "$output_dir"
  --method dense_rerank_20
  --method dense_rerank_28
  --method bridgetree_union_rerank
  --method bridgetree_guided_rerank
  --method bridgetree_guided_pathfilter
  --method full_pool_rerank
  --dense-pool-width "${DENSE_POOL_WIDTH:-20}"
  --anchor-width "${ANCHOR_WIDTH:-12}"
  --expand-branch-count "${EXPAND_BRANCH_COUNT:-2}"
  --branch-overfetch-width "${BRANCH_OVERFETCH_WIDTH:-8}"
  --branch-keep-width "${BRANCH_KEEP_WIDTH:-4}"
  --probe-mode "${PROBE_MODE:-query_anchor}"
)

if [[ -n "${LIMIT:-}" ]]; then
  args+=(--limit "$LIMIT")
fi
if [[ "$generate" == "true" ]]; then
  args+=(--generate)
else
  args+=(--no-generate)
fi
if [[ "${PATH_FILTER:-true}" == "true" ]]; then
  args+=(--path-filter)
else
  args+=(--no-path-filter)
fi
if [[ "${RERANK_USE_OPTIONS:-true}" == "true" ]]; then
  args+=(--rerank-use-options)
else
  args+=(--no-rerank-use-options)
fi
if [[ "${RERANK_INCLUDE_TIME:-true}" == "true" ]]; then
  args+=(--rerank-include-time)
else
  args+=(--no-rerank-include-time)
fi
args+=("$@")

export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python_bin" "${args[@]}"
