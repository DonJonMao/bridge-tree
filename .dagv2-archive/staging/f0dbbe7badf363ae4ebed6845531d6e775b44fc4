#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$TASK_ROOT"
TASK_MODE="${1:-smoke}"
TASK_PERSONA="${2:-${PERSONAMEM_OUTPUT:-$HOME/dagbt_runs/20261014_personamem_v4_experiment/dagv2/outputs/personamem_v4_experiment_full}}"
TASK_PYTHON="${DAGBT_PYTHON:-}"
if [[ -z "$TASK_PYTHON" ]]; then
  if [[ -x "$TASK_ROOT/.venv/bin/python" ]]; then
    TASK_PYTHON="$TASK_ROOT/.venv/bin/python"
  elif [[ -x "$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python" ]]; then
    TASK_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
  else
    TASK_PYTHON="python3"
  fi
fi
TASK_OUTPUT="${BENCHMARKS_OUTPUT:-outputs/benchmarks_v4_full}"
TASK_ARGS=(--output "$TASK_OUTPUT"
  --webwalker-config "${DAGBT_WEBWALKER_CONFIG:-configs/webwalker-v4.json}"
  --webwalker-judge-config "${DAGBT_WEBWALKER_JUDGE_CONFIG:-${DAGBT_WEBWALKER_CONFIG:-configs/webwalker-v4.json}}"
  --browsecomp-config "${DAGBT_BROWSECOMP_CONFIG:-configs/browsecomp-plus-v4.json}"
  --browsecomp-judge-config "${DAGBT_BROWSECOMP_JUDGE_CONFIG:-${DAGBT_BROWSECOMP_CONFIG:-configs/browsecomp-plus-v4.json}}"
  --webwalker-data "${WEBWALKER_DATA:-data/webwalkerqa}"
  --browsecomp-data "${BROWSECOMP_DATA:-data/browsecomp_plus}")
case "$TASK_MODE" in
  offline)
    "$TASK_PYTHON" scripts/webwalker_offline_smoke.py
    "$TASK_PYTHON" scripts/browsecomp_offline_smoke.py
    "$TASK_PYTHON" -m dagbt.benchmark_suite preflight "${TASK_ARGS[@]}" --offline
    ;;
  preflight)
    "$TASK_PYTHON" -m dagbt.benchmark_suite preflight "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA"
    ;;
  smoke)
    TASK_OUTPUT="${BENCHMARKS_OUTPUT:-outputs/benchmarks_v4_smoke}"
    TASK_ARGS[1]="$TASK_OUTPUT"
    "$TASK_PYTHON" scripts/webwalker_offline_smoke.py
    "$TASK_PYTHON" scripts/browsecomp_offline_smoke.py
    "$TASK_PYTHON" -m dagbt.benchmark_suite preflight "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA"
    "$TASK_PYTHON" -m dagbt.benchmark_suite run "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA" --limit 2
    ;;
  full)
    "$TASK_PYTHON" -m dagbt.benchmark_suite preflight "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA"
    "$TASK_PYTHON" -m dagbt.benchmark_suite launch "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA"
    echo "Background coordinator log: $TASK_OUTPUT/launcher.log"
    echo "Use: bash scripts/run_benchmarks.sh status"
    ;;
  status)
    "$TASK_PYTHON" -m dagbt.benchmark_suite status --output "$TASK_OUTPUT"
    ;;
  stop)
    "$TASK_PYTHON" -m dagbt.benchmark_suite stop --output "${2:-$TASK_OUTPUT}"
    ;;
  score)
    "$TASK_PYTHON" -m dagbt.benchmark_suite score "${TASK_ARGS[@]}" --after-personamem "$TASK_PERSONA"
    ;;
  *) echo "Usage: $0 {offline|preflight|smoke|full|status|stop|score} [personamem_output or stop_output]" >&2; exit 2 ;;
esac
