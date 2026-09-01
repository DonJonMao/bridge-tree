#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
cd "${project_dir}"

python_bin="${BRIDGETREE_PYTHON:-python3}"
"${python_bin}" -m bridgetree.cli check-ascend --strict
"${python_bin}" -m bridgetree.cli run \
  --config configs/default.yaml \
  --override-config configs/ascend910b.yaml \
  "$@"

