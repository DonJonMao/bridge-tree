# Evidence BridgeTree：Linux 实验、日志与续跑文档

版本：2026-09-23，配套 [代码修改设计](evidence_bridge_implementation.md)。当前方法使用冻结 embedding、reranker 和聊天模型，**不更新权重、不运行优化器**。本文件中的“一键运行实验”是完整 PersonaMem-32k 的检索、证据推理、reader 推理和评测；不会在本机提前调用用户模型服务。

## 1. 交付包和服务器条件

在项目根目录执行：

```bash
bash scripts/package_evidence_bridge.sh
```

得到 `dist/evidence-bridge-server/bridge-tree-evidence.tar.gz`、同名 `.sha256` 和 `package_manifest.json`。脚本要求新 PDF、设计文档、运行文档及正式配置均存在，缺一项即失败，不产生“没有文档的完整交付”。包内包含源码、测试、脚本、配置、固定 revision 的 32k 原始与 processed 数据，以及 `output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf`。包中不含 `.venv`、本机凭据、`.local.` 配置、软链接、缓存或任何旧 `outputs/`。**不能把本机 `.venv` 搬到 Linux 使用。**

Linux 要求 Python >= 3.9、bash、可用的 venv/pip、足够写入完整日志的磁盘，且能访问三个推理服务。纯远程模式仅安装 numpy 和 PyYAML，无本地模型下载、CUDA/NPU 依赖。实际内存与磁盘用量取决于请求日志及原文长度；此前完整原文日志已达 GB 级，应持续查看磁盘剩余空间。三个 API 继续使用项目现有协议：embedding、pointwise reranker、OpenAI-compatible chat completions。证据模块和最终 reader 共用冻结 chat 部署，但调用、预算、日志分别记录。

上传、校验、解包：

```bash
cd /path/to/archive-directory
sha256sum -c bridge-tree-evidence.tar.gz.sha256
mkdir -p ~/bridge-tree-evidence
tar -xzf bridge-tree-evidence.tar.gz -C ~/bridge-tree-evidence
cd ~/bridge-tree-evidence
```

校验文件和压缩包须放在同一目录。解包后的项目根目录包含 `pyproject.toml`。

## 2. 服务配置和一键后台启动

默认 `configs/evidence_bridge.yaml` 继承现有修复后服务设置，开启 `dense, activation, evidence_bridge` 三种方法。共有 589 题，默认 1767 个任务。`activation` 用于旧方法对照，新方法不会因为证据选择失败而悄悄退回它。

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
read -r -s -p "Chat API key: " BRIDGETREE_CHAT_API_KEY
export BRIDGETREE_CHAT_API_KEY
export BRIDGETREE_DEPLOYMENT_CONFIG="$PWD/configs/server.local.yaml"
bash scripts/start_evidence_bridge_linux.sh
```

服务不需要密钥时不必设置 `BRIDGETREE_CHAT_API_KEY`。沿用默认地址时不必设置 deployment override。第一次启动会创建本地 `.venv`、安装依赖、执行**不调用模型**的数据预检，然后启动独立后台 monitor 和 worker。数据预检核查固定数据 revision、589 题、非 synthetic、方法表和任务数；随后正式 worker 才检查服务并运行。返回 `Detached inference submitted` 只代表后台提交成功；以 `status` 与实际日志确认服务检查和任务执行。

关闭 SSH 不会终止已 detached 的实验。无需再加 `nohup` 或 `&`。完整过程：

```bash
bash scripts/run_evidence_bridge.sh status
bash scripts/run_evidence_bridge.sh log
bash scripts/run_evidence_bridge.sh module-log scheduler
bash scripts/run_evidence_bridge.sh module-log evidence
bash scripts/run_evidence_bridge.sh module-log effectiveness-current
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
| `BACKGROUND_STATE_DIR` | `outputs/background-evidence-bridge` |
| `OUTPUT_DIR` | `outputs/evidence-bridge`，每次 start 新建子目录 |

使用自定义 state 目录/venv 时，后续 status/stop/resume 必须继续传相同变量。方法参数修改应写一份新的 YAML，使用 `bash scripts/start_evidence_bridge_linux.sh configs/your_method.yaml`。不要修改正在运行的 YAML 或源码。

## 3. 停止、续跑和终态

```bash
bash scripts/run_evidence_bridge.sh stop
bash scripts/run_evidence_bridge.sh status
bash scripts/run_evidence_bridge.sh resume
```

`stop` 给 monitor 发 SIGTERM，monitor 转发给 worker，由实验器保存已完成任务和部分诊断。等待 status 变为 `interrupted` 后 resume。stop 返回 `stop_requested` 不代表进程已结束，不能立即杀进程并假设日志都已写完。

resume 使用原 `exact-run-dir`、原配置路径、原 deployment override 路径。此时当前 shell 的新 `BRIDGETREE_DEPLOYMENT_CONFIG` 不会替换原参数；代码、数据、方法配置和部署身份仍须与冻结 run identity 相符。成功任务跳过，失败和待处理任务重跑。任务内搜索不是 frontier 级精确断点恢复：被中断的任务从头执行，之前部分证据作为诊断保留。改算法、配置或模型应启动一个新 run，不能借 resume 把两种方法混在一起。

monitor 状态 `completed` 表示 worker 正常退出；**仍要查看运行目录 `completion.json` / `summary.json`** 区分 `completed` 与 `completed_with_failures`，不能把进程 exit 0 当全任务成功。错误原因在 `failures.jsonl`、outcomes 和模块 requests 中。实验器已有基础设施重试，超过有限次数后记录失败并继续；resume 可以继续失败任务。新证据 schema/引用/预算错误不会伪装成成功 fallback。

## 4. 日志目录与权威来源

固定管理目录 `outputs/background-evidence-bridge/`：

| 文件 | 用途 |
|---|---|
| `evidence_bridge.status.json` | monitor 当前 PID、状态、run_dir、退出信息 |
| `evidence_bridge.log` | stdout/stderr、heartbeat、后台结果 |
| `evidence_bridge.spec.json` | 原启动参数，resume 从此恢复 |
| `evidence_bridge.run_dir` | 当前实际运行目录，只有一行绝对路径 |
| `history/` | 重新启动/恢复前的管理状态与主日志 |

每个 `outputs/evidence-bridge/start_<日期>_<PID>/`：

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
| 需求规划 | `planner` | q-only 需求内容、schema 校验/修复、是否遗漏 query 所需历史阶段；原始输出在任务 artifact |
| 多目标调度 | `scheduler` | phase（coverage/deepen/explore）、目标、量子开始/结束、ANN/集合前后预算、游标、暂停与切换原因；根覆盖和单目标份额是否变化 |
| 目标约束/转向 | `target`, `activation` | 四项 R、A、M_before/M_after/M_group；retain/speculate/reject；pivot 是否确实删除旧 e、新根来自哪里、有无去重；汇总 pivot_count 只计 queued，尝试和拒绝分开 |
| 检索提案 | `proposal` | 原 query/桥接/条件/缺口查询各次 ANN、返回 IDs、池外发现、重复和额度耗尽 |
| 全集评分与归档 | `scoring`, `state`, `archive` | 已完成集合及预算；archive 保存完整 P/Pe/PG/PGe；未完整测量不得生成 A |
| 原文证据映射 | `evidence` | 全候选全文分片暴露、原文 quote/offset/role 校验、support/partial/contradiction、explicit/inference；不能只看有效证据条数忽略未映射候选 |
| 整体选择 | `selection` | 冻结需求的覆盖/缺失/歧义、支撑 IDs、每轮 added/removed IDs、实际完整输入预算和修订；不能把不满足 R 正边际当自动拒绝理由 |
| 缺口检索 | `feedback` | 哪项需求缺失、targeted query、ANN 计费、返回新/旧 ID、是否重映射、无新证据或预算耗尽终态 |
| 最终输入与答案 | `context`, `effectiveness-current` | 最终原始 Memory、ContextPlan、请求 hash、答案解析/正误；old/new 方法相同 payload 也可能得到不同输出 |
| 成本与失败 | `cost`, `requests`, `stop` | 逻辑 ANN/集合/证据 LLM 调用 vs 物理 HTTP 重试、缓存命中、预算耗尽、typed error；token estimate 不冒充 tokenizer 真值 |

证据阶段默认最多 24 次 LLM 调用，包括规划、全文映射、整体选择、最多一次 JSON 修复及有限反馈/预算修订；最终 reader 调用另计。这是冻结提示推理新增开销，不属于原 selection 512 次 R 集合预算。证据整表过大或不合法会产生 typed failure，不能认为“分片了”就一定可以容纳所有映射。

证据选择 artifact 中的具体字段如下，查原始记录时使用实际字段名，不通过文字描述猜测：

| 字段位置 | 字段 |
|---|---|
| `evidence_selection.costs` | `evidence_llm_calls`, `evidence_json_repairs`, `evidence_input_tokens_estimate`, `evidence_output_tokens_estimate`, `evidence_llm_elapsed_ms`, `evidence_elapsed_ms`, `evidence_calls_by_operation`, `token_count_is_estimate` |
| `evidence_selection.diagnostics` | `evidence_candidates`, `evidence_mapped_candidates`, `evidence_unmapped_candidates`, `evidence_units`, `evidence_verified_mappings`, `evidence_requirements` |
| 覆盖与修订诊断 | `evidence_covered_requirements`, `evidence_partial_requirements`, `evidence_missing_requirements`, `evidence_ambiguous_requirements`, `evidence_validation_failures`, `evidence_selection_revisions`, `evidence_feedback_rounds`, `evidence_selected_count` |
| `evidence_selection.coverage[]` | `requirement_id`, `status`, `evidence_ids`, `kind`, `explanation`, `supporting_ids` |
| 完整任务级记录 | `requests`（messages/raw_response/validation）, `exposures`, `selection_rounds`, `mappings` |

`evidence_unmapped_candidates > 0` 表示执行/映射没有完成，应结合任务失败状态分析；`evidence_validation_failures` 包括可修复的非法输出，不能只看终态成功就认为模型每次响应都合规。

## 6. 汇总和定位一条错误

```bash
bash scripts/run_evidence_bridge.sh summary
# 或指定一个旧目录，不改变当前 run
.venv/bin/python scripts/summarize_evidence_bridge.py outputs/evidence-bridge/start_YYYYMMDD_HHMMSS_PID
```

汇总读取冻结计划及 `outcomes/`，不累加 append-only 重试事件。`diagnostics.evidence_bridge_summary` 的每个数值指标输出 `observed_tasks/missing_tasks/sum/mean/min/max`，cost 同样单列；缺字段不会当 0。旧 dense/activation 没有新方法 summary 是预期缺失。schema/任务身份错误列入 `invalid_outcome_files`，命令返回非零。运行中生成的汇总不是跨文件事务快照，应在完成后重新执行一次。

新摘要同时保留 selector.diagnostics，例如全文映射完成数、校验失败、集合修订和反馈轮次。removed_memories 只计实际接受的整体集合变更，不能把 proposed 与 accepted 重复累加或把预算拒绝当成已经删除。

定位错误按以下顺序：

1. 在 `outcomes` 找 `status=success && correct=false` 的题，记录 task ID、question ID、attempt、selected_ids 和 context_hash；失败任务单独查 error_type，不混进检索机制错误。
2. 查 `candidate_pool/<task_id>.json` 中 `search`：目标有没有机会展开，暂停是否有剩余游标，预算在哪一阶段耗尽，候选是否真的召回/完整归档。
3. 查 `evidence_selection`：需求是否适合当前 query；相关记忆是否全部映射；引用是否被正确归为用户明示或助手建议；历史阶段是否保留；正确候选没被选是缺映射、coverage 判断、冗余删除还是 reader 预算修订。
4. 对照 `feedback`，确认缺失需求是否触发预算内真实 ANN，新候选是否进入映射和新集合。
5. 对照最终 ContextPlan 和实际 reader request，确认选出的原文确实进入模型。若相同 payload 的答案不同，标明 reader 波动，避免把变化全归因于搜索。模型自报 `covered` 只表示经引用校验的覆盖判断，不等于 gold evidence recall 或真实答案贡献。

可以用下面脚本列出当前错误，无需扫描数 GB 请求历史：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
state = Path('outputs/background-evidence-bridge/evidence_bridge.run_dir')
root = Path(state.read_text().strip())
for path in sorted((root / 'outcomes').glob('*.json')):
    row = json.loads(path.read_text())
    if row.get('status') == 'success' and row.get('correct') is False:
        task = row['task']
        print(task['method_id'], task['question_id'], task['task_id'], row['attempt'], row['selected_ids'])
PY
```

## 7. 本地验收与真实服务器评测的边界

本项目提供 `tests/test_evidence_bridge_operations.py`，实际启动 detached monitor＋临时 fake worker，检查 start/status/重复start/stop/resume、冻结部署参数、路径含空格、package内容和retry-safe汇总。它不调用用户服务，不声称新方法准确率已提升。

```bash
.venv/bin/python -m pytest tests/test_evidence_bridge_operations.py -q
```

方法层语义/边界测试与端到端本地模拟见设计文档验收记录。打包后服务器首次完整结果才是新版真实运行数据；保留日志、配置 identity 和包 SHA 后，再据此判断预算覆盖、目标转向、证据保存是否带来改善。
