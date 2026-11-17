# WebWalker v13 安装与两题验证

本包续接 2026-10-16 凌晨中断的工程修复交付，源码固定为 `8a491f36aa129d6a869a8df6906f788b03ca0e06`。
包含 WebWalkerQA 全部 680 题、独立安装器与 PDF 依赖；网页仍需在线访问。

凌晨的真实模型测试中，官方第二题两组均答对并通过来源审计，第一题两组仍未回答，
两组各为 1/2。此结果来自已恢复且校验历史 SHA256 的记录；原始临时运行目录已丢失，
本次没有重新请求真实模型。当前重新验证的项目与结果详见包内 `validation.json`。
本包用于安装和小规模复测，尚无 Linux 实测或 680 题全量结果。

## 1. 上传三个文件到 Linux 的 `~/bt/`

- `dagbt_webwalker_v4_access_v13_experiment.tar.gz`
- `dagbt_webwalker_v4_access_v13_experiment.tar.gz.sha256`
- 本说明文件（可选）

## 2. 校验并安装到独立新目录

```bash
cd ~/bt
sha256sum -c dagbt_webwalker_v4_access_v13_experiment.tar.gz.sha256
mkdir -p ~/dagbt_patches/webwalker_v4_access_v13
tar -xzf dagbt_webwalker_v4_access_v13_experiment.tar.gz -C ~/dagbt_patches/webwalker_v4_access_v13
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
bash ~/dagbt_patches/webwalker_v4_access_v13/dagbt_webwalker_v4_experiment/install_and_smoke.sh
```

默认新目标为 `~/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2`；
来源为 `~/dagbt_runs/20261014_personamem_v4_experiment/dagv2`，必须保留该来源目录。
安装器会核对 107 个公共核心文件，只从来源复用本地凭据，不覆盖旧实验。
以上最后一步安装浏览器并跑离线夹具，通过不等于真实题答对。

若服务器此前已安装 access_v2 浏览器，可在安装命令前运行下面这段以复用同服务器的缓存：

```bash
TASK_OLD="$HOME/dagbt_runs/20261015_webwalker_v4_access_v2_experiment/dagv2"
TASK_NEW="$HOME/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2"
mkdir -p "$TASK_NEW/_webwalker_browser_vendor" "$TASK_NEW/_webwalker_browsers"
cp -a "$TASK_OLD/_webwalker_browser_vendor/." "$TASK_NEW/_webwalker_browser_vendor/"
cp -a "$TASK_OLD/_webwalker_browsers/." "$TASK_NEW/_webwalker_browsers/"
```

仍需执行正常安装命令；它会实际启动浏览器。若已无缺库错误，无需安装系统库。
若再次提示最初的四项系统库缺失，可执行：

```bash
sudo apt-get update
sudo apt-get install -y libatk1.0-0t64 libatspi2.0-0t64 libxdamage1 libasound2t64
```

## 3. PersonaMem 已正常结束或干净停止后，跑真实两题

```bash
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
cd ~/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2
bash scripts/run_webwalker.sh smoke
```

这一步才会访问真实网站和模型，执行官方前两题 × 两组，并独立评分。
默认结果目录是 `outputs/webwalkerqa_v4_access_v13_smoke`。安装器和运行器不会替你停止 PersonaMem。
运行器要求没有活跃 writer，且 PersonaMem 状态为 `complete`、`complete_with_failures` 或 `stopped`。

查看 `progress.json`、`evaluation.json`、`generation_summary.json`；
其中 `evaluation.json` 包含两组正确率、环境排除数和覆盖率。
脚本正常退出并不代表所有题都答对。

第二题诊断：

```bash
"$DAGBT_PYTHON" scripts/webwalker_diagnose.py \
  --output outputs/webwalkerqa_v4_access_v13_smoke --question wwqa-0001
```

需要保留已有输出并另跑一次时，显式使用新的输出目录，避免读取上一次结果：

```bash
WEBWALKER_OUTPUT=outputs/webwalkerqa_v4_access_v13_smoke_2 bash scripts/run_webwalker.sh smoke
```

根页面不可访问时，两组按同题成对排除并报告覆盖率；中间链接故障、模型错误、预算耗尽仍保留为失败。
请先核对这次 Linux 两题复测，再决定是否启动全量。
