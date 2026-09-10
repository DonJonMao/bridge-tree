# BridgeTree 条件激活检索迁移与运行说明

日期：2026-09-10
参考仓库：`https://github.com/DonJonMao/bridge-tree`
参考基线：`65f411e3d3270874c54ec1e74d65f63e22564784`
实现分支：`codex/conditional-activation`

本文描述 `chain-run` 使用的无训练条件激活检索。旧树搜索、旧 Chain
原语和旧实验入口仍然保留；新入口显式调用 `dependency_*` 模块，不会让旧实验
在不知情的情况下改变算法。

## 1. 设计边界

新流程保留 PersonaMem 历史规范化、问题时间点之前的可见性边界、原问题一跳
检索、`query + memory` 初始外扩、真实来源 ID、已有模型部署配置和最终生成器
接口。后段改为固定目标记忆的条件搜索，再以完整证据组合相对于当前上下文的
边际决定最终上下文。

流程只使用已有 embedding 服务、冻结的 pointwise reranker 和最终回答模型。
它不训练模块，不读取生成器 log-probability，不生成个人事实，不使用 value
model、加权奖励混合、路径保护、硬搜索深度、固定 bundle 数量或全局最优证书。
生成器仅用于最终回答。

正激活只表示当前评分器下的互补性。它不证明必要条件、现实因果方向，也不保证
加入前提后 bundle 总分上升。有限语义提议和二元救援也不等于穷举全部前提。

## 2. 模块职责

| 文件 | 职责 |
|---|---|
| `dependency_config.py` | 解析严格的新资源配置与已有部署配置，拒绝新入口中的无效旧树 overlay |
| `dependency_retrieval.py` | 一跳、初始 bridge 外扩、全可见库条件补检索、固定池对照和来源图 |
| `dependency_scoring.py` | 规范集合序列化、空集实测、持久缓存、完整批次校验、长度与逻辑配额 |
| `dependency_search.py` | 四项差分、固定目标状态、pair rescue、bundle 档案和动态最终选择 |
| `dependency_experiment.py` | 全量任务冻结、真实逐题执行、原子 outcome、指标、心跳和恢复 |
| `clients.py` | HTTP embedding/reranker/generator；reranker 明示截断时失败 |
| `chain_worker.py` | 前台 worker 与纯数据预检 |
| `run_chain.sh` | Linux 后台 `start/status/log/resume/stop` |
| `package_chain_server.sh` | 打包源代码、配置、测试、文档及完整 raw/processed 数据 |

## 3. 数学契约

所有集合评分调用的 query 端始终是未改写的原问题 `q`：

\[
R_q(S)=\operatorname{FrozenReranker}(q,\operatorname{Serialize}(S)).
\]

`Serialize` 按时间和稳定 ID 排序真实记忆，保留原文、角色、时间和来源。它与
当前搜索中谁是目标、谁是前提无关。空集也必须通过同一 endpoint 实测，其固定
文本为：

```text
Personal memories: [No personal memories supplied.]
```

目标 `e` 在前提集合 `P` 下的普通边际为：

\[
M_q(e\mid P)=R_q(P\cup\{e\})-R_q(P).
\]

候选前提组 `G` 对固定目标的激活为：

\[
A_q(G\Rightarrow e\mid P)=R_q(P\cup G\cup\{e\})-R_q(P\cup G)
-R_q(P\cup\{e\})+R_q(P).
\]

每条 activation 记录保存 `P`、`Pe`、`PG`、`PGe` 四个集合及四个实测分数，
并同时保存普通上下文边际 `R(PGe)-R(Pe)`。

整个运行只使用一个声明的 pointwise 分数尺度。`unit_interval` 和
`logit_difference` 都直接保留服务返回的有限标量；集合评分器不做 sigmoid、
softmax、min-max、批内归一化或 rank 转换。

## 4. 步骤 0–7

### 步骤 0：先裁剪可见历史

每题只读取 `end_index` 之前的消息，然后应用已有时间可见性规则，再调用
`messages_to_memories` 形成 `user_assistant_pair` 原子记忆。角色、时间、原文、
消息索引和来源 ID 均保留。

裁剪发生在 embedding、索引、reranker 和候选缓存之前。正确答案只在最终回答
返回后用于评估，不进入检索、评分、缓存或诊断请求。公开选项只进入最终生成
请求。

### 步骤 1：原问题一跳

原问题经既有 embedding query 接口编码，在当前题完整可见记忆库上用确定性
exact inner-product index 取 `initial_width` 个记录。这里的 ANN 是检索接口
称呼；默认后端是精确索引，并不宣称近似检索。

### 步骤 2：一次 query-memory 初始外扩

每个一跳 seed 用原问题和该真实记忆构造 bridge probe，再在同一可见库取
`initial_expansion_width` 个记录。dense 与 bridge 的去重并集构成初始池；
外扩记录不会再被独立问题相似度阈值过滤。并集中每条记忆都可成为目标。

纯 `dense` 与 `dense_rerank` 只做原问题一跳，不支付不会使用的外扩调用。

### 步骤 3：来源与状态

每条召回边记录为 `retrieval_proposal` 且 `dependency_claim=false`。检索来源图
不能当作前提关系。

搜索状态为：

\[
H=(e,P),\qquad e\notin P.
\]

状态身份同时包含固定目标 ID 与规范前提 ID 集合。同一候选在不同 `P` 下必须
重新评分；只有同一 `(e,P)` 才只展开一次。后继是 `(e,P∪G)`，不会把最新前提
提升成新目标。

### 步骤 4：完整集合评分

每个候选用同一四项公式测量。批次即使按分数排序返回，也必须依靠 `index`
恢复输入位置，并验证无缺失、无重复、索引有效、分数有限、尺度有效且后端没有
报告截断。

一次四项请求先整体核对逻辑配额与完整输入长度，再执行任何新网络调用。不能将
超时、NaN、缺索引、输入过长或配额不足转换成零分或 embedding 分数。

### 步骤 5：固定目标补检索

每个状态把 `q + e + P` 仅作为 embedding proposal 文本，在完整可见库有限宽度
检索，排除目标与已有前提。reranker 的 query 仍然只是原问题。

根状态还合并初始池内候选；后续状态不会因为某候选曾在另一个 `P` 下测试过就
全局禁止它。根状态以零优先级进入同一 best-first frontier，测得正信号的后继
按本次信号调度，因此非空前提路径能在有限预算内继续演化。

### 步骤 6：有限 pair rescue 与停止

当本状态所有单候选均无正信号且资源允许时，在本轮有限候选的前
`pair_rescue_width` 个中测试二元组。默认宽度 4 至多 6 对。这只覆盖部分联合
激活，不穷举全部子集或所有跨池配对。

档案保留目标单例、独立候选单例、访问过的中间状态，以及一测得正信号便立即
归档的后继。即便随后预算不足以展开，已测 bundle 也不会丢失。

停止记录区分：ANN 配额、集合评分配额、输入容量、有限提议为空、没有正实测
信号、后继已经访问。它们只描述有限运行，不能作为“其他证据不存在”的证书。

### 步骤 7：冻结档案后动态选择

搜索完成后冻结候选 bundle 档案。令已选记忆并集为 `S`，每轮对所有输入可行
bundle 计算：

\[
\Delta_q(B\mid S)=R_q(S\cup B)-R_q(S).
\]

选择最大严格正边际，合并真实 ID 并重新计算下一轮。共享记忆只序列化、计分和
发送一次。同分按新增记忆数与稳定 ID 决定，不能依赖 hash 遍历顺序。

每一轮必须有足够独立 selection 配额比较所有可行候选后才能提交；不完整轮次
不选择任何 bundle。这里不使用静态 bundle 分、激活和、边际/令牌比，也不固定
选择数量。

最终使用同一个严格 `ContextPlan` 发送选中的精确记忆并集。可行性核对包含 query、
公开选项、生成模板和所有选中原文。不存在生成前的二次截断或偷偷删除前提。
token 数沿用仓库确定性估算器，并在产物中标为 estimate。

## 5. 缓存与资源计数

集合缓存身份包含原问题、可见历史 cutoff/内容、真实文本和元数据、序列化模板、
模型身份、endpoint、分数尺度与 pointwise 契约。改变其中任一项都不能复用旧值。

持久缓存命中仍消耗本题的唯一集合逻辑配额；缓存只减少网络成本，不能让 warm
run 搜索得比 cold run 更深。分别记录：

- `scored_sets`：本题请求过的唯一集合数量；
- `reranker_adapter_requests`：调用 reranker 客户端的批次数；
- `cache_hits`：从持久或进程缓存恢复的集合数；
- `ann_calls`：逻辑检索探针数。

搜索和最终选择各有独立新增集合配额。进入选择阶段时累计上限设为当前
`scored_sets + max_selection_sets`，而不是把 limit 重新设成小于已经消费的值。

每次实际执行 attempt 开始时只做一次数值协议探针：比较空集、单记忆、混合批次
和反序批次，使用配置中的 `rtol`/`atol` 判断 batch composition 一致性并保存最大
偏差。该探针独立于搜索配额，也不证明分数具有正确的语义互补性。最新快照写入
`service_probe.json`，每次 attempt 的成功或失败记录先追加到
`service_probes.jsonl`，因此恢复不会覆盖历史。

## 6. 方法与默认资源

默认方法共五个：

| 方法 | 候选发现 | 搜索信号 | 最终上下文 |
|---|---|---|---|
| `dense` | 原问题一跳 | 无 | dense 顺序、共同生成预算 |
| `dense_rerank` | 原问题一跳 | 单例集合分排序 | 同一生成预算 |
| `activation` | 初始扩池及全库补检索 | 四项激活 `A` | 动态 bundle 边际 |
| `context_marginal` | 相同提议接口 | `R(PGe)-R(Pe)` | 动态 bundle 边际 |
| `activation_fixed_pool` | 初始扩池后固定域 | 四项激活 `A` | 动态 bundle 边际 |

可选消融是 `activation_no_pairs` 与 `activation_singleton_selection`，两者复用同一
管线。默认 589 题乘五方法，共 2,945 个任务，不设置 limit 或静默开发子集。

默认资源：

| 字段 | 值 |
|---|---:|
| `initial_width` | 12 |
| `initial_expansion_width` | 4 |
| `proposal_width` | 4 |
| `max_ann_calls` | 36 |
| `max_scored_sets` | 512 |
| `max_selection_sets` | 512 |
| `pair_rescue_width` | 4 |
| `reranker_batch_size` | 32 |
| `reranker_max_input_tokens` | 8192 |

这些是可复现实验起点而非调优后的最优值。相同资源上限不表示不同方法实际成本
相等，因此报告保存每题实测模型工作量。

## 7. 数据、执行与恢复

正式配置固定 PersonaMem-v1 32k revision
`fd7c30f071d5c2ee2a211506783be222d7b6002e`。数据预检验证 raw/processed 文件
校验和、非空、589 个唯一问题 ID、可见性 cutoff 和最终 2,945 项任务计划。任务
计划必须在任何模型调用前原子冻结。

当前包内全量文件身份如下：

| 文件 | SHA-256 |
|---|---|
| `questions_32k.csv` | `cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c` |
| `shared_contexts_32k.jsonl` | `217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a` |
| processed `contexts.jsonl` | `36ede76374746f5e2e7050544cb5db515913f6882bccd026acc60bef8d37cdfa` |
| processed `queries.jsonl` | `26d7888aa3ea94690c0c4ce3a39e1d0edb3be93c5c6ce3169e21cb6b63547d45` |

正式配置没有 `limit` 或开发抽样；all-data 指标覆盖全部 589 题。由于当前没有可用
的权威 seen/confirmation protocol manifest，这两类报告明确为 `not_defined`，不会
从已查看的数据临时制造 unseen split。

规范化数据先写入输出目录内的临时文件并逐文件 flush/fsync；三个文件全部生成并
计算校验和后，才依次替换 `contexts.jsonl`、`queries.jsonl`，最后以
`manifest.json` 作为校验和 commit marker 发布。发布前失败会保留上一版完整文件。
这是逐文件原子替换与 manifest-last 协议，不宣称三个文件具有单次文件系统事务。

若显式传入权威 protocol manifest，运行验证其身份并据其生成 seen/confirmation
报告；否则两类报告标为 `not_defined`，不会在看过完整数据后发明新 split。无论
是否有角色清单，都保留 all-data 指标。

每任务 outcome 是恢复用权威状态，并原子写入 `outcomes/`。prediction 与 failure
日志是 append-only 事件历史。恢复复用原目录与冻结计划，跳过成功项，重试失败
和 pending 项，并拒绝配置、数据、源码或 protocol 身份变化。若所有 outcome 已
成功，resume 在创建模型客户端和协议探针之前返回，模型调用为零。

基础设施连接中断会先保存当前失败，并在原任务上执行下面的有界恢复；只有重试
预算耗尽或故障被明确标为不可重试时才停止本次 attempt，其余任务继续保持
pending，避免把同一服务故障重复花费在所有题上。失败仍在原计划分母中，不能
删除后只按成功任务计算准确率。

服务韧性分为互不混淆的三层：

1. 共用 JSON-over-HTTP transport 对连接错误、超时、`HTTPException`（包括响应
   未完整读取的 `IncompleteRead`）、UTF-8 解码失败、无效 JSON、HTTP
   408/425/429 和 5xx 最多发起 4 次物理请求。默认等待为 0.5、1、2 秒；若服务
   返回可解析的 `Retry-After`，等待可提高但最多采用 30 秒。除下面的 pointwise
   批次降级外，其他永久 4xx 只请求一次，标为 `retryable=false`，不会进入任务级
   重试。
2. 冻结 reranker 的契约为 pointwise，因此 413/422 可在第一次失败后直接把当前
   文档批次二分；500 则在该批次的 4 次 transport 请求仍失败后二分。子批次保持
   原索引并继续二分，直到成功或单文档仍失败。根批次一旦进入二分，所有层级的
   子批次都只允许 1 次 transport 请求，不会在每个二分深度重新支付 4 次 HTTP
   尝试；外层后续任务重试仍提供有界恢复机会。502/503/504 表示服务级故障，只做
   有界 HTTP 重试而不二分，避免在整体宕机时放大请求。二分与 transport 重试不
   重复扣除逻辑 scored-set、search 或 selection 配额。
3. pointwise service probe 与当前“方法×题”任务分别执行有界重试。正式配置的
   `infrastructure_task_max_attempts=3`、初始等待 15 秒、倍率 4，因此三次执行之间
   只等待 15 和 60 秒。第三次仍失败便打开 circuit、结束本次 execution attempt，
   并让尚未开始的任务保持 pending；永久 4xx 等显式不可重试故障会立即打开
   circuit，不等待 15 秒。等待可被 `SIGTERM`/`SIGINT` 中断并按可恢复终态落盘。

`events.jsonl` 与 `train.log` 记录
`infrastructure_retry_scheduled`、`infrastructure_retry_wait_completed`、
`infrastructure_retry_recovered` 和 `infrastructure_circuit_opened`；事件包含
`scope`、当前/下一 attempt、等待秒数、剩余次数、`retryable` 与 circuit 状态。
每次失败仍追加到 `failures.jsonl`；探针的每次结果另保存在
`service_probes.jsonl`，最新值原子写入 `service_probe.json`。任务结果与周期进度
区分 `tasks_attempted_this_attempt`、`unique_tasks_attempted_this_attempt` 和
`task_retries_this_attempt`。集合评分成本中的 `reranker_transport` 进一步区分
`logical_calls`/`logical_documents`、`batch_requests`/`batch_documents`、
`transport_attempts`/`transport_document_attempts`、`failed_batch_requests`、
`split_events`、`split_recovered_calls` 与 `failed_calls`，因此恢复性流量不会被误报
为新的逻辑搜索工作量。

每完成一个“方法×题”任务都会输出一条结构化 `module_effectiveness`；默认每完成
10 个任务另输出总进度，每 25 个任务输出 `method_metrics` 并刷新方法指标，每
30 秒刷新 active-task heartbeat。10/25 的周期按本 execution attempt 内首次处理的
unique `method×question` 计数；同一任务的基础设施 retry 不推进周期。进度和指标
仍分别报告 `tasks_attempted_this_attempt`（单位为 executor invocation）、
`unique_tasks_attempted_this_attempt` 与 `task_retries_this_attempt`，因此 cadence
稳定而额外工作量保持可见。resume 后这些区间计数在新 attempt 内重新开始。
`optimizer_steps=0`、`weights_updated=false`，日志不伪装训练步骤。

## 8. Linux / 910B 运行

该仓库是 HTTP 客户端，不安装或启动 910B 推理服务。服务器需要 Linux、Bash、
Python 3.9+ 与 `venv`，并能访问 Python 包源以及已部署的 embedding、reranker 和
generator。解包后的一键入口会创建或复用 `.venv`、安装项目、严格解析全量零调用
预检结果，并仅在确认 589 题、2,945 任务、0 模型调用且全部 pending 后提交后台
worker：

```bash
cd bridgetree_preference_rag
bash scripts/start_chain_linux.sh configs/chain_full.yaml
```

默认最低空闲空间门槛为 20 GiB，同时检查 output 与 cache 所在文件系统；它只是
启动下限，不是最终容量保证，可用 `BRIDGETREE_MIN_FREE_GB` 提高。首次安装若不能
访问包源，应由管理员预置完整 venv 后设置 `BRIDGETREE_SKIP_INSTALL=true`。脚本
拒绝复用非 venv、残缺 venv、危险路径、并发 bootstrap、已有 active run，以及尚
未显式 resume 的 failed/interrupted run；启动返回也必须同时满足
`launch_result=started`、`monitor_ready=true` 和非空精确 run directory。

endpoint 与 generator credential 继续使用 `configs/default.yaml`、同目录私有
`credentials.local.yaml` 或 `BRIDGETREE_CHAT_API_KEY`。仓库和打包文件不包含
私有 key。解包后应在服务器重新创建私有配置，或设置环境变量；不要把 key 加回
交付压缩包。私有配置必须执行 `chmod 600 configs/credentials.local.yaml`；一键
入口会拒绝 group/other 可读的 credential 文件，且不会打印凭据内容。

先做不访问服务的数据预检：

```bash
PYTHONPATH=src python -m bridgetree chain-run \
  --config configs/chain_full.yaml \
  --output-dir outputs/chain/data_check \
  --preflight-only
```

在同一目录正式前台执行：

```bash
PYTHONPATH=src python -m bridgetree chain-run \
  --config configs/chain_full.yaml \
  --output-dir outputs/chain/data_check
```

后台运行：

```bash
bash scripts/run_chain.sh preflight configs/chain_full.yaml
bash scripts/run_chain.sh start configs/chain_full.yaml
bash scripts/run_chain.sh status
bash scripts/run_chain.sh log
bash scripts/run_chain.sh module-log effectiveness
bash scripts/run_chain.sh module-log effectiveness-current
bash scripts/run_chain.sh resume
bash scripts/run_chain.sh stop
```

`preflight` 只冻结并验证数据/计划，不构造模型客户端。`start` 返回并记录精确
run directory，关闭 SSH 不影响 detached worker；`resume`
继续该目录而不是创建新目录。虚拟环境可通过 `BRIDGETREE_BASE_PYTHON` 指定，
状态与输出根目录可通过 `BACKGROUND_STATE_DIR`、`OUTPUT_DIR` 调整。
使用自定义 venv/state/output 时，一键入口在成功输出中给出带绝对路径环境变量的
可复制管理命令，避免新 shell 或重新登录后误用系统 Python。

本次韧性策略同时改变源码身份和正式配置身份；旧 run 的冻结 manifest 因而不能
由新版本 `resume`，身份校验会在模型调用前拒绝它。服务器不得删除或覆盖旧
`outputs/background`、旧 run directory 或 `outputs/cache`。保留它们用于审计，
并让内容寻址的模型缓存继续按自身 key 校验；新版本应使用隔离的后台状态和输出根
启动一个全新 run：

```bash
BACKGROUND_STATE_DIR=outputs/background-resilient \
OUTPUT_DIR=outputs/chain-resilient \
bash scripts/start_chain_linux.sh configs/chain_full.yaml
```

后续管理命令必须带相同变量，例如：

```bash
BACKGROUND_STATE_DIR=outputs/background-resilient \
OUTPUT_DIR=outputs/chain-resilient \
bash scripts/run_chain.sh status

BACKGROUND_STATE_DIR=outputs/background-resilient \
OUTPUT_DIR=outputs/chain-resilient \
bash scripts/run_chain.sh module-log effectiveness-current
```

这里应执行 `start` 创建新 run，而不是把新源码指向旧目录执行 `resume`。

服务器包：

```bash
bash scripts/package_chain_server.sh
```

包中包含源代码、配置、脚本、测试、文档及完整 raw/processed 32k 数据；不包含
`.git`、outputs、缓存、数据准备临时文件和私有 credential。应在最终数据准备与
离线测试通过后再打包；脚本同时生成 `.tar.gz.sha256`，传输后应先核对它。解包后运行上述 data-only
preflight 会再次验证包内 raw 文件和 processed manifest 的固定校验和。

## 9. 主要运行产物

| 产物 | 含义 |
|---|---|
| `run_manifest.json`, `resolved_config.json` | 数据、配置、代码、协议和运行身份 |
| `preparation_identity.json` | manifest 建立前的原子准备身份；支持精确目录中断恢复 |
| `planned_tasks.jsonl` | 模型调用前冻结的完整分母 |
| `outcomes/*.json` | 每任务原子权威状态 |
| `predictions.jsonl`, `failures.jsonl` | append-only 成功/失败尝试历史 |
| `progress.json`, `summary.json`, `completion.json` | 当前覆盖率、失败、pending 与终态 |
| `metrics.csv`, `reports/*.json` | 分方法和角色累计指标 |
| `visible_memories/*.json` | 每题真实可见历史快照 |
| `candidate_pool/*.json` | 初始池、proposal 图、状态、档案和选择结果 |
| `modules/*.jsonl` | 集合分、激活、proposal、状态、停止、选择、上下文和成本原始事件 |
| `modules/effectiveness.jsonl` | append-only 的逐 attempt 模块效果与周期方法指标历史 |
| `modules/effectiveness.current.jsonl` | 从权威 outcomes 原子物化、每个当前 outcome 恰一行的重试安全视图 |
| `train.log`, `events.jsonl`, `heartbeat.json` | 真实推理进度与活动任务 |
| `service_probe.json` | 最新一次执行 attempt 的 pointwise 数值一致性探针快照 |
| `service_probes.jsonl` | append-only 探针历史；每次 attempt 保留成功或失败记录 |

`module_effectiveness` 不包含 gold、答案原文、记忆正文、endpoint 或凭据。它具体记录
可见记忆与候选增量、ANN 配额、逻辑唯一集合、reranker/cache 工作量、单项/pair
交互信号、访问状态与 bundle、动态选择轮次/边际、最终上下文预算、生成调用、正确性、
解析失败、耗时和基础设施失败类型。正 interaction 仍只是冻结评分器上的测量，不是
因果证明；proposal 来源图也明确不是 dependency edge。跨方法共享的同题 memory
embedding 成本由固定执行顺序中的首个方法承担，因此不能直接拿单任务 embedding
成本做方法公平排名。

历史 JSONL 中旧 retry 行只表示 `authoritative_at_write`；审计当前结果必须使用
`effectiveness.current.jsonl`，或只选择与 `outcomes/*.json` 当前 attempt/status 匹配
的行。`method_metrics` 仅基于当前权威 outcome，报告 coverage、成功/失败、parse
failure、成功样本准确率、完整计划分母下界及仅在全任务结束时出现的 final accuracy；
它不是模块成本排名，且会标明各方法已完成 question 集是否可直接比较。

## 10. 验证边界

离线验证使用显式 deterministic fake embedding/reranker/generator，覆盖数学反例、
缓存、乱序索引、预算、输入容量、完整库与固定池差异、连续固定目标、pair rescue、
动态选择及小型真实执行/恢复。机器可读结果见 `docs/validation_report.json`。

本地验证不访问用户部署，也不产生真实 910B QA 结果。因此不能据此声称精度
提升、真实语义交互有效、服务器响应格式已经验证或搜索达到全局最优。服务器
正式运行仍需核对 endpoint 返回格式、数值批次稳定性和真实上下文容量。
