#!/usr/bin/env bash
set -euo pipefail
patch_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target="$HOME/dagbt_runs/20261011_personamem_a48/dagv2"
python="${DAGBT_PYTHON:-$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python}"
"$python" "$patch_dir/apply_patch.py" --target "$target"
cd -- "$target"
"$python" -m dagbt.runner launch \
    --config configs/residual-memory.personamem16k.json \
    --datasets personamem \
    --arms original dagbt_residual_memory_v1 \
    --limit 2 \
    --output outputs/personamem_a48_v3_smoke
