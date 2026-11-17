#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$TASK_ROOT"
TASK_MODE="${1:-smoke}"
TASK_PERSONA="${2:-${PERSONAMEM_OUTPUT:-$HOME/dagbt_runs/20261014_personamem_v4_experiment/dagv2/outputs/personamem_v4_experiment_full}}"
TASK_CONFIG="${DAGBT_BROWSECOMP_CONFIG:-configs/browsecomp-plus-v4.json}"
TASK_JUDGE_CONFIG="${DAGBT_BROWSECOMP_JUDGE_CONFIG:-$TASK_CONFIG}"
TASK_DATA="${BROWSECOMP_DATA:-data/browsecomp_plus}"
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
TASK_OUTPUT="${BROWSECOMP_OUTPUT:-outputs/browsecomp_plus_v4_full}"
case "$TASK_MODE" in
  offline)
    "$TASK_PYTHON" scripts/browsecomp_offline_smoke.py
    "$TASK_PYTHON" -m dagbt.browsecomp_runner preflight --offline --config "$TASK_CONFIG" --data-dir "$TASK_DATA"
    ;;
  preflight)
    "$TASK_PYTHON" -m dagbt.browsecomp_runner preflight --config "$TASK_CONFIG" --data-dir "$TASK_DATA" \
      --after-personamem "$TASK_PERSONA" --output "${TASK_OUTPUT}_preflight"
    ;;
  smoke)
    TASK_OUTPUT="${BROWSECOMP_OUTPUT:-outputs/browsecomp_plus_v4_smoke}"
    "$TASK_PYTHON" scripts/browsecomp_offline_smoke.py
    "$TASK_PYTHON" -m dagbt.browsecomp_runner preflight --config "$TASK_CONFIG" --data-dir "$TASK_DATA" \
      --after-personamem "$TASK_PERSONA" --output "${TASK_OUTPUT}_preflight"
    "$TASK_PYTHON" -m dagbt.browsecomp_runner run --config "$TASK_CONFIG" --data-dir "$TASK_DATA" \
      --after-personamem "$TASK_PERSONA" --limit 2 --output "$TASK_OUTPUT"
    "$TASK_PYTHON" -m dagbt.browsecomp_runner score --config "$TASK_JUDGE_CONFIG" --data-dir "$TASK_DATA" --output "$TASK_OUTPUT"
    ;;
  full)
    "$TASK_PYTHON" -m dagbt.browsecomp_runner preflight --config "$TASK_CONFIG" --data-dir "$TASK_DATA" \
      --after-personamem "$TASK_PERSONA" --output "${TASK_OUTPUT}_preflight"
    mkdir -p "$TASK_OUTPUT"
    nohup "$TASK_PYTHON" -u -m dagbt.browsecomp_runner run --config "$TASK_CONFIG" --data-dir "$TASK_DATA" \
      --after-personamem "$TASK_PERSONA" --output "$TASK_OUTPUT" \
      >> "$TASK_OUTPUT/launcher.log" 2>&1 < /dev/null &
    echo "BrowseComp-Plus launched: PID=$!; log=$TASK_OUTPUT/launcher.log"
    echo "After generation finishes: bash scripts/run_browsecomp_plus.sh score"
    ;;
  status)
    "$TASK_PYTHON" -m dagbt.browsecomp_runner status --output "$TASK_OUTPUT"
    ;;
  stop)
    "$TASK_PYTHON" -m dagbt.browsecomp_runner stop --output "${2:-$TASK_OUTPUT}"
    ;;
  score)
    "$TASK_PYTHON" -m dagbt.browsecomp_runner score --config "$TASK_JUDGE_CONFIG" --data-dir "$TASK_DATA" --output "$TASK_OUTPUT"
    ;;
  *) echo "Usage: $0 {offline|preflight|smoke|full|status|stop|score} [personamem_output or stop_output]" >&2; exit 2 ;;
esac
