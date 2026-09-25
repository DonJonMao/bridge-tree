# BridgeTree 机制修订
## 从部分运行日志到 Evidence BridgeTree

2026-09-23 · 方法设计与实现说明 · evidence_bridge_v1

本报告把本轮真实日志的机制性问题、近两年顶会工作的启发，以及当前直接实施的修改连成一条可追溯的证据链。新方法同时包含多目标预算调度、条件贡献约束与目标转向、基于信息需求的整体证据选择。

> 核心决定：把“值得继续搜索”“原目标值得保留”“历史证据足以支撑回答”拆成三个决策。相关性 R 保留为搜索代理分数，不再独自决定最终历史证据去留。

| 已有事实 | 本轮行动 | 结果边界 |
|---|---|---|
| 227/257 个成功 activation 任务只访问一个根 | 显式分配开根、深入和中期探索机会 | 多开根不自动等于更准 |
| 9,862 次正 A 中有 382 次目标新边际非正 | 正 A 与正目标边际才进入保留目标的深入队列 | 这些边际仍针对 R |
| 已召回历史理由因负 R 边际被拒绝 | 冻结需求、校验原文引用、整体选择和替换 | 覆盖是模型判断，不是真实效用标签 |

交付由三部分组成：本 PDF 解释依据与改法；docs/evidence_bridge_implementation.md 规定代码接口、预算和验收；docs/evidence_bridge_runbook.md 说明 Linux 一键运行、日志定位和续跑。最终实现审查与测试证据由独立验收记录维护，本报告不预写测试总数。

本轮直接修改方法，不以先得到消融结果为实施前提。采用冻结模型推理，无参数训练、无优化器更新。新增证据推理有独立 LLM 开销；embedding/reranker 超长专项按用户要求暂缓。

<!-- page -->
# 01 · 日志范围与结果口径

分析对象为 bridge_tree_partial_20260922_131127.tar.gz 中的正式运行，不含 smoke 和 regression 子目录。权威来源是逐任务 outcomes，而非导出时稍有滞后的 summary。

| 运行事实 | 数值与解释 |
|---|---|
| 原全量计划 | 589 题 × 5 方法 = 2,945 任务 |
| 已有权威结果 | 1,303 任务；1,281 成功、22 执行失败 |
| 成功输出中的错误 | 479 个按原标签评分错误；不同于执行失败 |
| 当前样本 | 261 题、9 个 persona；剩余 1,642 个任务未有终态 |
| 日志完整性 | 2,964 个 JSON/JSONL 文件可解析；1,659,739 条非空 JSONL 记录 |

| 方法 | 成功 | 失败 | 正确 | 成功准确率 |
|---|---:|---:|---:|---:|
| dense | 261 | 0 | 171 | 65.52% |
| dense_rerank | 261 | 0 | 170 | 65.13% |
| activation | 257 | 4 | 159 | 61.87% |
| context_marginal | 245 | 15 | 148 | 60.41% |
| activation_fixed_pool | 257 | 3 | 154 | 59.92% |

在 dense 与 activation 的共同成功 257 题中，前者 170 对、后者 159 对；activation 救回 19 题、损害 30 题，净差 -4.28 个百分点。性能差距不能全部由 4 个执行失败解释。

这些是按原计划顺序产生的部分结果，persona 相关、失败非随机。不能宣称完整 589 题的最终准确率，也不能把 30 个损害全部归因于检索。已检查的题目用于开发和机制说明，不再视为未见确认数据。

> 归因边界：261 对 dense/dense_rerank 的实际 reader 请求完全相同，但 21 对标签不同、13 对正误不同。另有 1 条 options→(s) 解析错误，以及 9 题存在重复选项正文。这些因素限制答案变化的归因，不否定日志中真实发生的搜索和选择动作。

<!-- page -->
# 02 · 搜索问题是调度和信号语义

三个搜索方法的 759 个成功任务全部耗尽 ANN。通常初始 dense 加桥接探测使用 13/36 次，剩余 23 次条件检索。未访问根 priority=0，正后继优先，因此既有目标很容易持续得到预算。

| 方法 | 仅访问一个根 | 比例 | 平均根覆盖 |
|---|---:|---:|---:|
| activation | 227/257 | 88.33% | 5.68% |
| context_marginal | 244/245 | 99.59% | 4.77% |
| activation_fixed_pool | 220/257 | 85.60% | 5.88% |

activation 平均约有 21.91 个初始根；首根仅 13/257 题是 dense 第一名。根平局使用 memory ID 词典序，并不等于相关性排序。这是队列规则的预期行为，不是 heap 写错。未展开为 target 的记忆仍可能作为 premise 被看到。

令 P 为前提、e 为目标、G 为新前提组：

> M_before = R(Pe) - R(P)；M_after = R(PGe) - R(PG)。A = M_after - M_before。A 为正只说明目标边际改善，不说明改善后的边际已经为正。

真实例：qid ca958afd-7fb1-497b-9234-735115cc3813，e=m02，G=m21，P 为空。

| R(P) | R(Pe) | R(PG) | R(PGe) |
|---:|---:|---:|---:|
| 0.03358950 | 0.00251636 | 0.55832699 | 0.53898322 |

M_before=-0.03107314，M_after=-0.01934377，A=+0.01172937。目标“少拖一点后腿”就获得正信号，仍不如只保留 G。

257 个成功 activation 任务共有 48,960 次完整测量、9,862 次正 A；其中 381 次目标新边际为负、1 次为零，占正 A 约 3.9%。不能仅过滤这部分就声称解决了普遍的单根垄断。四项差分算术本身已复核，无计算缺陷。

<!-- page -->
# 03 · 已召回的历史为什么被丢掉

当前 R 被明确标记为 legacy_query_relevance，并未验证为回答效用或充分性。让这个分数同时决定搜索、集合增加和停止，会偏向“与 query 相似”，而非“补上 query 缺少的历史”。

### flashcards：理由就在候选池里

qid dbbd6663-a17f-4b84-8579-6d39ad99c738。dense 第 4 条 m36 记载用户过去认为 flashcards “weren't conducive to deep learning”。最终却只选 m94，其用户正文与当前 query 同文。

| 已测集合 | R | 选择含义 |
|---|---:|---|
| {m94} | 0.9996170364 | 当前表态高度匹配 |
| {m94, m36} | 0.9974090206 | 加历史理由后边际 -0.0022080158，因此被拒绝 |

dense 答对而三个搜索方法答错。这是历史被真实拒绝的证据；单次答案差异仍不足以证明 m36 是唯一因果因素。painting 原因题同样已召回 m39，却因 -0.000857374829 的增量被拒绝。

### 已测组合也有归档缺口

77/257 个成功 activation 任务存在已经测到、生成预算可行、R 更高但未最终选择的集合。它们主要是缺少原 target 的 P/PG，没有作为完整 bundle 入 archive。例 e12b0c88-fa61-410f-acd7-2cfeda5a365a：最终 {m04,m11} 的 R=0.187133，已测 {m11,m79} 为 0.622459，完整生成输入估算 1,012 tokens。

| 类型 | 本轮处理 |
|---|---|
| 完整已测集合遗漏、options 误解析 | 实现层修正与诊断；不包装成新算法收益 |
| 单目标优先、固定 e、只加不删、R 作为证据效用 | 三个方向的机制修改 |
| embedding/reranker 物理超长 | 本轮暂缓，失败保留原有边界 |

更高 R 不等于更好答案：上述 77 题中有 44 题原答案本来就正确。query 回声也不是一律有害：只选回声的 16 题仍有 14 题答对。新方法不强制“多留历史”，而是说明留下哪段历史以及依据。

<!-- page -->
# 04 · 2025-2026 顶会的可借用机制

正式录用身份以官方会议页或 ACL Anthology 核验；借鉴局部方法，不将别的数据集收益迁移成本项目结论。

| 论文与会议 | 本轮借用 | 必须保留的区别 |
|---|---|---|
| [1] SETR · ACL 2025 主会 | 回答所需信息 → 证据映射 → 整体集合选择 | 正式 SETR 有教师标注蒸馏训练；本实现为冻结 LLM 提示推理 |
| [2] AB-MCTS · NeurIPS 2025 | 把生成新分支与深入已有分支分成动作 | 不复制依赖可靠评价器的奖励后验或搜索保证 |
| [3] BG-MCTS · ICML 2026 | 剩余预算进入策略，保留前期覆盖和后期深入 | 数学推理中的深度和 token 成本不等于记忆条数、ANN 或集合评分 |
| [4] REMem · ICLR 2026 | 历史事件与矛盾事实按时段共存 | 不采用 latest-wins；观测顺序不能冒充事件时间 |
| [5] MRAgent · ICML 2026 | 新找到的内容可以引出新的检索线索 | 支持有限 target pivot 的启发；其原方法证据累加不是删除/替换依据 |

本轮没有直接套用整套 MCTS 或图记忆重建。当前最明确的结构限制是开根没有机会、目标永久固定和已召回证据被旧相关性边际否决。针对这些限制修改，能够保持问题与代码动作的对应。

条件贡献研究也提示评价目标的重要性：SCARLet 和 InfoGain-RAG（EMNLP 2025 主会）使用 gold-answer 条件反馈及训练过程，不能直接搬进答案不可见的在线检索。先猜答案再优化其概率，同样可能只强化初始猜测。

> 本方法的边界：保持无参数训练，允许检索阶段新增 LLM 推理；不把输出 0-1、pointwise 一致性或四项交互宣称为语义效用校准。完整文献核验与方法细节见研究报告，官方链接列于末页。

<!-- page -->
# 05 · 完整方法与信息边界

正式方法名为 evidence_bridge，默认与 dense、activation 一起运行。以下流程是一套完整方法；三个方向均接入实际任务执行器，而非独立示例。

| 步骤 | 实际输入与动作 | 产物 |
|---|---|---|
| 1. 需求规划 | 只读原 query；不看候选、选项或 gold | 最多 6 项冻结信息需求 |
| 2. 初始召回 | 原 query dense 与桥接提案；仅 cutoff 内历史 | 初始可见候选池 |
| 3. 多目标搜索 | 覆盖/深入/探索调度；原 R 四项测量 | 所有完整已测集合、候选和来源 |
| 4. 全文证据映射 | 所有已发现候选全文分片；原文引用校验 | 需求-证据表、角色/阶段/推断标记 |
| 5. 整体选择 | 完整映射表；允许删除、替换和缺失 | 整体原始记忆 ID 集合 |
| 6. 缺口反馈 | 未覆盖必要需求触发最多 2 次预算内 ANN | 新候选重映射、重新整体选择 |
| 7. Reader 与评估 | 可行原始记忆 + 原公开选项；生成后才读 gold | ContextPlan、真实请求、答案与结果 |

时间边界在任何 embedding、评分或 LLM 推理之前应用。原始记录新增 authoritative source_segments，保存真实说话人和 Memory.text 字符区间；用户正文中出现 “Assistant:” 不会改变其实际来源。

选择器不接收 example 对象。它需要 reader 输入预算时，只调用 feasibility callback，得到可行性、token 数、预算和 hash，不读取选项文本。最终 reader 接收原始记忆，不以规划器撰写的解释替换证据。

原始 R 始终用原 query 评分。冻结需求可进入条件提案和缺口查询，但不能将 LLM 猜出的答案当成检索事实。公开选项仍只在最后 reader 阶段使用。

> 这套信息边界把证据选择的新增推理成本与最终答案生成分开，也避免把答案侧信息回流成检索优势。

<!-- page -->
# 06 · 方向一：双预算多目标调度

新 EvidenceBridgeSearcher 复用原检索与集合评分协议。开新根和继续已有目标是不同动作，不再让所有未访问根永久与正后继争同一个零优先级入口。

| 资源/动作 | 当前默认规则 |
|---|---|
| 总 ANN | 36；其中最多 2 次预留给证据缺口反馈 |
| 搜索评分 | 512 个题内唯一逻辑集合；暖缓存仍计额度 |
| 前期覆盖 | 最多 6 个不同根得到明确工作机会 |
| 中期探索 | 最多 4 个新根或新线索机会，中途释放 |
| 每个工作片 | 至多 1 次新 ANN、24 个新集合、8 个完整四项测量 |
| 连续使用同目标 | 默认最多 2 片；无可用替代目标时可解释地放宽 |

通常初始 13 次 ANN 后剩 23 次，典型额度约为 6 次覆盖、11 次深入、4 次中期探索、2 次缺口反馈。实际按可用根、已花预算和待测工作缩放；中期额度释放后共同使用剩余搜索预算，不是不可互借的固定分区。

代表根保留 dense 首位，之后基于已有 embedding 最远优先选取不同语义方向；精确平局确定性处理。配置 root_selection=discovery 可使用发现顺序。代表性只改变比较机会，不宣称远离已有根的候选一定有用。

工作片同时限制 ANN 和新集合，避免“虽只发一次 ANN，却扫描整个 initial_pool”。工作区保留已取得 proposal、singleton/pair 序列与游标。再次轮到该状态时继续测量，不重复 ANN。即使新集合已缓存为 0 开销，也仍受 8 次完整测量限制。

每状态至多 6 对 pair，与 singleton 交错获得机会。任何正 singleton 不再自动关闭 pair；没有测完也不能宣布所有 singleton 非正。四项评分缺预算时不拆开构造 A。

ANN 用尽后，已取得 proposal 的待测项目仍可在剩余集合预算内执行。停止事件说明究竟是资源耗尽、可行域限制还是工作队列已空。每片记录 phase、动作、目标、前后预算、游标和切换原因。

<!-- page -->
# 07 · 方向二：探索、留存与转向分离

每条完整测量记录四个 R、A、目标旧/新边际和前提边际。默认 epsilon=0，保留原有数值语义；不把任意更大的阈值包装成经验证的语义容差。

| 测量条件 | 后续动作 | 解释 |
|---|---|---|
| A>0 且 M_after>0 | retain：进入保留原目标的深入队列 | 原目标在新条件下对 R 有正贡献 |
| A>0 但 M_after≤0 | speculate：仅有界探索 | 不把暂时负贡献永久剪掉，也不无限续费 |
| PG 优于 PGe | pivot：可选 G 中新 target，前提变为 PG 去掉新 target | 旧 e 不再被强制携带 |
| 无有效后继或预算不足 | reject / pause / stop，记录具体原因 | 未完成测量不当作负值 |

speculation 默认最多 8 个状态、深度 2。pivot 默认最多 4 次、每条路径深度 2；状态去重和 target_path 防止 e→g→e 循环。外部新发现可以晋升为新根，同样受预算与晋升额度约束。

全量已测集合归档属于必要的完整性修复：非空 P、Pe、PG、PGe 只要真正完成评分，就作为整体集合保留，不依赖 A 正负。跨物理 batch 失败前已返回的真实得分也保全；缺分集合标为 incomplete，不猜值，不伪造四项交互。

> 对 flashcards 类问题，这个方向还不够。即便删除了负贡献 target，只要 R 仍排斥历史理由，最终语义问题仍存在。因此目标控制与下一页的信息需求选择必须同时工作。

调度日志区分 pivot 尝试、成功入队和拒绝原因。汇总的 pivot_count 只计实际 queued 的转向；探索动作是否后来被执行，还可通过目标成本与工作片事件核对。最终证据集合不必沿搜索路径单调增长。

本轮不声称所有负目标都应删除。多步互补、阶段性歧义和评分代理失配仍可能存在；有限试探与可追溯日志保留了后续定位这些情况的依据。

<!-- page -->
# 08 · 方向三：有出处的需求覆盖与集合修订

SETR 的信息需求-证据映射-整体选择流程被适配为无参数训练的冻结提示过程。需求先 q-only 生成并冻结，避免看完候选后再改变“需要什么”的标准。

### 先保证每条候选真的被读过

所有发现的真实候选都进入映射，包括负 A 分支或未进入正后继的记忆。长记忆按字符范围分片，不截尾、不 top-k 丢掉映射表。exposures 记录 memory ID、unit ID、start/end、来源角色与完成状态，区间必须覆盖全文。

LLM 引用必须是实际传入原文的连续子串，由代码验证全局 offset 与真实说话人。映射保存 requirement_id、memory_id、quote、explicit/inference、support/contradiction/partial、阶段和时间说明。跨多条事实的推断允许存在，但不能伪装成用户原话；顺序不是因果，未知时间不猜测。

### 整体选择可以撤销之前的决定

选择器读取全部有效映射，输出原始 selected_ids，以及每项需求的 covered/partial/missing/ambiguous、引用和解释。covered 必须有有效支持，而且支持所在记忆必须在最终集合中。仅由 partial 证据联合覆盖时，至少需要两条映射且标为 inference；来源检查不能证明语义正确。

对缺失或部分覆盖的必要需求，最多 2 次 targeted ANN 使用原总预算。必要需求全部覆盖时可停止反馈，可选需求的缺失仍如实保留。新候选必须重新映射，再对整个集合重选。每轮记录 added_ids、removed_ids 与覆盖变化。旧观点和新观点可按不同历史阶段同时保留，不默认 latest-wins。

| 推理额度 | 当前默认 |
|---|---|
| 整题证据 LLM 逻辑调用 | 最多 24 次，包括规划、映射、选择和修复 |
| 输入估算上限 / 映射批上限 | 16,384 / 6,144 tokens |
| 单次输出上限 | 4,096 tokens，与 reader max_tokens 独立 |
| JSON 修复 / reader 预算修订 | 整题最多 1 次 / 最多 2 次 |

ContextPlan 对完整原始记忆集合检查预算。超限只能整体修订，不事后静默截断。非法引用、未知 ID、调用耗尽、全映射表超输入预算或最终不可行都产生 typed error 和部分 artifact，不静默回退旧选择器，也不把失败写成成功。

<!-- page -->
# 09 · 日志要能解释模块反应

仅看正确率无法知道预算、证据和 reader 哪一环出了问题。新版按关键事件持久化简短模块日志，并保存包含完整原文、请求与响应的任务级快照。

| 层级 | 路径与用途 |
|---|---|
| 实时事件 | modules/planner、scheduler、target、archive、evidence、feedback、selection.jsonl 等；record_kind=live |
| 完整实时快照 | evidence_live/<task_id>.json；每关键事件更新，保留已有需求、请求、映射和修订 |
| 任务结案 artifact | candidate_pool/<task_id>.json；search 与 evidence_selection 全过程 |
| 追加结案事件 | modules 中 record_kind=task_snapshot；可能与 live 重复表达同一动作 |
| 权威结果 | outcomes/<task_id>.json；当前 attempt、成功/失败、预测、成本、模块摘要 |
| 当前汇总 | effectiveness.current.jsonl 与 summary 命令；不累加重试历史 |

建议顺着一条错误的 task ID 检查：是否有根覆盖机会 → 是否真实召回 → 是否完整归档 → 是否全文映射 → 引用/角色是否通过 → 为何整体选入或删除 → 缺口 ANN 是否带来新证据 → 最终原文是否进入 reader。

关键指标包括 initial_root_coverage、max_target_ann_share、phase 预算、成功 pivot 和拒绝原因；还包括 evidence_unmapped_candidates、evidence_validation_failures、各需求状态、预算修订和缺口反馈次数。删除数量只累计实际接受的集合改变，不能把被拒绝 proposal 重复当作已删除。

新增 LLM 费用通过 evidence_llm_calls、evidence_calls_by_operation、输入/输出 token estimate、elapsed_ms 单列；最终 reader 调用另计。逻辑 ANN/集合额度、缓存命中和物理 HTTP 重试分别记录。估算 token 不冒充服务端真实 tokenizer 计数。

> 汇总规则：一任务一份当前 authoritative outcome；缺字段保留缺失，不当作 0。live 和 task_snapshot 都是事件历史，不能直接按行数求准确率或成本。中断/失败保存已完成步骤，但未完成判断不转为负值。

相同 payload 的输出变化、重复选项、时间指代歧义继续作为诊断因素保留。covered 不是 gold evidence recall，也不是回答因果贡献；R 变高、访问更多根、生成更短上下文都不能独立证明方法更好。

<!-- page -->
# 10 · Linux 运行与后续观察

默认完整配置运行 dense、activation、evidence_bridge，共 589×3=1,767 任务。包内含固定数据、源码、设计、运行文档及本 PDF；排除本机凭据、缓存、旧 outputs 和 macOS 虚拟环境。

| 步骤 | 项目根目录命令 |
|---|---|
| 本机打包 | bash scripts/package_evidence_bridge.sh |
| Linux 一键启动 | bash scripts/start_evidence_bridge_linux.sh |
| 查看状态 | bash scripts/run_evidence_bridge.sh status |
| 查看主日志 | bash scripts/run_evidence_bridge.sh log |
| 查看模块 | bash scripts/run_evidence_bridge.sh module-log evidence |
| 汇总当前结果 | bash scripts/run_evidence_bridge.sh summary |
| 停止 | bash scripts/run_evidence_bridge.sh stop |
| 续跑 | bash scripts/run_evidence_bridge.sh resume |

首次启动安装远程推理依赖，先做零模型调用的数据预检，再由 detached monitor 启动 worker。关闭 SSH 不会停止实验。服务覆盖通过 BRIDGETREE_DEPLOYMENT_CONFIG，密钥在服务器使用环境变量提供。完整命令与字段说明见运行文档。

resume 继承原 run 目录、配置和部署覆盖，验证源码/数据/配置 identity。已成功任务跳过，失败和待运行任务重跑；中断任务从任务边界重启，不假装恢复搜索 frontier。修改方法或模型必须新开 run。monitor 正常退出后仍检查 completion.json，确认是否 completed_with_failures。

下一轮日志直接回答三个问题：不同目标是否获得预算且产生可用证据；负目标是否被有界探索或实际转向；已召回历史是否通过有出处的映射进入最终集合。先看模块因果链，再结合原标签准确率、任务成功覆盖及总开销判断，不用代理指标代替最终结果。

本地已完成方法边界与故障测试、实际执行路径的模拟验证、后台进程生命周期检查及全套回归。这里的模型后端使用受控替身；没有运行新版远端模型评测，也没有新的准确率结论。具体源码与测试证据见最终验收记录。

<!-- page -->
# 11 · 文献与审计索引

以下为本轮采用的主要正式录用论文。来源负责支撑局部机制选择；预算参数、与 PersonaMem 的适配及实际实现属于本项目设计，不能视为论文已证明的结果。

### 主要文献链接

[1] SETR，Shifting from Ranking to Set Selection for Retrieval Augmented Generation，ACL 2025： https://aclanthology.org/2025.acl-long.861/

[2] AB-MCTS，Wider or Deeper? Scaling LLM Inference-Time Compute with Adaptive Branching Tree Search，NeurIPS 2025： https://neurips.cc/virtual/2025/poster/116491

[3] BG-MCTS，Aligning Tree-Search Policies with Fixed Token Budgets in Test-Time Scaling of LLMs，ICML 2026： https://icml.cc/virtual/2026/poster/63795

[4] REMem: Reasoning with Episodic Memory in Language Agent，ICLR 2026： https://iclr.cc/virtual/2026/poster/10008195

[5] MRAgent，Memory is Reconstructed, Not Retrieved: Graph Memory for LLM Agents，ICML 2026： https://icml.cc/virtual/2026/poster/60697

### 项目内可复核材料

| 材料 | 位置与作用 |
|---|---|
| 原版日志审计 | outputs/partial_audit_20260923/REPORT.md；含逐任务统计、语义案例与离线复算索引 |
| 近两年文献调研 | reports/2026-09-23-mechanism-research/REPORT.md；官方录用核验、论文方法与适用边界 |
| 本轮实现契约 | docs/evidence_bridge_implementation.md；接口、预算、失败、日志与逐项验收要求 |
| Linux 运行说明 | docs/evidence_bridge_runbook.md；部署、启动、日志、停止恢复和聚合命令 |

本 PDF 记录设计依据，不宣称已完成新版远端模型评测或已取得准确率提升。原始归档保留不覆盖，新方法使用独立配置、输出目录和 run identity。实施后的准确率、稳定性和费用只能由新的真实运行日志确认。
