# WebWalkerQA + BrowseComp-Plus v4 实验包

修订 3 使用独立的新目标目录，保留修订 1 和修订 2 部署。
同一个包包含 WebWalkerQA 全部 680 题、BrowseComp-Plus 全部 830 题及其固定检索语料。
两数据集均运行 `dagbt_joint_memory_v1`、`dagbt_residual_memory_v2` 两组。
这里的“训练”沿用现有实验流程：调用模型执行算法并评测，不更新模型权重。
公共核心仍与 `e6677081cdfb33c01db3aaa274a497168f314f78` 的 107 个 Python 文件一致。

## 上传后启动

上传 `dagbt_benchmarks_v4_experiment.tar.gz` 和同名 `.sha256` 文件到服务器 `~/bt/`。
服务器沿用之前可用的 Python 环境与 PersonaMem v4 来源部署；来源实验须已完成或正常停止。
不要同时运行旧的 WebWalker full 与本包。

```bash
cd ~/bt
sha256sum -c dagbt_benchmarks_v4_experiment.tar.gz.sha256
mkdir -p ~/dagbt_patches/dual_benchmark_v4_v3
tar -xzf dagbt_benchmarks_v4_experiment.tar.gz -C ~/dagbt_patches/dual_benchmark_v4_v3
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
bash ~/dagbt_patches/dual_benchmark_v4_v3/dagbt_benchmarks_v4_experiment/install_and_run.sh
```

最后一条命令完成独立安装、浏览器依赖检查、两个数据集的离线及真实服务预检，
随后在后台顺序运行两个数据集。SSH 断开后继续执行。
离线检查会分别通过本地 HTTP 夹具执行两数据集的完整算法链路；真实模型测试单独记录。
默认新目标是 `~/dagbt_runs/20261016_dual_benchmark_v4_v3/dagv2`；
不覆盖原 PersonaMem/WebWalker 部署，不带旧输出或任务缓存。
包内不含私人凭据，安装器仅在服务器本地从来源部署复用凭据，权限为 0600。
所有 payload 和 PDF wheel 均校验 SHA256；大语料使用流式校验、复制。

若需先跑少量真实测试，将最后一条命令的入口换为 `install_and_smoke.sh`。
它在前台执行每数据集前 2 题 × 2 组，共 8 个任务；不要求答案全部正确，
重点核对生成正常终态、计费、引用核验、日志及独立评分流程。
本机验证结果与平台限制以包内 `validation.json` 为准；不把本机结果称作 Linux 全量结果。

## 日志、状态、停止与恢复

```bash
cd ~/dagbt_runs/20261016_dual_benchmark_v4_v3/dagv2
bash scripts/run_benchmarks.sh status
tail -f outputs/benchmarks_v4_full/launcher.log
bash scripts/run_benchmarks.sh stop
```

套件根目录保留 `launcher.log`、`progress.json`、`manifest.json`、`pid.json` 和 OS writer 锁。
`webwalkerqa/`、`browsecomp_plus/` 子目录各自保留原有布局：

- `progress.json`：任务数、失败数和当前阶段。
- `tasks/<题>/<组>/worker.log`、`result.json`：单任务日志与终态。
- 每任务请求、`fusion_events.jsonl`、`call_events.jsonl`、分词和检索日志：实际调用、成本与完整证据明细。
- `generation_summary.json`：全部任务的调用次数、token、耗时及缺失成本统计。
- `evaluation.json`：生成全部终态后的独立答案评分。

顺序固定为 WebWalkerQA 生成 → BrowseComp-Plus 生成 → WebWalkerQA 评分 → BrowseComp-Plus 评分。
任一阶段异常退出会停止后续阶段。正常预算耗尽或未解题保留为任务结果，不阻断其他题。
停止命令验证真实锁和 PID 身份，通知协调器清理当前 runner/worker，禁止自动继续评分或下一数据集。
停止后通过同一条 `bash scripts/run_benchmarks.sh full` 恢复；已终态任务复用，
已经开始但未正常发布终态的付费任务保留为失败，不自动免费重试。
修改过代码、配置或数据时应使用全新输出目录，不能在旧目录换实现重跑。

```bash
bash scripts/run_benchmarks.sh full
```

若运行 smoke，查看或恢复时也使用同一个目录：

```bash
BENCHMARKS_OUTPUT=outputs/benchmarks_v4_smoke bash scripts/run_benchmarks.sh status
BENCHMARKS_OUTPUT=outputs/benchmarks_v4_smoke bash scripts/run_benchmarks.sh stop
```

恢复 smoke 时再次执行 `bash scripts/run_benchmarks.sh smoke`，并保持相同的
`BENCHMARKS_OUTPUT` 和配置。不要换成 `full`；两者的题目范围不同。

## 可选路径与单数据集接口

`install_and_run.sh /新的/目标/dagv2` 可指定独立安装目标；
`DAGBT_PERSONAMEM_BASE` 指定 PersonaMem v4 来源目录。
`PERSONAMEM_OUTPUT` 指定已完成或正常停止的 PersonaMem 输出目录。
`BENCHMARKS_OUTPUT` 指定两个数据集共用的套件根输出目录。
`DAGBT_WEBWALKER_CONFIG`、`DAGBT_BROWSECOMP_CONFIG` 及相应 `_JUDGE_CONFIG` 指定配置；
`WEBWALKER_DATA`、`BROWSECOMP_DATA` 指定已经完整准备的数据目录。
所有变量应在安装/启动前 `export`，恢复时保持一致。

原 `bash scripts/run_webwalker.sh {offline|preflight|smoke|full|status|stop|score}` 接口保留。
新增 `bash scripts/run_browsecomp_plus.sh {offline|preflight|smoke|full|status|stop|score}`，
独立输出由 `BROWSECOMP_OUTPUT` 指定。
单独 BrowseComp-Plus `full` 只在后台生成，终态后显式执行 `score`；
双数据集套件 `full` 则在两边生成全部终态后自动评分。
同一实验使用套件入口即可，不要另外启动其子数据集。

## 数据与算法边界

WebWalkerQA 延续从给定根页面及实际观察链接遍历的协议，保留上一轮修复的链接上下文、
公平探索、独立原文核验及有界修复；根页面不可访问仍按两组配对排除并报告覆盖率。
BrowseComp-Plus 从随包固定语料进行 SQLite FTS 检索，运行时不需要外部搜索服务、
embedding 服务或额外 Python 检索依赖，不依赖当前网络页面是否变化。
原始题目答案、gold/evidence 文档标注及困难负例身份不进入模型生成输入，
仅独立评分阶段加载参考答案。
两组共用相同模型、精确分词和预算，保留初始 DAG、证据来源、反证、失败草稿及未解决义务。

浏览器首次安装需要服务器访问 PyPI 和 Chromium CDN。
可沿用之前同服务器完整的 `_webwalker_browser_vendor`、`_webwalker_browsers` 两个目录，
不要复制旧输出/网页缓存。系统动态库仍按之前部署要求准备；安装器不运行 sudo。
第二个安装参数 `--no-browser` 可跳过浏览器安装，前提是目标中已有完整可运行的依赖。
