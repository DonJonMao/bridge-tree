#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_dir"

usage() {
  echo 'Usage: bash scripts/start_diagnostics_linux.sh [CONFIG] [--offline]'
  echo 'Default CONFIG: configs/diagnostic_28.server.yaml'
  echo 'Installs base Python dependencies into .venv-diagnostics and delegates detached startup.'
}

config="configs/diagnostic_28.server.yaml"
config_supplied=false
offline=false
for argument in "$@"; do
  case "$argument" in
    --help|-h) usage; exit 0 ;;
    --offline)
      if [[ "$offline" == true ]]; then echo 'duplicate --offline flag' >&2; exit 2; fi
      offline=true
      ;;
    --*) echo 'unknown option' >&2; usage >&2; exit 2 ;;
    *)
      if [[ "$config_supplied" == true ]]; then echo 'only one CONFIG is accepted' >&2; exit 2; fi
      config="$argument"
      config_supplied=true
      ;;
  esac
done

setup_python="${BRIDGETREE_SETUP_PYTHON:-python3}"
venv_dir="${BRIDGETREE_VENV_DIR:-$repo_dir/.venv-diagnostics}"
state_dir="${DIAGNOSTIC_STATE_DIR:-$repo_dir/outputs/background-diagnostics}"
run_root="${DIAGNOSTIC_RUN_ROOT:-$repo_dir/outputs/diagnostics}"
skip_install="${BRIDGETREE_SKIP_INSTALL:-false}"
allow_non_linux="${BRIDGETREE_ALLOW_NON_LINUX:-false}"
case "$skip_install:$allow_non_linux" in
  true:true|true:false|false:true|false:false) ;;
  *) echo 'BRIDGETREE_SKIP_INSTALL and BRIDGETREE_ALLOW_NON_LINUX must be true or false' >&2; exit 2 ;;
esac
if [[ "$(uname -s)" != Linux && "$allow_non_linux" != true ]]; then
  echo 'start_diagnostics_linux.sh only supports Linux' >&2
  exit 1
fi
if ! command -v "$setup_python" >/dev/null 2>&1; then
  echo "Python executable is unavailable: $setup_python" >&2
  exit 1
fi
"$setup_python" -c 'import sys; sys.version_info >= (3, 9) or sys.exit("BridgeTree requires Python >= 3.9")'
"$setup_python" - "$venv_dir" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1]).expanduser()
if path.is_symlink() and not path.exists():
    raise SystemExit("refusing to repair a dangling virtual environment symlink")
PY
resolve_path() {
  "$setup_python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$1"
}
config="$(resolve_path "$config")"
venv_dir="$(resolve_path "$venv_dir")"
state_dir="$(resolve_path "$state_dir")"
run_root="$(resolve_path "$run_root")"
if [[ ! -f "$config" ]]; then
  echo "Diagnostic configuration is unavailable: $config" >&2
  exit 1
fi
if [[ ! -f "$repo_dir/scripts/background_entrypoint.py" || ! -f "$repo_dir/scripts/run_diagnostics.sh" ]]; then
  echo 'Diagnostic background entry points are unavailable; deploy the complete repository' >&2
  exit 1
fi
"$setup_python" - "$repo_dir" "$venv_dir" "$state_dir" "$run_root" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])
targets = dict(zip(("BRIDGETREE_VENV_DIR", "DIAGNOSTIC_STATE_DIR", "DIAGNOSTIC_RUN_ROOT"),
                   map(Path, sys.argv[2:])))
for label, path in targets.items():
    if path in {Path("/"), Path.home().resolve(), repo} or path in repo.parents:
        raise SystemExit(f"unsafe {label} target: {path}")
    if path.exists() and not path.is_dir():
        raise SystemExit(f"{label} must name a directory: {path}")
items = list(targets.items())
for i, (label, path) in enumerate(items):
    for other_label, other in items[i + 1:]:
        if path == other or path in other.parents or other in path.parents:
            raise SystemExit(f"conflicting directory targets: {label} and {other_label}")
PY

# Atomic, repository-wide setup exclusion also covers two invocations using
# different state directories. Never guess that an existing lock is stale.
lock_dir="$repo_dir/.start_diagnostics_linux.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "Diagnostic bootstrap lock exists: $lock_dir" >&2
  echo 'Another setup may be active. Verify its recorded PID and that no installer is running before manually removing a stale lock.' >&2
  exit 1
fi
printf '%s\n' "$$" > "$lock_dir/pid"
cleanup_lock() {
  local recorded_pid=""
  if [[ -f "$lock_dir/pid" && ! -L "$lock_dir/pid" ]]; then
    IFS= read -r recorded_pid < "$lock_dir/pid" || true
    if [[ "$recorded_pid" == "$$" ]]; then
      unlink "$lock_dir/pid" 2>/dev/null || true
      rmdir "$lock_dir" 2>/dev/null || true
    fi
  fi
}
trap cleanup_lock EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$state_dir" "$run_root"
bootstrap_log="$state_dir/bootstrap.log"
"$setup_python" - "$bootstrap_log" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if path.is_symlink() or (path.exists() and (not path.is_file() or path.stat().st_nlink != 1)):
    raise SystemExit("refusing unsafe bootstrap.log target")
PY

export BRIDGETREE_BASE_PYTHON="$venv_dir/bin/python"
export DIAGNOSTIC_STATE_DIR="$state_dir"
export DIAGNOSTIC_RUN_ROOT="$run_root"

check_previous_run() {
  # The dependency-free manager deliberately tolerates malformed status;
  # setup must fail closed instead of treating corrupt state as a fresh run.
  "$setup_python" - "$state_dir/diagnostics.status.json" <<'PY'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("refusing symlink diagnostic status")
if path.exists():
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        valid = isinstance(value, dict) and value.get("job") == "diagnostics" and isinstance(value.get("state"), str)
    except (OSError, ValueError):
        valid = False
    if not valid:
        raise SystemExit("cannot validate existing diagnostic status; no environment was changed")
PY
  local status_json previous_state
  status_json="$("$setup_python" "$repo_dir/scripts/background_entrypoint.py" \
    status --job diagnostics --state-dir "$state_dir")"
  previous_state="$("$setup_python" -c 'import json, sys; print(json.load(sys.stdin).get("state", ""))' <<<"$status_json")"
  case "$previous_state" in
    not_started|completed) ;;
    starting|running)
      echo "A diagnostic run is already active ($previous_state); refusing setup/start" >&2
      return 1
      ;;
    failed|interrupted)
      echo "The previous diagnostic run is $previous_state; resume it instead of reinstalling:" >&2
      printf 'BRIDGETREE_BASE_PYTHON=%q DIAGNOSTIC_STATE_DIR=%q DIAGNOSTIC_RUN_ROOT=%q bash %q resume\n' \
        "$BRIDGETREE_BASE_PYTHON" "$state_dir" "$run_root" "$repo_dir/scripts/run_diagnostics.sh" >&2
      return 1
      ;;
    *) echo 'Cannot interpret existing diagnostic state; refusing setup/start' >&2; return 1 ;;
  esac
}

bootstrap() {
  printf 'Diagnostic bootstrap log: %s\n' "$bootstrap_log"
  check_previous_run
  if [[ -e "$venv_dir" ]]; then
    if [[ ! -f "$venv_dir/pyvenv.cfg" || ! -x "$venv_dir/bin/python" ]]; then
      echo "Refusing to repair or overwrite an incomplete virtual environment: $venv_dir" >&2
      return 1
    fi
  else
    printf 'Creating independent diagnostic virtual environment: %s\n' "$venv_dir"
    "$setup_python" -m venv "$venv_dir"
  fi
  local venv_python="$venv_dir/bin/python"
  "$venv_python" - "$venv_dir" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
if sys.version_info < (3, 9):
    raise SystemExit("the diagnostic virtual environment requires Python >= 3.9")
if Path(sys.prefix).resolve() != target:
    raise SystemExit("diagnostic virtual environment identity mismatch")
PY
  if [[ "$skip_install" == false ]]; then
    printf 'Installing base BridgeTree dependencies (no local models/CUDA extras): %s\n' "$venv_dir"
    if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
      "$venv_python" -m ensurepip --upgrade
    fi
    PYTHONUNBUFFERED=1 "$venv_python" -m pip install --disable-pip-version-check --no-input -e "$repo_dir"
  fi
  "$venv_python" -c 'import bridgetree, numpy, yaml' >/dev/null
  check_previous_run
  local start_arguments=(start --config "$config")
  if [[ "$offline" == true ]]; then start_arguments+=(--offline); fi
  echo 'Starting detached PR1–PR4 diagnostics; optimizer_steps=0, weights_updated=false'
  bash "$repo_dir/scripts/run_diagnostics.sh" "${start_arguments[@]}"
  printf 'Inspect: BRIDGETREE_BASE_PYTHON=%q DIAGNOSTIC_STATE_DIR=%q DIAGNOSTIC_RUN_ROOT=%q bash %q status\n' \
    "$BRIDGETREE_BASE_PYTHON" "$state_dir" "$run_root" "$repo_dir/scripts/run_diagnostics.sh"
  echo 'Replace status with log to inspect the detached job output.'
}

# Keep installer output visible as it happens and preserve installer/start
# failures through tee. Never echo the environment, credentials or YAML body.
bootstrap 2>&1 | tee -a "$bootstrap_log"
