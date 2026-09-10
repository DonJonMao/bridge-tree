#!/usr/bin/env bash
set -euo pipefail
umask 077

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_dir"

config="${1:-configs/chain_full.yaml}"
setup_python="${BRIDGETREE_SETUP_PYTHON:-python3}"
venv_dir="${BRIDGETREE_VENV_DIR:-$repo_dir/.venv}"
skip_install="${BRIDGETREE_SKIP_INSTALL:-false}"
allow_non_linux="${BRIDGETREE_ALLOW_NON_LINUX:-false}"
state_dir="${BACKGROUND_STATE_DIR:-$repo_dir/outputs/background}"
run_root="${OUTPUT_DIR:-$repo_dir/outputs/chain}"
minimum_free_gb="${BRIDGETREE_MIN_FREE_GB:-20}"

case "$skip_install:$allow_non_linux" in
  true:true|true:false|false:true|false:false) ;;
  *)
    echo "BRIDGETREE_SKIP_INSTALL and BRIDGETREE_ALLOW_NON_LINUX must be true or false" >&2
    exit 2
    ;;
esac

if [[ "$(uname -s)" != "Linux" && "$allow_non_linux" != "true" ]]; then
  echo "start_chain_linux.sh only supports Linux" >&2
  exit 1
fi

case "$skip_install" in
  true|false) ;;
  *)
    echo "BRIDGETREE_SKIP_INSTALL must be true or false" >&2
    exit 2
    ;;
esac

if [[ ! -f "$config" ]]; then
  echo "Chain configuration is unavailable: $config" >&2
  exit 1
fi

if ! command -v "$setup_python" >/dev/null 2>&1; then
  echo "Python executable is unavailable: $setup_python" >&2
  exit 1
fi

"$setup_python" - <<'PY'
import sys

if sys.version_info < (3, 9):
    raise SystemExit(
        f"BridgeTree requires Python >= 3.9; found {sys.version.split()[0]}"
    )
PY

resolve_path() {
  "$setup_python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$1"
}
config="$(resolve_path "$config")"
state_dir="$(resolve_path "$state_dir")"
run_root="$(resolve_path "$run_root")"
"$setup_python" - "$repo_dir" "$state_dir" "$run_root" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1]).resolve()
state = Path(sys.argv[2]).resolve()
run_root = Path(sys.argv[3]).resolve()
for label, path in (("BACKGROUND_STATE_DIR", state), ("OUTPUT_DIR", run_root)):
    if path in {Path("/"), Path.home().resolve(), repo}:
        raise SystemExit(f"unsafe {label} target: {path}")
if state == run_root:
    raise SystemExit("BACKGROUND_STATE_DIR and OUTPUT_DIR must be distinct")
PY

venv_dir="$("$setup_python" - "$repo_dir" "$venv_dir" "$state_dir" "$run_root" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).expanduser().resolve()
state = Path(sys.argv[3]).resolve()
run_root = Path(sys.argv[4]).resolve()
home = Path.home().resolve()
if target in {Path("/"), repo, home, state, run_root}:
    raise SystemExit(f"unsafe BRIDGETREE_VENV_DIR target: {target}")
print(target)
PY
)"

mkdir -p "$state_dir" "$run_root"
if [[ ! -w "$state_dir" || ! -w "$run_root" ]]; then
  echo "Chain state/output directories must be writable" >&2
  exit 1
fi

lock_dir="$state_dir/.start_chain_linux.lock"
"$setup_python" - "$lock_dir" "$$" <<'PY'
import os
from pathlib import Path
import sys

lock = Path(sys.argv[1])
owner = lock / "pid"
try:
    lock.mkdir()
except FileExistsError:
    entries = list(lock.iterdir()) if lock.is_dir() else []
    if len(entries) != 1 or entries[0] != owner or not owner.is_file():
        raise SystemExit(f"unsafe or malformed Chain bootstrap lock: {lock}")
    try:
        old_pid = int(owner.read_text(encoding="utf-8").strip())
        os.kill(old_pid, 0)
    except ProcessLookupError:
        owner.unlink()
        lock.rmdir()
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise SystemExit(f"another Chain bootstrap won the lock race: {lock}") from exc
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot validate Chain bootstrap lock: {lock}") from exc
    else:
        raise SystemExit(f"another Chain bootstrap is active with pid {old_pid}")
owner.write_text(sys.argv[2] + "\n", encoding="utf-8")
PY
cleanup_lock() {
  local recorded_pid=""
  if [[ -f "$lock_dir/pid" ]]; then
    IFS= read -r recorded_pid < "$lock_dir/pid" || true
  fi
  if [[ "$recorded_pid" == "$$" ]]; then
    unlink "$lock_dir/pid" 2>/dev/null || true
    rmdir "$lock_dir" 2>/dev/null || true
  fi
}
trap cleanup_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf -v management_environment \
  'cd %q && BRIDGETREE_BASE_PYTHON=%q BACKGROUND_STATE_DIR=%q OUTPUT_DIR=%q' \
  "$repo_dir" "$venv_dir/bin/python" "$state_dir" "$run_root"
status_json="$("$setup_python" "$repo_dir/scripts/background_entrypoint.py" \
  status --job chain_full --state-dir "$state_dir")"
previous_state="$("$setup_python" -c '
import json, sys
value = json.load(sys.stdin)
print(value.get("state", ""))
' <<<"$status_json")"
case "$previous_state" in
  not_started|completed) ;;
  starting|running)
    printf '%s\n' "$status_json"
    echo "a Chain run is already active; no environment or run was changed" >&2
    exit 1
    ;;
  failed|interrupted)
    printf '%s\n' "$status_json"
    echo "the previous Chain run is resumable; run: $management_environment bash scripts/run_chain.sh resume" >&2
    exit 1
    ;;
  *)
    echo "cannot interpret existing Chain status: $previous_state" >&2
    exit 1
    ;;
esac

"$setup_python" - "$run_root" "$minimum_free_gb" <<'PY'
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
try:
    minimum = float(sys.argv[2])
except ValueError as exc:
    raise SystemExit("BRIDGETREE_MIN_FREE_GB must be numeric") from exc
if minimum < 0:
    raise SystemExit("BRIDGETREE_MIN_FREE_GB must be non-negative")
free = shutil.disk_usage(root).free
required = int(minimum * 1024**3)
if free < required:
    raise SystemExit(
        f"insufficient free disk under {root}: {free / 1024**3:.2f} GiB; "
        f"require at least {minimum:.2f} GiB"
    )
PY

if [[ "${BRIDGETREE_CHAT_API_KEY+x}" == "x" && -z "${BRIDGETREE_CHAT_API_KEY:-}" ]]; then
  echo "BRIDGETREE_CHAT_API_KEY is set but empty" >&2
  exit 1
fi

if [[ -e "$venv_dir" ]]; then
  if [[ ! -f "$venv_dir/pyvenv.cfg" || ! -x "$venv_dir/bin/python" ]]; then
    echo "refusing to repair or overwrite an incomplete virtual environment: $venv_dir" >&2
    exit 1
  fi
else
  printf 'Creating Linux virtual environment: %s\n' "$venv_dir"
  "$setup_python" -m venv "$venv_dir"
fi
venv_python="$venv_dir/bin/python"

"$venv_python" - "$venv_dir" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1]).resolve()
if sys.version_info < (3, 9):
    raise SystemExit("the selected virtual environment requires Python >= 3.9")
if Path(sys.prefix).resolve() != target:
    raise SystemExit(f"virtual environment identity mismatch: {sys.prefix} != {target}")
PY

if [[ "$skip_install" == "false" ]]; then
  printf 'Installing BridgeTree into: %s\n' "$venv_dir"
  if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    "$venv_python" -m ensurepip --upgrade
  fi
  "$venv_python" -m pip install --disable-pip-version-check -e "$repo_dir"
fi

"$venv_python" -c "import bridgetree, numpy, yaml" >/dev/null
"$venv_python" - "$config" "$repo_dir" "$minimum_free_gb" <<'PY'
from pathlib import Path
import os
import shutil
import sys
import tempfile

import yaml

from bridgetree.dependency_config import load_dependency_config

config = Path(sys.argv[1]).resolve()
repo = Path(sys.argv[2]).resolve()
seen = set()
pending = [config]
while pending:
    path = pending.pop()
    if path in seen:
        continue
    seen.add(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SystemExit(f"configuration root must be a mapping: {path}")
    credential = path.parent / "credentials.local.yaml"
    if credential.is_file() and credential.stat().st_mode & 0o077:
        raise SystemExit(
            f"private credential file must not be group/other accessible: {credential}"
        )
    base = raw.get("base_config")
    if isinstance(base, str) and base.strip():
        base_path = Path(base).expanduser()
        pending.append((path.parent / base_path).resolve() if not base_path.is_absolute() else base_path.resolve())

resolved = load_dependency_config(config)
cache = Path(resolved.runtime.cache_dir).expanduser()
if not cache.is_absolute():
    cache = repo / cache
cache.mkdir(parents=True, exist_ok=True)
try:
    descriptor, probe = tempfile.mkstemp(prefix=".chain-write-probe-", dir=cache)
    os.close(descriptor)
    Path(probe).unlink()
except OSError as exc:
    raise SystemExit(f"Chain cache directory is not writable: {cache}") from exc
minimum = float(sys.argv[3])
free = shutil.disk_usage(cache).free
if free < int(minimum * 1024**3):
    raise SystemExit(
        f"insufficient free disk under Chain cache {cache}: "
        f"{free / 1024**3:.2f} GiB; require at least {minimum:.2f} GiB"
    )
PY
export BRIDGETREE_BASE_PYTHON="$venv_python"
export BACKGROUND_STATE_DIR="$state_dir"
export OUTPUT_DIR="$run_root"
printf -v management_environment \
  'cd %q && BRIDGETREE_BASE_PYTHON=%q BACKGROUND_STATE_DIR=%q OUTPUT_DIR=%q' \
  "$repo_dir" "$venv_python" "$state_dir" "$run_root"

printf 'Running full data-only preflight (zero model calls): %s\n' "$config"
preflight_json="$(bash "$repo_dir/scripts/run_chain.sh" preflight "$config")"
printf '%s\n' "$preflight_json"
"$setup_python" -c '
import json, sys

value = json.load(sys.stdin)
dataset = value.get("dataset", {})
summary = value.get("summary", {})
checks = {
    "status": value.get("status") == "preflight_complete",
    "questions": dataset.get("questions") == 589,
    "tasks": value.get("expected_tasks") == 2945,
    "model_calls": value.get("model_calls") == 0,
    "pending": summary.get("pending_tasks") == 2945,
    "inference_complete": value.get("inference_complete") is False,
    "synthetic": dataset.get("synthetic") is False,
    "revision": dataset.get("dataset_revision") == "fd7c30f071d5c2ee2a211506783be222d7b6002e",
    "split": dataset.get("split") == "32k",
    "methods": value.get("methods") == [
        "dense",
        "dense_rerank",
        "activation",
        "context_marginal",
        "activation_fixed_pool",
    ],
}
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("full data-only preflight contract failed: " + ", ".join(failed))
' <<<"$preflight_json"

printf 'Starting detached train-free inference run: %s\n' "$config"
start_json="$(bash "$repo_dir/scripts/run_chain.sh" start "$config")"
printf '%s\n' "$start_json"
if ! "$setup_python" -c '
import json, sys

value = json.load(sys.stdin)
checks = {
    "launch_result": value.get("launch_result") == "started",
    "monitor_ready": value.get("monitor_ready") is True,
    "run_dir": isinstance(value.get("run_dir"), str) and bool(value["run_dir"]),
    "state": value.get("state") in {"starting", "running"},
}
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("detached launch contract failed: " + ", ".join(failed))
' <<<"$start_json"; then
  echo "the monitor may already be active; do not retry start before checking status" >&2
  exit 1
fi

printf '%s\n' \
  "Detached run submitted. Closing SSH will not stop it." \
  "Status:     $management_environment bash scripts/run_chain.sh status" \
  "Main log:   $management_environment bash scripts/run_chain.sh log" \
  "Module log: $management_environment bash scripts/run_chain.sh module-log effectiveness" \
  "Current:    $management_environment bash scripts/run_chain.sh module-log effectiveness-current" \
  "Resume:     $management_environment bash scripts/run_chain.sh resume" \
  "Stop:       $management_environment bash scripts/run_chain.sh stop" \
  "Mode:       train_free (optimizer_steps=0, weights_updated=false)"
