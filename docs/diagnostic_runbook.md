# PR1–PR4 同轮诊断运行手册

本轮交付是诊断改造，不是 PR5 主方法重设计。不训练，不引入 dense 保护、Judge 或新选择器。旧集合评分、空集合真实评分、正边际选择和默认搜索策略保留；PR4 只提供初始零优先级根的平局顺序开关。

按用户最终确认，本机只完成代码、离线验收和 PDF；真实模型实验留到服务器执行，不是本轮交付阻断项。服务器上的身份检查和预算约束继续保留。

## 上传服务器后先做什么

推荐上传或更新完整仓库源码，不要复制本机 `.venv`。另行放置两份原始审计包 `chain-audit-full.tgz` / `chain-audit-detail.tgz`，以及同一 revision 的 `questions_32k.csv` / `shared_contexts_32k.jsonl`。已有文件可以复用，不必再次下载；审计包保持原字节和 SHA。

服务器需已有 Python 3.9 或以上及可用的 `venv`。准备好下述配置后，一键脚本会新建或验证独立的 `.venv-diagnostics`，安装 `pip install -e` 的基础依赖，并委派后台管理器启动；不需要复制本机虚拟环境，也不需要为运行实验安装测试依赖。

当前远程 embedding / reranker / generator 配置不需要本机安装模型权重、CUDA 或 `local-models` 依赖。不要把密钥写进可提交配置；生成服务可使用 `BRIDGETREE_CHAT_API_KEY` 环境变量或现有私有凭据配置。

复制 `configs/diagnostic_28.yaml` 为 `configs/diagnostic_28.server.yaml`，在服务器上编辑副本：

- 把两处 `/Users/mao/chain-audit-*.tgz` 改为服务器实际路径。例如审计包放在仓库 `data/audit/` 时，使用 `../data/audit/chain-audit-full.tgz` 和 `../data/audit/chain-audit-detail.tgz`；不改 SHA。
- 检查 `questions`、`contexts`、`deployment_config`。所有相对路径均相对于诊断 YAML 所在目录，而不是执行命令时的目录。
- 从 `diagnostic_deployment.example.yaml` 制作私有部署覆盖文件，填写三个服务的实际 endpoint、必要模型名及真实身份，再设置 `deployment_override` 指向该文件。`identity_source` 应按证据选择；未知量化/tokenizer字段可保留空，不得假填 revision 绕过门禁。
- 部署覆盖文件的顶层是 `models`，不能直接使用旧凭据文件的顶层 `generator` 格式，也不要加入 `base_config`。依赖实验 YAML 自己的 `base_config` 则按那个 YAML 的目录解析。
- 数据或路径、源码、服务配置改完后再 `diagnostic-plan`。不要使用从本机复制的冻结目录执行线上实验，服务器必须建立自己的新 manifest。

配置就绪后，在服务器仓库根目录执行：

```bash
bash scripts/start_diagnostics_linux.sh configs/diagnostic_28.server.yaml
bash scripts/run_diagnostics.sh status
bash scripts/run_diagnostics.sh log
```

第一条默认启动真实在线诊断，不是仅预览：历史分析 → 28 个 fresh-all 评分 → 310 个重复生成 trial → 独立评估 → 12 个根顺序消融 → 汇总。任务不训练、不更新权重。成功提交后台之后可断开 SSH；安装本身仍在前台进行。后台脱离终端不等于主机重启后自动恢复，也不能绕过集群调度器的作业回收规则。

若只验收离线链路，在第一条末尾加 `--offline`。它仍可能联网安装 Python 依赖，但不会调用 embedding/reranker/generator；已有环境可设置 `BRIDGETREE_SKIP_INSTALL=true` 跳过安装。离线完成不代表 28/310/12 个在线项目完成。状态、模块日志、停止、续跑和四分区进度的完整说明见 [后台诊断操作手册](background_diagnostics.md)。

下文保留逐阶段的手动命令，示例使用本机的 `.venv/bin/python` 和 `configs/diagnostic_28.yaml`；服务器请分别替换为 `.venv-diagnostics/bin/python` 和 `configs/diagnostic_28.server.yaml`。不带 `--execute` 的三个逐阶段入口只预览预算，这与默认会在线执行的一键后台入口不同。不要在同一冻结目录同时运行后台流水线和手动执行器。

PDF 已在本机生成，可直接上传。服务器运行实验只需 Python，不依赖 Chrome 或 macOS PDFKit；本机的 PDF 构建脚本与 Swift 图像验收工具不是模型实验运行依赖。

## 独立验收

所有测试默认只用合成数据和假 HTTP。不能把假服务通过当成真实在线实验已完成。

```bash
.venv/bin/python -m pytest tests/test_diagnostic_identity.py tests/test_request_audit.py tests/test_clients.py tests/test_dependency_scoring.py tests/test_config.py tests/test_dependency_experiment.py
.venv/bin/python -m pytest tests/test_dependency_diagnostics.py
.venv/bin/python -m pytest tests/test_diagnostic_runner.py
.venv/bin/python -m pytest tests/test_root_tie_diagnostics.py tests/test_diagnostic_root_runner.py tests/test_dependency_search.py tests/test_dependency_config.py
.venv/bin/python -m pytest
```

PR2 可在尚未接入其他诊断入口时单独运行：

```bash
.venv/bin/python -m bridgetree.dependency_diagnostics /Users/mao/chain-audit-detail.tgz --expected-sha256 c040e839dc5f957596cde0632d739d60769e1ec884092829460bde62c3334c80
```

三个真实案例恢复 28 个子集中的 24 个历史分数；缺口为绘画 `{11,39}` 和音乐 `{5,6,27}`、`{5,8,27}`、`{5,6,8,27}`。读书会四项完整。全 archive 回放与受限格点模拟分开，所有结论带评分及可行性来源；缺分不补零，不将跨界 bundle 截成 B∩U。

## 准备部署与冻结运行

`configs/diagnostic_28.yaml` 是当前真实归档的可执行离线配置。路径可以复制后调整，归档 SHA 不得随意更换。`configs/diagnostic_deployment.example.yaml` 是有意保留未知身份的模板，不是一个已冻结的部署。

在线前由部署操作者确认每个实际服务的 checkpoint / 权重 / deployment revision 至少一种，以及身份来源等级。量化、tokenizer、服务版本未知时明确保留未知。模型 API 名、地址或人工填写“284B INT8”不能冒充服务端验证。把真实部署信息放在私有 override，修改诊断配置的 `deployment_override`，再创建一个新运行；不要改旧 manifest，也不要用旧输出目录重新冻结。

完整输入计划为：三个问题的全部子集含三个独立空集（28 个）；加各题原 dense 上下文（3 个）；每条件 10 次独立客户端请求，共 310 个生成 trial。没有偷偷补造长度对照；可在冻结前用 `cases[].controls` 显式提供来自可见历史的控制集合和理由。新增 3 个长度对照会使生成 trial 成为 340，必须同步增加冻结预算。

默认上限：评分 28 个逻辑输入 / 84 个物理传输尝试；生成 310 个 trial / 930 个物理尝试；根消融 12 次搜索 / 12,000 个物理尝试，根消融不生成答案。根消融每次保留原 ANN=36、搜索和选择各512个逻辑唯一集合增量上限；三例×（legacy+seed 7/19/43）全部报告。物理上限不是保证会消耗的调用量，更不是 token 或账单金额。

以下以独立新目录为例；这组命令不是自动启动后台任务。

```bash
.venv/bin/python -m bridgetree diagnostic-plan --config configs/diagnostic_28.yaml --output-dir outputs/diagnostics/frozen-run
.venv/bin/python -m bridgetree diagnostic-analyze --run-dir outputs/diagnostics/frozen-run
.venv/bin/python -m bridgetree diagnostic-score --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
.venv/bin/python -m bridgetree diagnostic-generate --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
.venv/bin/python -m bridgetree diagnostic-roots --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
```

`plan/analyze/evaluate/report` 无网络。`score/generate/roots` 不带 `--execute` 只展示冻结清单和上限。在线入口会核对源码、服务配置、实际 payload 身份和部署声明；身份未知或漂移时写 gate 失败并在任何模型请求前拒绝执行。只有部署方保证服务未热切换，配置声明才具备实际冻结含义；客户端不能证明服务没有未披露的路由、缓存或量化变化。

## 显式执行与续跑

后台任务通常使用以下命令，不需要手动逐阶段执行：

```bash
bash scripts/run_diagnostics.sh module-log --module scoring
bash scripts/run_diagnostics.sh module-log --module selection
bash scripts/run_diagnostics.sh stop
bash scripts/run_diagnostics.sh resume
```

`log` / `module-log` 是跟随查看，Ctrl+C 只退出查看，不会停止任务。停止须用 `stop`，再用 `status` 确认。`resume` 默认继承上次的在线/离线模式；如果上次是离线且冻结身份已经齐全，可用 `resume --online` 转为线上。若补身份或改模型导致配置发生变化，不能续用旧 manifest，须新建运行。终止失败不会因为 `resume` 获得额外重试，详见下文。

下列为逐阶段手动执行方案，与后台流水线二选一：

```bash
.venv/bin/python -m bridgetree diagnostic-score --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute
.venv/bin/python -m bridgetree diagnostic-analyze --run-dir outputs/diagnostics/frozen-run --score-view fresh
.venv/bin/python -m bridgetree diagnostic-generate --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute --resume
.venv/bin/python -m bridgetree diagnostic-roots --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute --resume
.venv/bin/python -m bridgetree diagnostic-evaluate --run-dir outputs/diagnostics/frozen-run --gold-source data/raw/personamem-v1/questions_32k.csv
.venv/bin/python -m bridgetree diagnostic-report --run-dir outputs/diagnostics/frozen-run
```

续跑始终以同一个预注册 trial_id 为单位，成功和已经终止的失败不会因再次执行命令获得额外样本或重试额度。不同 repeat 始终绕过响应缓存；相同 trial 的已落盘成功、不可重试失败或已耗尽任务次数的失败事件都可以恢复原 outcome，不重复调用或把已知错误改成 InterruptedAttempt。只有可重试且任务额度未耗尽的失败可以继续下一次尝试。崩溃留下的 started 保守消耗一次任务/物理额度；已发请求但响应不明的情况不能计成“服务没执行”。错误答案与解析失败不触发重试。实际物理尝试额度从 durable 请求日志恢复，不能因进程重启清零。

请求前事件持久化、失败、拆批父子关系、原文档 index 和集合身份都在 `requests.jsonl`。默认不输出凭据、私网 endpoint 或记忆原文。评分文档和完整 reader 上下文在本地受控 manifest 中，和脱敏请求 hash 可关联。实际 token 不可获得时为 null，估算 token 不冒充实际 token。

## 输出与解释

- `progress.json`：后台约每 5 秒更新；每个 `score` / `generation` / `root` 阶段有互斥的 `success`、`failed`、`pending`、`unknown` 四个计数，四项之和等于该阶段 `planned`。`started`、`outcome_unknown` 是重叠辅助字段，不加入这四项。
- `run.log`、`runtime.jsonl`：当前阶段、心跳和流水线完成状态；`modules/*.jsonl` 提供 proposal、scoring、activation、state、selection、stop、context、execution 的即时观测。
- `manifest.json`：公开题目、严格可见历史、完整输入、部署身份、调用顺序和预算；无正确答案。
- `offline_analysis.json`：历史分数来源、24/28 缺口、真实 bundle 可达性与预算感知历史回放。
- `score/*.json`、`fresh_analysis.json`：本会话完整新评分或失败；不混入24个旧分。局部最高 R 不称全库最优。
- `generation/*.json`：每个预注册重复的原始输出或失败；`attempts.jsonl` 保存全部尝试。
- `root/*.json`、`root_summary.json`：每个预声明 seed 的完整/部分搜索、选择和 trace，最终集合差异；无答案生成。
- `evaluation.json`：独立评价、固定 trial 分母、成功输出分母、解析失败、答案分布与原选择的分块配对。
- `diagnostic_report.json`：统一汇总，包括未执行和 gate 阻断项；不是只统计成功样本。

后台管理器外层 `state=completed` 只代表进程成功结束；还要查看内层 `completion.status` 是否为 `completed_with_failures` 或 `offline_complete`。HTTP 失败是执行失败，不是答错；只有独立评估的成功生成才有答题正确性。进度快照中的缓存和根搜索指标是观测摘要，不是所有失败重试的完整账单，完整传输成本仍以 `requests.jsonl` 为准。

三例为事后选出的机制诊断案例，不是正式测试集；技术重复不是新的独立问题。新证据是否帮助回答、R是否错位、archive是否可构造、严格正路径是否存在和greedy是否找到分别报告。根 tie-only 消融仅测无语义次序敏感性，不保证根覆盖，也不实现轮询或根预算。

## 下一步机制方向（尚未实现）

优先审视相关性、条件证据贡献和停止依据是否应分离。如果补历史稳定改善回答却降低R，应改目标；如果高R且更有用的可行组合没找到，再研究联合添加、有限回退或替换；若关键事实在可见库却没被召回，再研究跨目标覆盖。不能把新Judge随意输出的分数直接当cardinal utility，也不能用logit修复固定archive下的选择排序。PR5须依据诊断另行定义和批准。
