# WebWalkerQA v4 修复实验包（access v13）

这是独立 WebWalker 部署包。107 个公共 Python 核心文件保持与
`e6677081cdfb33c01db3aaa274a497168f314f78` 逐字节一致；两组仍为
`dagbt_joint_memory_v1` 和 `dagbt_residual_memory_v2`。

**access_v13 候选包若没有独立 `validation.json`，新安装与真实 smoke 状态即为待验证；当前暂不建议启动 680 题全量。**
上一版 access_v12 的本地官方两题、两组共四任务均因预算耗尽未回答，零环境排除；
测试页面上的成功不代表正式问答通过。本版的安装、正式 smoke、答案正确性、平台和限制，
以包内独立 `validation.json` 的实际结果为准。候选没有该文件时为待验证。
本地 Darwin 验证不能当作 Linux 或全量结果；每版使用独立目标和输出目录。

## 安装

上传本包与同名校验文件到 `~/bt/`，执行：

```bash
cd ~/bt
sha256sum -c dagbt_webwalker_v4_access_v13_experiment.tar.gz.sha256
mkdir -p ~/dagbt_patches/webwalker_v4_access_v13
tar -xzf dagbt_webwalker_v4_access_v13_experiment.tar.gz -C ~/dagbt_patches/webwalker_v4_access_v13
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
bash ~/dagbt_patches/webwalker_v4_access_v13/dagbt_webwalker_v4_experiment/install_and_smoke.sh
```

默认新目标：`~/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2`。
默认来源：`~/dagbt_runs/20261014_personamem_v4_experiment/dagv2`。
目标不能覆盖或嵌套在 PersonaMem 来源目录中，安装器不替换任何已有不同内容的文件。
包内不含私人凭据；从来源部署复用本地凭据到新目标，权限为 0600，原文件不修改。
可用第一个参数指定其他新目标，用 `DAGBT_PERSONAMEM_BASE` 指定来源。

若服务器已有 access_v2 的浏览器，可在安装前复制依赖与浏览器缓存，减少下载：

```bash
TASK_OLD="$HOME/dagbt_runs/20261015_webwalker_v4_access_v2_experiment/dagv2"
TASK_NEW="$HOME/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2"
mkdir -p "$TASK_NEW/_webwalker_browser_vendor" "$TASK_NEW/_webwalker_browsers"
cp -a "$TASK_OLD/_webwalker_browser_vendor/." "$TASK_NEW/_webwalker_browser_vendor/"
cp -a "$TASK_OLD/_webwalker_browsers/." "$TASK_NEW/_webwalker_browsers/"
```

只复制这两个目录，不复制旧输出、页面快照或任务缓存。复制后仍执行正常安装命令，
安装器会检查依赖并实际启动 Chromium。浏览器缓存不完整时会补下载；Python vendor 必须完整且来自同一服务器，缺失依赖不保证自动补齐。
若仍报告服务器最初的四个系统动态库缺失，执行：

```bash
sudo apt-get update
sudo apt-get install -y libatk1.0-0t64 libatspi2.0-0t64 libxdamage1 libasound2t64
```

安装器本身不运行 sudo、不更改旧虚拟环境。浏览器下载需要 PyPI 和浏览器 CDN 可访问。
安装命令可加第二个参数 `--no-browser` 跳过浏览器安装；这不会改变默认 `auto` 后端，
需要浏览器回退时仍须完整依赖。PDF 依赖随包提供。
安装后的 offline smoke 使用本地网页和模型 HTTP 夹具，不访问真实模型或外站。

## 运行 smoke 与核对结果

```bash
cd ~/dagbt_runs/20261016_webwalker_v4_access_v13_experiment/dagv2
bash scripts/run_webwalker.sh smoke
```

smoke 默认官方前两题、两组共四任务；结果写到
`outputs/webwalkerqa_v4_access_v13_smoke`，完成生成后独立评分。
它先核对 PersonaMem 的真实 OS writer 锁与 `complete` / `complete_with_failures` / `stopped`
状态。`stopped` 是正常手动停止，不代表全量完成；没有活跃 writer 时可以试跑。
不自动停止或修改 PersonaMem。

核对以下结果：

- `progress.json`：任务是否全部终止，失败数与环境跳过数。
- `tasks/*/*/result.json`、`fusion_events.jsonl`：完整初始输出要求是否保留，实际链接与阅读、修复、义务及终端状态。
- `evaluation.json`：共同可访子集的正确率、有效题数和覆盖率。
- `generation_summary.json`：实际 LLM 请求与 token、网页动作和耗时，含缺失 usage 数。

只读诊断命令：

```bash
"$DAGBT_PYTHON" scripts/webwalker_diagnose.py \
  --output outputs/webwalkerqa_v4_access_v13_smoke --question wwqa-0001
```

没有答案、预算用尽、规划/阅读违规与实际容量不足都保留为失败及成本；
不把它们当网站故障删题。模型持续违反协议时，有界修复仍可能失败。
不要在原失败目录换代码重跑；源码、配置、数据和方法身份冻结，变更后须用新输出。
本包的 full/status/stop/score 接口仍保留，本次交付不自动启动全量。

## 本次调度修正

- 对相同查询、证据和链接上下文，记录实际完成的空导航窗口。完整扫描后只允许一次有边界的重新考虑；仍未选出方向则局部暂停，保留所有观察链接。新证据、父绑定或真实可用材料变化可重新打开探索。
- 普通读取合法完成但仍没有新绑定或纠正时，让长文档阅读与其他观察链接探索交替推进；保留原文、未知项、复查义务和必须恢复的旧窗口。失败的强制复查不能由该调度绕过。

这两项只改变探索调度，不产生答案、缺证结论或事实授权。最终效果由本版真实复测决定。

## 实验约束

初始完整 DAG 在首个网页访问前确定，执行中保持不变。仅从提供的根 URL 和实际观察到的链接遍历；不使用参考答案、黄金路径、全局搜索、reranker 或单独最终阅读器。

两组共用相同的 `deepseek-v4-flash`、部署 tokenizer 和预算：24 次 LLM、6 次 JSON 修复、每请求最多 2 次修复、16384 总上下文、4096 输出、36 次网页动作，并预留最终审计。精确完整请求计数仍是准入条件；原文、来源坐标、反证、失败草稿和未解决义务均保留。

根页面不可访问时，两组按同一题配对排除并报告覆盖率；中间链接错误、模型错误、预算耗尽和容量不足保留为失败。共同可访子集结果不是官方全量准确率。
