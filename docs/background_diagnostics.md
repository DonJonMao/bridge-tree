# PR1–PR4 后台诊断操作手册

这套入口安装运行依赖、启动可脱离 SSH 的诊断进程，并持续记录进度和模块事件。它不训练模型，不更新权重，不新增评分目标、选择器或调度策略。诊断协议、历史归档含义及逐阶段手动命令见 [诊断运行手册](diagnostic_runbook.md)。

## 1. 先准备服务器配置

上传完整仓库源码，不复制本机 `.venv`。服务器需已有 Python ≥3.9、可用的 `venv`、Bash，以及安装基础 Python 依赖和访问三个模型服务所需的网络。脚本不使用 sudo，也不安装系统 Python、CUDA 或本地模型权重。

运行配置副本 `configs/diagnostic_28.server.yaml` 需要自己准备，它不是一个已配好的部署。以 `configs/diagnostic_28.yaml` 为模板，核对：

1. `full_archive`、`detail_archive` 指向服务器上的原始 `chain-audit-full.tgz`、`chain-audit-detail.tgz`；保留原始 SHA256。它们不是训练数据下载任务，也不会由启动器自动下载。
2. `questions`、`contexts` 使用同一 PersonaMem-v1 32k 数据及原 revision，记忆单位仍为 `user_assistant_pair`。配置中的相对路径相对于该 YAML 所在目录；不要保留本机 `/Users/mao/...` 路径。
3. `deployment_config` 是实际基础部署配置；从 `diagnostic_deployment.example.yaml` 准备私有 `deployment_override`，其顶层为 `models`，不要加入 `base_config`。填写 embedding、reranker、generator 的实际 endpoint、必要模型名及真实部署身份；不要用 API 别名或随手填的 revision 冒充验证。
4. 密钥放环境变量或既有私有凭据配置，私有文件限制为本人可读写。自定义私有文件名不一定被 `.gitignore` 覆盖，提交前自行确认；不要把密钥、私有 override 或完整 manifest 推入公共仓库。
5. 先完成源码、数据、路径和部署配置，再冻结新运行。不能把本机 manifest 复制到服务器后当作当前源码/服务的在线计划。

身份模板中的 `identity_source: unknown` 和空 revision 会阻止在线执行。`checkpoint_revision`、`weights_sha256` 或 `deployment_revision` 至少一种必须有实际依据，身份来源等级也必须如实声明。量化、tokenizer 等未核实的信息继续留未知，不通过猜填绕过门禁。

## 2. 一键安装并启动

在仓库根目录执行：

```bash
bash scripts/start_diagnostics_linux.sh configs/diagnostic_28.server.yaml
```

默认会真实调用已配置的模型服务。启动器先检查后台 job `diagnostics`，再验证或创建独立 `.venv-diagnostics`，执行基础 `pip install -e`，最后委派 `run_diagnostics.sh start --config ...`。安装过程在前台持续输出，同时追加到 `outputs/background-diagnostics/bootstrap.log`。只有后台启动成功返回之后，才能把它视为已脱离当前 SSH 的任务。

检查启动返回的 `launch_result`、`monitor_ready`，并随后执行 `status`。后台已接管进程不等于身份门禁已通过，更不等于服务健康或实验完成；后续阶段仍可能失败。

默认配置的预列数量和物理请求上限如下；修改条件、重复数或 seed 后必须重新冻结并相应更新预算。

| 阶段 | 固定项目数 | 物理 HTTP 尝试上限 |
| --- | ---: | ---: |
| 全子集 fresh-all 评分 | 28 个逻辑输入，包含每题的空集 | 84 |
| 重复生成 | 31 个条件 × 10 次 = 310 个 trial | 930 |
| 根顺序消融 | 3 题 ×（legacy + seeds 7/19/43）= 12 次 | 12,000 |

根消融不生成答案；每次保留 ANN=36、搜索与选择各 512 个逻辑唯一集合增量上限。默认 `task_max_attempts=1`；底层 HTTP 重试仍受物理上限约束。上限不是保证消耗量，也不是 token 或费用金额。全程 `optimizer_steps=0`、`weights_updated=false`。

在线流水线依次执行：冻结计划、历史归档分析、在线身份门禁、fresh-all 评分、fresh 分析、重复生成、独立评估、根顺序消融、统一报告。历史 24/28 个已知分数只用于历史视图，不拿来填充当前 fresh-all 测量。

可用环境变量：

| 变量 | 默认值或用途 |
| --- | --- |
| `BRIDGETREE_SETUP_PYTHON` | `python3`；仅用于安装前检查和创建 venv |
| `BRIDGETREE_VENV_DIR` | 仓库下 `.venv-diagnostics`；不要复用正在运行的实验环境 |
| `BRIDGETREE_SKIP_INSTALL` | `false`；设 `true` 时仅跳过依赖安装，已有环境仍须可导入依赖 |
| `DIAGNOSTIC_STATE_DIR` | 仓库下 `outputs/background-diagnostics` |
| `DIAGNOSTIC_RUN_ROOT` | 仓库下 `outputs/diagnostics` |
| `BRIDGETREE_BASE_PYTHON` | 管理命令使用的解释器；启动器会设为选中的 venv Python |

路径不能是 `/`、用户 home、仓库根或仓库祖先；venv、状态目录和运行根目录不能相同或相互嵌套。残缺 venv、悬空 venv 符号链接、损坏状态文件会被拒绝，不会自动覆盖修复。现有 `starting/running` job 会在安装前被拒绝；`failed/interrupted` job 会提示使用 `resume`，不是重新安装。

启动器有仓库级 setup 锁，避免两个 bootstrap 同时安装。若进程被强制杀死留下 `.start_diagnostics_linux.lock`，它会保守阻止新启动；确认记录的 PID 以及相关安装进程都已退出后再处理锁，不自动猜测清理。指定状态目录之外的任意进程是否也在使用同一个 venv，不是该锁或单个状态文件能证明的；不要跨仓库任意复用环境。

`umask 077` 保护新建文件，但“无 gold 的公开输入投影”不等于可公开发布的数据：manifest、原始生成和历史档案仍包含个人历史，应私下保管。模块日志使用脱敏 ID、分数和 hash，不打印请求正文、endpoint 或密钥。

## 3. 离线验收与转为在线

离线后台验收：

```bash
bash scripts/start_diagnostics_linux.sh configs/diagnostic_28.server.yaml --offline
```

这里的 `--offline` 表示零 embedding/reranker/generator 调用，不表示禁止 pip 联网。已有可用环境可设置 `BRIDGETREE_SKIP_INSTALL=true`。离线阶段只冻结计划、恢复历史分数、评估当前已有或 pending 的生成记录并写报告；完成状态为 `offline_complete`。28/310/12 个在线项目仍可全部是 pending。

需要从已完成的离线运行继续在线测量时：

```bash
bash scripts/run_diagnostics.sh resume --online
```

这仅在原 manifest 已含完整真实身份、源码和服务配置没有变化时成立。若最初离线计划使用 unknown 身份，后来才补 override，身份已经发生变化，不能续用旧 manifest；应使用配置齐全的新运行，例如 `start --config configs/diagnostic_28.server.yaml`。不要编辑 manifest 或删除身份检查来续跑。

`bash scripts/run_diagnostics.sh preflight --config ...` 是前台离线流水线，不提交后台 job，也不会把它登记成 `status` 的新任务。需要后续通过后台管理器续跑时，优先使用上面的后台 `--offline` 方式。

## 4. 查看、停止和续跑

```bash
bash scripts/run_diagnostics.sh status
bash scripts/run_diagnostics.sh log
bash scripts/run_diagnostics.sh module-log --module execution
bash scripts/run_diagnostics.sh module-log --module scoring
bash scripts/run_diagnostics.sh module-log --module activation
bash scripts/run_diagnostics.sh module-log --module selection
bash scripts/run_diagnostics.sh stop
bash scripts/run_diagnostics.sh resume
```

`log` 跟随后台 job 主日志，`module-log` 跟随指定模块；二者均显示最近 100 行后持续跟随。模块名用 `--module` 指定，不是 `run_chain.sh` 的位置参数用法。支持 `events`（全部模块）、`execution`、`proposal`、`scoring`、`activation`、`state`、`selection`、`stop`、`context`。Ctrl+C 只关闭日志查看，不停止实验。

`stop` 核实记录的 monitor PID、命令和 detached session 后发出正常停止请求；返回 `graceful_stop_requested` 不等于已经停止，继续用 `status` 确认。服务端可能已经执行了正在途中的请求，停止不代表这些成本为零。不要把 `kill -9` 当作正常停止流程。

`resume` 复用记录的 config 和 run directory，默认继承上次在线/离线模式；`--online` 显式切换到在线，`--offline` 显式只执行离线部分。成功和终止失败都不会因重复执行命令获得新样本或额外额度。已落盘的完成/终止失败事件可恢复缺失的 outcome；只有可重试且未耗尽任务额度的失败才继续尝试。答错与解析失败不触发重试。

重新测量已终止失败需要显式的新运行，并报告新增测量预算，不能通过 `resume` 偷增样本。若已有 `failed/interrupted` job 而确实要新建，可以使用 `start --config ... --run-dir ...` 指定一个空的新目录；它必须位于声明的 `--run-root` 之下。原目录不要删除。

管理命令支持 `--state-dir`、`--run-root`、`--job`，默认 job 为 `diagnostics`。使用自定义路径时，优先复制启动输出的 `commands` 中的完整命令，其中包含解释器及目录，避免查询到另一个状态目录的旧 job。启动器也会打印带完整环境变量的 status/resume 提示。

底层仍由原 background manager 的新 session 启动机制负责脱离 SSH。它不是 systemd、作业调度器或重启恢复服务：机器重启、容器销毁、调度器回收、磁盘故障仍会结束进程。文件保留下来时可以检查并尝试 `resume`，但必须通过身份与预算校验。

## 5. 如何读当前进度与成功率

`status` 返回外层 job 状态，并附带当前运行的 `progress`、`completion`。进度约每 5 秒写入一次，实际刷新可因本地 I/O 延迟；它是派生快照，不是权威 trial 账本。没有 `progress` 时先查看是否仍在建 manifest，或 planning 已经失败。

`progress.phases` 下只有 `score`、`generation`、`root` 三个测量阶段；每阶段都有四个互斥分区：

```text
planned = success + failed + pending + unknown
```

| 字段 | 含义 |
| --- | --- |
| `success` | 当前固定项目成功执行；对于生成，不等于回答正确 |
| `failed` | 执行已终止的错误或预算耗尽；不等于答错 |
| `pending` | 尚无终态，包括仍运行或待允许重试的项目 |
| `unknown` | 如耗尽额度后仍无法判定结果的 `InterruptedAttempt`；不是错误答案 |

`started`、`in_progress_or_retry_pending`、`outcome_unknown` 是辅助指标，与上述分区重叠，不能再次相加。HTTP 错误仍归执行失败；即使 `outcome_unknown=true` 表示服务端是否完成不明，也不一定放入 `unknown` 项目分区。

各阶段的 `physical_attempts` 和 `transport_budget.used_reservations/cap/remaining` 来自请求预留事件，包含重试和拆批子请求；崩溃发生在预留后、实际发送前也可能占用额度。`http_errors`、`http_error_types` 汇总观察到的物理失败。`physical_elapsed_ms` 不含退避等待和任务外围开销，`server_reported_tokens` 只统计服务实际返回的 token 字段，缺失为 null，不是完整账单。不要把模块增量再加到任务总计。

答题准确率看 `evaluation.json` 的 `conditions`：`successful_accuracy` 是正确数/成功生成数，`fixed_trial_denominator_accuracy` 是正确数/该条件全部预列重复数，失败和 pending 不从固定分母移除。`progress.evaluation.conditions` 是其中已评估成功输出的摘要；评估阶段尚未到达时不可用或滞后，不据此把进行中的答案判错。

只有 3 个独立问题，10 次调用是每个条件的技术重复，不是新增独立题目。不能把 310 个 trial 当作 310 道 benchmark 题，也不能把各子集最好成绩当成方法准确率。

外层 `state=completed` 仅代表 worker 以正常退出码结束。还要检查 `completion.status`：`completed`、`completed_with_failures`、`offline_complete` 含义不同。`failed` 或 `interrupted` 查看 `last_phase`、错误类型和对应日志；`online_preflight.json` 的 `blocked_before_network` 表示身份门禁拦截，不能称为 HTTP 服务故障或线上实验完成。

## 6. 用模块日志定位改进点

先按 `run_identity`、`phase`、`task_id/item_id`、`task_attempt` 对齐记录；生成还用 `condition_id/repeat_index`，根消融还用 `root_tie_seed/root_tie_break`。`modules/events.jsonl` 与单模块文件包含同一事件的两份视图，不能叠加统计；`event_id` 用于对齐，`sequence` 只在单次 recorder 生命周期内递增，resume 后会重新开始。

| 要判断的问题 | 看哪些证据 | 结论边界 |
| --- | --- | --- |
| R 目标是否与回答收益错位 | `scoring` 的 `ids/score/source/objective_semantics`；`selection` 日志内 `comparisons` 的 `base_score/combined_score/marginal`；`context` 的 `selected_ids/context_hash`；再对齐 `evaluation.json` 中 `paired_to_historical_selection` 的 `rescues/harms/common_success_blocks` | 只有“加证据稳定改善回答，却降低 R”才支持目标错位判断；正交互、正边际或高 R 本身不证明回答改善 |
| 是否集中在少数根/单链 | `state` 的 `target_id/premise_ids/premise_depth/priority/is_zero_priority_root`，`root_trace.per_target` 的状态数与成本；`progress.module_diagnostics.per_root_trial` 的 `root_coverage/max_target_state_share` | 低根覆盖、高目标集中度结合跨 seed 的 archive/selection 差异表明顺序敏感性；不自动证明必须改轮询或保留根预算 |
| 外扩是否只增加候选、没有进入最终上下文 | `proposal` 的 `candidate_ids/domain_scope/ann_call_index`；根 trace 的 `external_candidate_ids/external_archived_ids/external_selected_ids`；进度的 `external_candidate_count/external_selected_count` | 外部候选多但最终采用少说明转化低，不直接证明外扩无用；还要查真实 bundle 是否存在、容量和边际为何拒绝、回答是否改善 |
| 是否被 HTTP/容量/预算打断 | `execution` 的 `task_attempt_failed/cause_type/http_status`；`requests.jsonl` 的实际 HTTP 尝试与拆批关系；`stop` 的 `ann_budget_exhausted/score_budget_exhausted/input_capacity/no_positive_marginal` | HTTP 500 是基础设施失败；ANN 到限是搜索预算停止；`no_positive_marginal` 是原目标下的停止，不是服务异常或任务正确性证明 |

`activation` 保留 `P/Pe/PG/PGe`、`activation`、`context_marginal`、`signal_kind/signal/accepted/queued`。这些值可以直接复核四项差分 `PGe - PG - Pe + P`，但只是 reranker 测得的交互，不是因果关系。`selection` 的每个 `selection_round` 保留 `current_ids`、完整 `comparisons`、`accepted_bundle_ids`、`selected_ids_after` 与 `complete`，可以区分真正拒绝的候选和未完整比较的一轮。

`scoring.source` 区分 `reranker`、`memory_cache`、`persistent_cache`；缓存命中导致零新 HTTP 不等于评分模块没工作。当前 `objective_semantics=legacy_query_relevance`、`utility_validation_id=null`，不要把 [0,1] 分数当作已验证的 cardinal utility。相同 `context_hash` 只说明上下文相同；比较完整生成请求还应核对 manifest 或生成 outcome 中的 `wire_payload_hash`。

HTTP 500 本身不能定位为显存不足、输入过长或服务瞬态故障；需结合请求长度估算、重试/拆批父子关系及服务端日志确认。不要仅凭提高重试次数或降低 batch 后偶然成功就断言根因。

这些 proposal/activation/state/selection 在线模块事件主要在根消融阶段产生；评分和生成阶段没有新的搜索事件是正常的。历史分析从档案读取，不会把旧事件伪装成当前模型调用。`progress.module_diagnostics` 只概括已经有 root outcome/终态事件的观测；正在执行的根可能尚未进入摘要，此时看实时 `module-log`。部分失败的 `partial_selected_memory_count` 不是最终集合，缺失 final selection/hash 应保持 null，而不是当作空集合。

## 7. 文件位置与故障检查

默认固定状态目录为 `outputs/background-diagnostics`：`diagnostics.status.json`、`diagnostics.log`、`diagnostics.run_dir`、`bootstrap.log`。不要再查询旧链实验的 `outputs/background/chain_full.*` 来判断诊断任务。

每次实际运行位于 `outputs/diagnostics/diagnostic_...`，路径以启动/status 返回的 `run_dir` 或 `diagnostics.run_dir` 文件为准：

- `run.log`、`runtime.jsonl`：阶段与心跳；`progress_snapshot_error` 表示派生快照更新出了问题，不会覆盖权威 outcome。
- `progress.json`、`completion.json`：进度快照与流水线终态。
- `modules/*.jsonl`：即时模块事件；`requests.jsonl` 是物理请求审计，`attempts.jsonl` 是完整任务尝试账本。
- `score/*.json`、`generation/*.json`、`root/*.json`：固定项目的成功、失败或未知 outcome，包含可用的部分轨迹。
- `offline_analysis.json`、`fresh_analysis.json`、`evaluation.json`、`root_summary.json`、`diagnostic_report.json`：不同证据视图，未执行的部分应保持缺失/null，而不是制造成功结果。

遇到失败，先保留这些文件，再查最后阶段、错误类型和预算。不要删除 ledger、改已冻结预算、覆盖 manifest 或重新安装活跃环境来“恢复进度”。源码或部署确实变化时创建新运行，保留旧运行作可追溯证据。审计写入失败会终止流水线，不能在记录缺失时继续模型调用。
