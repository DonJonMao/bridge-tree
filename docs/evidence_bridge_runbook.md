# Evidence BridgeTree：Linux 实验、日志与续跑文档

版本：v3 / 2026-09-30，配套 [代码修改设计](evidence_bridge_implementation.md)。当前方法使用冻结 embedding、reranker 和聊天模型，**不更新权重、不运行优化器**。本文件中的“一键运行实验”是完整 PersonaMem-32k 的检索、证据推理、reader 推理和评测；Linux 启动脚本默认拒绝在非 Linux 系统启动整套实验。

## 从 v2 切换到 v3

保留旧项目和日志，不删除旧文件夹，也不把新源码覆盖进正在运行的目录。v3 默认独立使用 `outputs/background-evidence-bridge-v3` 与 `outputs/evidence-bridge-v3`，缓存为 `outputs/cache-evidence-bridge-v3`；即使同一 checkout 更新，也不会读取 v1/v2 的默认 run 指针。源码、协议和预算参与已有冻结运行身份，v3 必须新建 run，不能 resume v2。

服务器先在旧项目目录停止 v2，并确认状态为 `interrupted` 或已终止，再到新目录启动：

```bash
cd /home/sn_maozhifang/bt/bridge-tree-evidence-v2-20260927 && BACKGROUND_STATE_DIR="$PWD/outputs/background-evidence-bridge-v2" bash scripts/run_evidence_bridge.sh stop && BACKGROUND_STATE_DIR="$PWD/outputs/background-evidence-bridge-v2" bash scripts/run_evidence_bridge.sh status
```

如果状态还是 `running`，等待并再次执行 `status`；`stop_requested` 只是信号已发出。新目录可复制旧目录的 `configs/credentials.local.yaml`（如存在）或重新导出环境密钥，不要复制 `.venv` 与 `outputs`。如之前显式设置过 `BACKGROUND_STATE_DIR` / `OUTPUT_DIR`，切换目录后先 `unset BACKGROUND_STATE_DIR OUTPUT_DIR`，避免覆盖默认隔离设置。这里仅给出操作命令，不代表已在服务器停止旧实验。

## 1. 交付包和服务器条件

在项目根目录执行：

```bash
bash scripts/package_evidence_bridge.sh
```

得到 `dist/evidence-bridge-v3-server/bridge-tree-evidence-v3.tar.gz`、同名 `.sha256` 和 `package_manifest.json`。脚本要求机制背景 PDF、设计文档、运行文档及正式配置均存在，缺一项即失败，不产生“没有文档的完整交付”。v1/v2 已分发压缩包保持原样，新文件名和 dist 目录不会覆盖它。包内包含源码、测试、脚本、配置、固定 revision 的 32k 原始与 processed 数据，以及 `output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf`。PDF 保留 v1 机制背景；v3 的需求规划、原文独立复核与覆盖未评估处理，以当前实现契约和 [v3 方案](evidence_bridge_v3_plan.md) 为准，不能用旧 PDF 的禁止截断或映射准入条款解释 v3。包中不含 `.venv`、本机凭据、`.local.` 配置、软链接、缓存或任何旧 `outputs/`。**不能把本机 `.venv` 搬到 Linux 使用。**

Linux 要求 Python >= 3.9、bash、可用的 venv/pip、足够写入完整日志的磁盘，且能访问三个推理服务。纯远程模式仅安装 numpy 和 PyYAML，无本地模型下载、CUDA/NPU 依赖。实际内存与磁盘用量取决于请求日志及原文长度；此前完整原文日志已达 GB 级，应持续查看磁盘剩余空间。三个 API 继续使用项目现有协议：embedding、pointwise reranker、OpenAI-compatible chat completions。证据模块和最终 reader 共用冻结 chat 部署，但调用、预算、日志分别记录。

上传、校验、解包：

```bash
cd ~/bt && sha256sum -c bridge-tree-evidence-v3.tar.gz.sha256 && mkdir bridge-tree-evidence-v3-20260930 && tar -xzf bridge-tree-evidence-v3.tar.gz -C bridge-tree-evidence-v3-20260930 && cd bridge-tree-evidence-v3-20260930
```

校验文件和压缩包须放在同一目录。命令中的 mkdir 在目标目录已存在时会停止，避免把新源码覆盖到旧运行目录；这时改用另一个新目录名，不删除已有实验。解包后的项目根目录包含 `pyproject.toml`。

## 2. 服务配置和一键后台启动

默认 `configs/evidence_bridge.yaml` 继承现有修复后服务设置，开启 `dense, activation, evidence_bridge` 三种方法。共有 589 题，默认 1767 个任务。`activation` 用于旧方法对照，新方法不会因为证据选择失败而悄悄退回它。v3 默认开启 `raw_memory_review` 与 `allow_unassessed_coverage`：dense 预算可行的原始记忆具有独立复核和选入资格，不再必须先被 mapper 接纳；它们不被强制全部选入。结构与预算合法的选集可以在覆盖字段修复耗尽后保留，但未能验证的覆盖必须如实记为未评估，不能冒充 `covered`。

服务器地址/模型与本机不同时，新建私有 `configs/server.local.yaml`，仅写要覆盖的字段，例如：

```yaml
models:
  embedding:
    endpoint: http://YOUR_EMBEDDING_HOST/v1/embeddings
    model: YOUR_EMBEDDING_MODEL
  reranker:
    endpoint: http://YOUR_RERANKER_HOST/rerank
    model: YOUR_RERANKER_MODEL
  generator:
    endpoint: http://YOUR_CHAT_HOST/v1/chat/completions
    model: YOUR_CHAT_MODEL
    api_key: ""
    api_key_env: BRIDGETREE_CHAT_API_KEY
```

如更换了部署，同步在 `models.<name>.deployment_identity` 中记录真实已知身份；未知字段保留未知，不沿用已失效的修复服务标记。override 不可再声明 `base_config`。凭据在服务器注入，例如：

```bash
read -r -s -p "Chat API key: " BRIDGETREE_CHAT_API_KEY; export BRIDGETREE_CHAT_API_KEY
export BRIDGETREE_DEPLOYMENT_CONFIG="$PWD/configs/server.local.yaml"
unset BACKGROUND_STATE_DIR OUTPUT_DIR; bash scripts/start_evidence_bridge_linux.sh
```

服务不需要密钥时不必设置 `BRIDGETREE_CHAT_API_KEY`。沿用默认地址时不必设置 deployment override。第一次启动会创建本地 `.venv`、安装依赖、执行**不调用模型**的数据预检，再执行一次 evidence 规划协议服务探测；通过后启动独立后台 monitor 和 worker。探测使用固定的非私有问题、当前配置的输出协议和当前部署，不在 plain/json_object/json_schema 间静默切换；失败则不提交实验。它产生一次额外逻辑模型调用（底层 HTTP 可重试），属于部署预检，不计入实验任务成本。仅证明规划协议的烟雾检查通过，不证明所有真实任务都可靠。数据预检核查固定数据 revision、589 题、非 synthetic、方法表和任务数；随后正式 worker 才检查服务并运行。返回 `Detached inference submitted` 只代表后台提交成功；以 `status` 与实际日志确认服务检查和任务执行。

关闭 SSH 不会终止已 detached 的实验。无需再加 `nohup` 或 `&`。完整过程：

```bash
bash scripts/run_evidence_bridge.sh status
bash scripts/run_evidence_bridge.sh log
bash scripts/run_evidence_bridge.sh module-log scheduler
bash scripts/run_evidence_bridge.sh module-log evidence
bash scripts/run_evidence_bridge.sh module-log effectiveness-current
bash scripts/run_evidence_bridge.sh summary
bash scripts/run_evidence_bridge.sh export
```

`log` / `module-log` 的 Ctrl+C 只退出 tail，不停止实验。重复 `start` 在已有 live monitor 时返回 `already_running`，不会同时启动第二份任务。

可选环境变量：

| 变量 | 默认与用途 |
|---|---|
| `BRIDGETREE_SETUP_PYTHON` | `python3`；用于创建 venv |
| `BRIDGETREE_VENV_DIR` | 项目 `.venv`；Linux 本地环境目录 |
| `BRIDGETREE_SKIP_INSTALL` | `false`；已安装依赖时可设 `true` |
| `BRIDGETREE_BASE_PYTHON` | 管理脚本默认 `.venv/bin/python`；自定义 venv 管理时传其 Python |
| `BRIDGETREE_DEPLOYMENT_CONFIG` | 首次启动使用的私有覆盖配置路径 |
| `BACKGROUND_STATE_DIR` | `outputs/background-evidence-bridge-v3` |
| `OUTPUT_DIR` | `outputs/evidence-bridge-v3`，每次 start 新建子目录 |

使用自定义 state 目录/venv 时，后续 status/stop/resume 必须继续传相同变量。方法参数修改应写一份新的 YAML，使用 `bash scripts/start_evidence_bridge_linux.sh configs/your_method.yaml`。不要修改正在运行的 YAML 或源码。

## 3. 停止、续跑和终态

```bash
bash scripts/run_evidence_bridge.sh stop
bash scripts/run_evidence_bridge.sh status
bash scripts/run_evidence_bridge.sh resume
```

`stop` 给 monitor 发 SIGTERM，monitor 转发给 worker，由实验器保存已完成任务和部分诊断。等待 status 变为 `interrupted` 后 resume。stop 返回 `stop_requested` 不代表进程已结束，不能立即杀进程并假设日志都已写完。

resume 使用原 `exact-run-dir`、原配置路径、原 deployment override 路径。此时当前 shell 的新 `BRIDGETREE_DEPLOYMENT_CONFIG` 不会替换原参数；代码、数据、方法配置和部署身份仍须与冻结 run identity 相符。成功任务跳过，失败和待处理任务重跑。任务内搜索不是 frontier 级精确断点恢复：被中断的任务从头执行，之前部分证据作为诊断保留。改算法、配置或模型应启动一个新 run，不能借 resume 把两种方法混在一起。

monitor 状态 `completed` 表示 worker 正常退出；**仍要查看运行目录 `completion.json` / `summary.json`** 区分 `completed` 与 `completed_with_failures`，不能把进程 exit 0 当全任务成功。错误原因在 `failures.jsonl`、outcomes 和模块 requests 中。实验器已有基础设施重试，超过有限次数后记录失败并继续；resume 可以继续失败任务。选集 ID、可见来源与 reader 预算仍是硬约束。v3 的覆盖未评估继续执行属于明确记录的方法分支；它不是答案正确或证据充分的保证，也不是伪造合法 coverage。

## 4. 日志目录与权威来源

固定管理目录 `outputs/background-evidence-bridge-v3/`：

| 文件 | 用途 |
|---|---|
| `evidence_bridge.status.json` | monitor 当前 PID、状态、run_dir、退出信息 |
| `evidence_bridge.log` | stdout/stderr、heartbeat、后台结果 |
| `evidence_bridge.spec.json` | 原启动参数，resume 从此恢复 |
| `evidence_protocol_probe.json` | 最近一次启动前协议服务探测结果，不含原始密钥或响应全文 |
| `evidence_bridge.run_dir` | 当前实际运行目录，只有一行绝对路径 |
| `history/` | 重新启动/恢复前的管理状态与主日志 |

每个 `outputs/evidence-bridge-v3/start_<日期>_<PID>/`：

| 文件/目录 | 用途与判读 |
|---|---|
| `run_manifest.json`, `resolved_config.json` | 数据/配置/源码/部署/提示 identity，冻结新方法配置 |
| `planned_tasks.jsonl` | 所有任务及题目、方法身份；待处理分母来源 |
| `outcomes/<task_id>.json` | **每个任务当前权威结果**，含 attempt、成功/失败、答案、selected_ids、costs、diagnostics |
| `summary.json`, `progress.json`, `metrics.csv`, `completion.json` | 全体/分方法评测、进度、终态 |
| `train.log` | train-free 状态、进度和周期性方法指标文本；实际模块反应读 JSONL |
| `candidate_pool/<task_id>.json` | initial/conditional 候选、完整 search archive、证据需求/映射/整体选择与修订；新证据表在 `evidence_selection` |
| `evidence_live/<task_id>.json` | 每个证据关键事件更新的完整实时快照，保留原始模型请求/响应、需求、映射和修订；任务未结束即可检查 |
| `visible_memories/` | 当前 cutoff 内原文记忆身份；不能跨题误用其全历史 |
| `modules/*.jsonl` | 各模块追加事件，包含 task/method/attempt；失败前事件仍保留 |
| `modules/effectiveness.current.jsonl` | 每个当前 outcome 一行的 retry-safe 模块表现视图 |
| `predictions.jsonl`, `failures.jsonl`, `events.jsonl` | 历次尝试和运行事件历史；不能直接按行数计算准确率 |
| `mechanism_summary.json`, `mechanism_summary.md` | `summary` 命令重建的最新方法/机制/成本汇总 |

完整日志可能含用户原始记忆、query 和模型原始输出，用于论文分析时按研究数据规范保管。凭据、Authorization 和私有 endpoint 不应进入模块日志。

## 5. 三个方向分别看什么

所有事件均通过 task ID、method ID 和 attempt 关联。`record_kind=live` 是执行中实时事件，`record_kind=task_snapshot` 是任务结束/失败后的完整事件重放；两者可能描述同一动作，不可直接相加。实时完整文本查 `evidence_live/<task_id>.json`，权威结案查 outcome 和 candidate_pool。数值不替代语义判断，特别是 R 仍是 `legacy_query_relevance`，不是已校准效用。

| 模块 | 查看命令的 module 名 | 需要检查的关键反应 |
|---|---|---|
| 需求规划 | `planner` | query-only 的个性化依据、过去状态/原因与偏好；不要把规划为外部知识、地点/日期细节误当个人记忆需求；原始输出在任务 artifact |
| 多目标调度 | `scheduler` | phase（coverage/deepen/explore）、目标、量子开始/结束、ANN/集合前后预算、游标、暂停与切换原因；根覆盖和单目标份额是否变化 |
| 目标约束/转向 | `target`, `activation` | 四项 R、A、M_before/M_after/M_group；retain/speculate/reject；pivot 是否确实删除旧 e、新根来自哪里、有无去重；汇总 pivot_count 只计 queued，尝试和拒绝分开 |
| 检索提案 | `proposal` | 原 query/桥接/条件/缺口查询各次 ANN、返回 IDs、池外发现、重复和额度耗尽 |
| 全集评分与归档 | `scoring`, `state`, `archive` | 已完成集合及预算；archive 保存完整 P/Pe/PG/PGe；未完整测量不得生成 A |
| 原文证据映射 | `evidence` | 原文 source span 暴露、模型引用 span ID、代码回取原文及 offset/role 校验、support/partial/contradiction、explicit/inference；不能只看有效证据条数忽略未映射候选 |
| 整体选择 | `selection` | 映射证据与独立提供的 dense 原文、各自可见/保留/丢弃 ID；每轮 added/removed IDs、覆盖或未评估状态、预算修订；原文复核资格不等于最终必选 |
| 缺口检索 | `feedback` | 哪项需求缺失、targeted query、ANN 计费、返回新/旧 ID、是否重映射、无新证据或预算耗尽终态 |
| 最终输入与答案 | `context`, `effectiveness-current` | 最终原始 Memory、ContextPlan、请求 hash、答案解析/正误；old/new 方法相同 payload 也可能得到不同输出 |
| 成本与失败 | `cost`, `requests`, `stop` | 逻辑 ANN/集合/证据 LLM 调用 vs 物理 HTTP 重试、缓存命中、预算耗尽、typed error；token estimate 不冒充 tokenizer 真值 |

证据阶段默认最多 24 次 LLM 调用，包括规划、全文映射、整体选择、局部修复及有限反馈/预算修订；每个逻辑请求最多 2 次修复、整题最多 6 次，均计入总调用额度，最终 reader 调用另计。选择阶段可在预算内按完整记录裁剪 ledger；有效但部分映射的候选可进入选择。未评估部分保持 unavailable，不能当无关；被裁掉的证据不能引用。如果选集本身（ID、可见性、reader 预算）不合法仍记失败。覆盖判断修复耗尽时，可在已验证的选集上将失败行保留为内部未评估状态；不能构造假的支持关系，不自动回退其他方法。

证据选择 artifact 中的具体字段如下，查原始记录时使用实际字段名，不通过文字描述猜测：

| 字段位置 | 字段 |
|---|---|
| `evidence_selection.costs` | `evidence_llm_calls`, `evidence_json_repairs`, `evidence_input_tokens_estimate`, `evidence_output_tokens_estimate`, `evidence_llm_elapsed_ms`, `evidence_elapsed_ms`, `evidence_calls_by_operation`, `token_count_is_estimate` |
| `evidence_selection.diagnostics` | `evidence_candidates`, `evidence_mapped_candidates`, `evidence_unmapped_candidates`, `evidence_units`, `evidence_verified_mappings`, `evidence_requirements` |
| 覆盖与修订诊断 | `evidence_covered_requirements`, `evidence_partial_requirements`, `evidence_missing_requirements`, `evidence_ambiguous_requirements`, `evidence_validation_failures`, `evidence_selection_revisions`, `evidence_feedback_rounds`, `evidence_selected_count` |
| `evidence_selection.coverage[]` | `requirement_id`, `status`, `evidence_ids`, `kind`, `explanation`, `supporting_ids` |
| 完成类型 | `reliability_status` 为 `normal` / `truncated` / `partially_mapped` / `truncated_and_partially_mapped` / `coverage_unassessed`；另记 `selection_input_truncated`, `partially_mapped`, `unavailable_unit_count` |
| v3 覆盖状态 | `coverage_validation_complete`, `unassessed_requirement_count`；`unassessed` 不冒充已判断的 `missing` 或 `covered` |
| v3 原文复核与选集 | `baseline_ids`, `raw_review_ids`, `candidate_dispositions`；诊断有 `evidence_baseline_count`, `evidence_baseline_selected_count`, `evidence_raw_review_count`, `evidence_raw_selected_count`, `evidence_empty_context`, `evidence_state` |
| 完整任务级记录 | `requests`（messages/raw_response/validation）, `exposures`, `selection_rounds`, `mappings` |

`evidence_unmapped_candidates > 0` 表示未完整映射，可同时存在有效的部分证据，应结合任务状态与 `partially_mapped` 分析；`evidence_validation_failures` 包括可修复的非法输出，不能只看终态成功就认为模型每次响应都合规。mapper 判无关的原始理由在 `requests` 中 `evidence_map` / `evidence_map_repair` 对应 `raw_response` JSON 的 `units[].irrelevance_reason`；按 `unit_id` 联结 `exposures[].memory_id`，不要把曝光完成状态误读成语义相关。

## 6. 汇总和定位一条错误

```bash
bash scripts/run_evidence_bridge.sh summary
# 或指定一个旧目录，不改变当前 run
.venv/bin/python scripts/summarize_evidence_bridge.py outputs/evidence-bridge-v3/start_YYYYMMDD_HHMMSS_PID
```

汇总读取冻结计划及 `outcomes/`，不累加 append-only 重试事件。`diagnostics.evidence_bridge_summary` 的每个数值指标输出 `observed_tasks/missing_tasks/sum/mean/min/max`，cost 同样单列；缺字段不会当 0。旧 dense/activation 没有新方法 summary 是预期缺失。schema/任务身份错误列入 `invalid_outcome_files`，命令返回非零。运行中生成的汇总不是跨文件事务快照，应在完成后重新执行一次。

标准 `summary.json` 的 evidence_bridge 方法行和 `mechanism_summary.json` 均包含 `evidence_reliability.completion_cohorts`：分别统计五种完成类型及 `unknown` 的题数、答对数、准确率与成本。旧日志没有版本诊断时记 `unknown`，不冒充正常完成；失败题成本独列 `failure_cost_metrics`。各组题目不相同，不能据此直接声称方法更有效。`normal` 仅描述映射处理/选择输入是否完整，不能证明需求正确、关键历史被保留或覆盖语义正确；空映射、空上下文与覆盖未评估必须结合新增语义诊断分别检查。

v3 同一 `evidence_reliability` 对象还包含两组独立统计，每组都有 `tasks/correct/accuracy/cost_metrics`：

- `evidence_state_cohorts`：`empty` / `mapped_only` / `raw_only` / `mixed` / `unknown`，分别表示没有原文、只含有映射的记忆、只含独立原文、两者都有、历史日志未记录。
- `coverage_validation_cohorts`：`complete` / `unassessed` / `unknown`。`complete` 只说明覆盖行通过引用协议校验，不保证语义真值；原文 `raw_only` 可以保留 `missing` 覆盖并正常交给 reader。

任务级 `diagnostics.evidence_bridge_summary.selection` 有 `baseline_count`, `baseline_selected_count`, `baseline_retention_rate`, `raw_review_count`, `raw_selected_count`, `raw_review_ids`, `evidence_state`, `candidate_disposition_counts`。它们帮助判断模型是否使用独立原文、是否仍在删去 dense 历史。v3 顶层 `costs.evidence_calls` 与 `costs.evidence_reasoning.evidence_llm_calls` 应一致；旧 v2 顶层可能为 0，分析旧日志应使用嵌套的真实 evidence 计数，不能据此声称没有额外调用。

新摘要同时保留 selector.diagnostics，例如全文映射完成数、校验失败、集合修订和反馈轮次。removed_memories 只计实际接受的整体集合变更，不能把 proposed 与 accepted 重复累加或把预算拒绝当成已经删除。

定位错误按以下顺序：

1. 在 `outcomes` 找 `status=success && correct=false` 的题，记录 task ID、question ID、attempt、selected_ids 和 context_hash；失败任务单独查 error_type，不混进检索机制错误。
2. 查 `candidate_pool/<task_id>.json` 中 `search`：目标有没有机会展开，暂停是否有剩余游标，预算在哪一阶段耗尽，候选是否真的召回/完整归档。
3. 查 `evidence_selection`：需求是否适合个性化回答；相关历史被 mapper 判无关的原始理由是什么；它是否通过原文独立复核仍能被选择；引用的角色/历史阶段是否正确；丢失发生在映射、原文复核、最终选择还是 reader 预算修订。覆盖未评估与已验证覆盖分开统计。
4. 对照 `feedback`，确认缺失需求是否触发预算内真实 ANN，新候选是否进入映射和新集合。
5. 对照最终 ContextPlan 和实际 reader request，确认选出的原文确实进入模型。若相同 payload 的答案不同，标明 reader 波动，避免把变化全归因于搜索。模型自报 `covered` 只表示经引用校验的覆盖判断，不等于 gold evidence recall 或真实答案贡献。

当前进度用一行命令查看：

```bash
python3 -c 'import json; from pathlib import Path; r=Path(Path("outputs/background-evidence-bridge-v3/evidence_bridge.run_dir").read_text().strip()); print((r/"progress.json").read_text())'
```

导出当前运行的全部方法分析日志：

```bash
bash scripts/run_evidence_bridge.sh export
```

默认写到 `outputs/exports/evidence_logs_<run>_<时间>_<PID>.tar.gz` 和同名 `.sha256`。包含权威 outcomes、完整候选/证据原始请求响应、实时快照、模块日志、已脱敏配置及冻结任务计划；不包含项目私有配置、环境变量、旧实验目录或软链接。`export_manifest.json` 记录每个成员的实际字节数和 SHA256。原始记忆和模型文本用于分析，仍应按实验数据管理。可以在运行期间导出；这不是跨文件事务快照，正在追加的 JSONL 末行可能不完整。最终分析应在停止或完成后再次导出。

也能导出已停止的 v2 运行，供逐题检查本轮语义损失（此路径对应此前用户提供的运行）：

```bash
.venv/bin/python scripts/export_evidence_bridge_logs.py /home/sn_maozhifang/bt/bridge-tree-evidence-v2-20260927/outputs/evidence-bridge-v2/start_20260927_034132_625737
```


## 7. 本地验收与真实服务器评测的边界

本项目提供 `tests/test_evidence_bridge_operations.py`，实际启动 detached monitor＋临时 fake worker，检查 start/status/重复start/stop/resume、冻结部署参数、路径含空格、package内容和retry-safe汇总。它不调用用户服务，不声称新方法准确率已提升。

```bash
.venv/bin/python -m pytest tests/test_evidence_bridge_operations.py -q
```

方法层语义/边界测试与端到端本地模拟见 [v3 验证记录](evidence_bridge_v3_validation.md)。真实开发题离线回放不证明提示词在新模型调用中会生成正确语义判断；启动前茶叶问题协议探测也不覆盖这些语义问题。打包后服务器首次完整结果才是新版真实运行数据；保留日志、配置 identity 和包 SHA 后，再据此判断预算覆盖、目标转向、证据保存是否带来改善。


## 8. 不调用模型的旧日志回放

对解包后含 `outcomes/`、`candidate_pool/`、`visible_memories/`、`modules/context.jsonl` 的旧运行目录，可执行一行：

```bash
PYTHONPATH=src .venv/bin/python scripts/replay_evidence_v3.py --run-dir /path/to/export/run --output-dir outputs/evidence-v3-offline-replay
```

输出目录必须是新的，且位于被审计 run 之外。工具从同题 dense 实际 reader 请求恢复预算可行原文，冻结旧需求/映射重建 v3 选择 payload，检查原文与角色是否可见、输入是否在预算内；对旧错误的原始 select 响应重验引用与保守 kind 归一化，并检查紧凑 repair 输入。只输出任务/题号、日志路径、hash、ID 与计数，不复制完整记忆、模型原始文本或凭据。它不生成任何新答案；可见性改善、旧响应变为合法或 repair 放得下均不等于 v3 准确率提高或真实任务已被修复。
