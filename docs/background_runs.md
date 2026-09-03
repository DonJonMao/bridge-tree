# 一键后台运行

服务器上的正式任务不再要求 tmux、screen、`nohup`、重定向或手动记录 PID。
后台管理器使用独立进程 session 启动前台实现，启动命令返回后即可关闭 SSH 和电脑。

## 效果优先六方法验证

```bash
./scripts/start_effect_first_background.sh
```

固定文件：

| 文件 | 内容 |
| --- | --- |
| `outputs/background/effect_first.log` | 从启动信息到结束状态的全部 stdout/stderr |
| `outputs/background/effect_first.status.json` | `starting/running/completed/failed/interrupted`、PID、命令、起止时间、秒数、退出码、运行目录 |
| `outputs/background/effect_first.pid` | 后台监控进程 PID |
| `outputs/background/effect_first.exit` | 结束后的数字退出码；`0` 表示脚本成功 |
| `outputs/background/effect_first.run_dir` | 本次 timestamped 原始结果目录 |
| `outputs/background/effect_first.summary.json` | 自动复制的 `effect_summary.json` |
| `outputs/background/effect_first.results.csv` | 自动复制的六方法结果表 |
| `outputs/background/effect_first.paired_results.json` | 自动复制的逐题配对结果 |

查看状态和最近 100 行日志：

```bash
./scripts/start_effect_first_background.sh status
./scripts/start_effect_first_background.sh log
```

若需要更多日志行：

```bash
LINES=300 ./scripts/start_effect_first_background.sh log
```

原有环境变量仍可直接使用。例如：

```bash
DENSE_POOL_WIDTH=20 \
ANCHOR_WIDTH=12 \
EXPAND_BRANCH_COUNT=2 \
BRANCH_OVERFETCH_WIDTH=8 \
BRANCH_KEEP_WIDTH=4 \
./scripts/start_effect_first_background.sh
```

## 完整 32K 调参

```bash
./scripts/start_train_32k_background.sh
```

固定文件：

| 文件 | 内容 |
| --- | --- |
| `outputs/background/train_32k.log` | 安装、检查、服务预检、调参和审计的全部输出 |
| `outputs/background/train_32k.status.json` | 生命周期、PID、起止时间、耗时、退出码和真实运行目录 |
| `outputs/background/train_32k.pid` | 后台监控进程 PID |
| `outputs/background/train_32k.exit` | 最终退出码 |
| `outputs/background/train_32k.run_dir` | 本次 `tune_*` 目录 |
| `outputs/background/train_32k.summary.json` | 自动复制的 `final_summary.json` |
| `outputs/background/train_32k.audit.json` | 自动复制的 `completion_audit.json` |
| `outputs/background/train_32k.best_config.json` | 自动复制的 `best_config.json` |

查看状态和日志：

```bash
./scripts/start_train_32k_background.sh status
./scripts/start_train_32k_background.sh log
```

启动脚本仍支持原来的环境覆盖：

```bash
OUTPUT_DIR=/data/bridgetree/tuning-32k \
OVERRIDE_CONFIG=configs/server.yaml \
./scripts/start_train_32k_background.sh
```

## 重复启动与历史记录

同名任务仍在运行时再次执行启动命令不会创建第二份任务，返回值中的
`launch_result` 为 `already_running`。这可以避免误点造成两组模型请求并发。

任务完成或失败后再次启动时，旧的固定状态、日志和结果副本会自动移动到：

```text
outputs/background/history/<job>_<start-time>/
```

新的任务继续使用相同固定文件名。原始 timestamped 实验目录不会被移动或删除。
如果服务器在任务中途重启，下一次 `status` 会把失去后台进程的任务标记为
`interrupted`。

可通过 `BACKGROUND_STATE_DIR` 把整组固定文件放到其他磁盘。后台状态不会记录完整
环境变量或 API key；精确实验配置仍由 timestamped 运行目录中的
`resolved_config.json` 保存。
