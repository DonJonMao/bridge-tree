#!/usr/bin/env bash
# Verify and install the isolated access_v4 release, then launch the full experiment.
(
set -euo pipefail
cd ~/bt
sha256sum -c dagbt_webwalker_v4_access_v4_experiment.tar.gz.sha256
TASK_PATCH="$HOME/dagbt_patches/webwalker_v4_access_v4"
mkdir -p "$TASK_PATCH"
tar -xzf dagbt_webwalker_v4_access_v4_experiment.tar.gz -C "$TASK_PATCH"
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
export DAGBT_PERSONAMEM_BASE="$HOME/dagbt_runs/20261014_personamem_v4_experiment/dagv2"
TASK_OLD="$HOME/dagbt_runs/20261015_webwalker_v4_access_v2_experiment/dagv2"
TASK_NEW="$HOME/dagbt_runs/20261015_webwalker_v4_access_v4_experiment/dagv2"
for TASK_DEP in _webwalker_browser_vendor _webwalker_browsers
do
  if [ -d "$TASK_OLD/$TASK_DEP" ]
  then
    mkdir -p "$TASK_NEW/$TASK_DEP"
    cp -a "$TASK_OLD/$TASK_DEP/." "$TASK_NEW/$TASK_DEP/"
  fi
done
bash "$TASK_PATCH/dagbt_webwalker_v4_experiment/install_and_smoke.sh" "$TASK_NEW"
cd "$TASK_NEW"
export DAGBT_WEBWALKER_CONFIG="$TASK_NEW/configs/webwalker-v4.json"
export DAGBT_WEBWALKER_JUDGE_CONFIG="$DAGBT_WEBWALKER_CONFIG"
export WEBWALKER_OUTPUT=outputs/webwalkerqa_v4_access_v4_full
bash scripts/run_webwalker.sh full "$DAGBT_PERSONAMEM_BASE/outputs/personamem_v4_experiment_full"
sleep 3
bash scripts/run_webwalker.sh status
tail -n 15 "$WEBWALKER_OUTPUT/launcher.log"
)
