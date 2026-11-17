> 当前先不执行启动脚本。access_v4 复核发现输出要求缩窄和导航/阅读闭环缺陷，详见 FAILURE_ANALYSIS.md；下列步骤保留为安装与启动操作记录。

# Linux 启动步骤

将新版 `dagbt_webwalker_v4_access_v4_experiment.tar.gz` 及同名 `.sha256` 上传到 `~/bt/` 后执行以下命令。不要使用旧 v2/v3 包。

```bash
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
```

安装器先检查与离线验证；full 启动前自动检查 PersonaMem writer 锁、模型和精确 tokenize。首站403只作诊断，不会否决全680题。目标目录和输出独立，旧结果保留。

若安装器仍报告最初的四个浏览器系统库缺失，先执行以下命令，再重跑安装命令及后续启动步骤：

```bash
sudo apt-get update
sudo apt-get install -y libatk1.0-0t64 libatspi2.0-0t64 libxdamage1 libasound2t64
```

然后重新执行第一段完整命令。安装检查失败会停止该段，不会继续启动 full。

启动后，`live_writer=true` 且进度由 `running` 持续增加，才说明全量实际在运行。仅打印 PID 不足以证明运行正常。查看日志可用：

```bash
tail -f "$HOME/dagbt_runs/20261015_webwalker_v4_access_v4_experiment/dagv2/outputs/webwalkerqa_v4_access_v4_full/launcher.log"
```

生成结束预计 `completed=total=1360`。随后独立评分，`live_scorer=false` 且 `evaluation_available=true` 后检查：

- `evaluation.json`：共同可访题集的准确率、有效题数、覆盖率、网站排除数及 judge 失败。
- `generation_summary.json`：两组 LLM 次数、输入/输出 token、网页访问、耗时及缺失成本。
- `tasks/`：所有失败与未回答保留，不能只统计成功题；执行成功不等于答对。

此版本不承诺两题或全量答对。固定协议下的失败属于结果，不因此无限调试或免费重跑；没有实际运行的全量实验，也没有全量结果可等待。
