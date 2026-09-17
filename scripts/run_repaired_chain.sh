#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
export BACKGROUND_STATE_DIR="$repo_dir/outputs/background-service-fixed"
export OUTPUT_DIR="$repo_dir/outputs/chain-service-fixed"
action="${1:-status}"
case "$action" in
  start)
    bundle="${2:-$repo_dir/outputs/reranker_regression_20260917_verified}"
    test -f "$bundle/manifest.json" || { echo "Missing regression bundle: $bundle" >&2; exit 1; }
    python_bin="${BRIDGETREE_BASE_PYTHON:-$repo_dir/.venv/bin/python}"
    run_prefix="dependency_$(date +%Y%m%d_%H%M%S)_$$"
    exec "$python_bin" scripts/background_entrypoint.py start \
      --job chain_full --state-dir "$BACKGROUND_STATE_DIR" --cwd "$repo_dir" \
      --run-root "$OUTPUT_DIR" --run-prefix "$run_prefix" --exact-run-dir "$OUTPUT_DIR/$run_prefix" \
      --artifact acceptance.json=chain_full.acceptance.json \
      --artifact summary.json=chain_full.summary.json \
      --artifact progress.json=chain_full.progress.json \
      --artifact completion.json=chain_full.completion.json \
      -- "$python_bin" scripts/repaired_chain_worker.py \
      --config configs/chain_service_fixed.yaml --bundle "$bundle" --output-dir "$OUTPUT_DIR/$run_prefix"
    ;;
  status|log|stop)
    exec bash scripts/run_chain.sh "$action"
    ;;
  *)
    echo "usage: bash scripts/run_repaired_chain.sh {start|status|log|stop} [bundle]" >&2
    exit 2
    ;;
esac
