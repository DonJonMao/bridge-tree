#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if (( $# > 0 )); then
  echo "formal 32K launcher does not accept trailing CLI overrides" >&2
  echo "use APP_CONFIG, TUNING_CONFIG, OVERRIDE_CONFIG, or OUTPUT_DIR" >&2
  exit 2
fi

app_config="${APP_CONFIG:-configs/default.yaml}"
tuning_config="${TUNING_CONFIG:-configs/train.yaml}"
override_config="${OVERRIDE_CONFIG:-}"
venv_dir="${BRIDGETREE_VENV:-$repo_dir/.venv}"
bootstrap="${BOOTSTRAP:-true}"
run_checks="${RUN_CHECKS:-true}"
check_services="${CHECK_SERVICES:-true}"
download_data="${DOWNLOAD_DATA:-true}"
preflight_only="${PREFLIGHT_ONLY:-false}"

if [[ ! -f "$app_config" ]]; then
  echo "missing app config: $app_config" >&2
  exit 2
fi
if [[ ! -f "$tuning_config" ]]; then
  echo "missing tuning config: $tuning_config" >&2
  exit 2
fi

if [[ -n "${BRIDGETREE_PYTHON:-}" ]]; then
  python_bin="$BRIDGETREE_PYTHON"
  if ! "$python_bin" -c "import sys" >/dev/null 2>&1; then
    echo "BRIDGETREE_PYTHON is not runnable: $python_bin" >&2
    exit 2
  fi
else
  python_bin="$venv_dir/bin/python"
  if [[ ! -x "$python_bin" ]] || ! "$python_bin" -c "import sys" >/dev/null 2>&1; then
    base_python="${BRIDGETREE_BASE_PYTHON:-python3}"
    if [[ -z "$venv_dir" || "$venv_dir" == "/" ]]; then
      echo "refusing unsafe virtualenv path: $venv_dir" >&2
      exit 2
    fi
    echo "creating portable virtualenv: $venv_dir"
    "$base_python" -m venv --clear "$venv_dir"
  fi
fi

export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "$bootstrap" == "true" ]]; then
  echo "installing BridgeTree and verification dependencies"
  "$python_bin" -m pip install --disable-pip-version-check -e '.[test]'
fi

data_args=(
  -m bridgetree.cli prepare-configured-data
  --config "$app_config"
)
if [[ -n "$override_config" ]]; then
  data_args+=(--override-config "$override_config")
fi
if [[ "$download_data" != "true" ]]; then
  data_args+=(--no-download-missing)
fi
"$python_bin" "${data_args[@]}"

if [[ "$run_checks" == "true" ]]; then
  echo "running unit tests, lint, and offline synthetic smoke"
  "$python_bin" -m pytest -q
  "$python_bin" -m ruff check src tests
  "$python_bin" -m bridgetree.cli smoke-synthetic --output-dir outputs/smoke
fi

preflight_args=(
  -m bridgetree.cli preflight-tuning
  --config "$app_config"
  --tuning-config "$tuning_config"
  --require-full-32k
)
if [[ -n "$override_config" ]]; then
  preflight_args+=(--override-config "$override_config")
fi
if [[ "$check_services" == "true" ]]; then
  preflight_args+=(--check-services)
fi

echo "validating full 32K protocol, data, and required services"
"$python_bin" "${preflight_args[@]}"

if [[ "$preflight_only" == "true" ]]; then
  echo "preflight complete; PREFLIGHT_ONLY=true, tuning was not started"
  exit 0
fi

tune_args=(
  -m bridgetree.cli tune
  --config "$app_config"
  --tuning-config "$tuning_config"
  --audit-full-32k
)
if [[ -n "$override_config" ]]; then
  tune_args+=(--override-config "$override_config")
fi
if [[ -n "${OUTPUT_DIR:-}" ]]; then
  tune_args+=(--output-dir "$OUTPUT_DIR")
fi

echo "starting full PersonaMem-v1 32K tuning; success requires the persisted completion audit"
exec "$python_bin" "${tune_args[@]}"
