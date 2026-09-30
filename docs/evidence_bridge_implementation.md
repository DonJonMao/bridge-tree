# Evidence BridgeTree 方法修改设计与验收文档

版本：2026-09-30 / evidence_bridge_v3。本文是当前实现契约；本轮详细计划见 [v3 修改计划](evidence_bridge_v3_plan.md)，实测验收见 [v3 验证记录](evidence_bridge_v3_validation.md)。用户要求直接完成方法修改，本方法仍使用冻结模型推理，没有参数训练；服务器的一键“实验”指完整数据集推理评测。

v3 根据真实日志修正个性化需求定义，为 dense 召回原文提供独立复核资格，保守派生覆盖类型，并增加紧凑修复和透明的覆盖未评估完成状态。没有改变搜索调度、A 算术和 reader 预算；不能把 v2/v3 混入同一个 run。

## 1. 目标与交付

- 2026-09-23 PDF 保留为 v1 机制背景；v2 引用协议、局部恢复与预算截断以本文及可靠性修订记录为准。
- 本文：三个方向的算法、接口、预算、日志、异常及逐项验证要求。
- 正式新方法 `evidence_bridge`，接入现有 `chain-run` 数据、任务计划、reader 和评估流程，不能停留于孤立 demo 或 fake 分支。
- 保留 legacy 方法用于复现；新版完整方法默认打开三个方向，不能默认退回旧 R 选择器。
- Linux 打包、一键后台启动、状态/日志/停止/恢复及训练运行文档；任务结束或失败有明确终态，续跑不重做已成功任务。
- 以真实实现、代表性机制测试、端到端执行和逐项源码审查证明完成；不把本地测试冒充服务器模型准确率。

## 2. 日志依据与文献来源

归档 `bridge_tree_partial_20260922_131127.tar.gz` 的权威 outcomes 为 1303 个，1281 成功，479 成功输出按原标签错误。成功 activation 257 题中，227 题仅访问一个根；9862 次正 A 中 382 次目标新边际非正。已测但未整体归档的更高 R 集合存在于 77/257 题；高 R 不等于答案更正确。flashcards 与 painting 案显示相关历史已召回但被最终负 R 边际否决。相同 reader payload 仍会有不同输出，不能将所有正误变化归因于检索。embedding/reranker 超长专项按用户要求暂缓。

采用的局部机制：SETR (ACL2025) 的信息需求-证据映射-整体集合选择；AB-MCTS (NeurIPS2025) / BG-MCTS (ICML2026) 的开新分支与深化动作、预算进入策略；REMem (ICLR2026) 的有时间情境的历史共存；MRAgent (ICML2026) 的新内容引出新线索。SETR 正式模型有蒸馏训练，本实现采用冻结 LLM 提示流程。没有复制论文的训练收益、统计保证或吞吐数字。详见 `reports/2026-09-23-mechanism-research/REPORT.md`。

## 3. 完整数据流与信息边界

1. 载入当前题 cutoff 内原始记忆，构建真实说话人原文边界，禁止未来历史或派生未来摘要。
2. 用一次 q-only LLM 调用生成至多 6 条个人历史需求；输入只有 query 和个性化任务说明。用户近况不自动变成名称/日期/地点查询，推荐任务接受用户偏好作为依据而非要求原文已有推荐答案。需求冻结，记录原始响应及校验结果。
3. 复用原 query dense/bridge 初始池。条件 proposal 可携带冻结需求，原 R 始终对原 query 评分，不把 R 重命名为效用。
4. 运行多目标双预算搜索，保存每个完整测量集合；目标边际约束深入资格，有限 pivot 可以脱离旧目标。
5. 将全部已发现候选（不只正后继）全文划分为来源片段；按调用与输入预算分批映射。有限恢复后失败/未评估片段明确记为 unavailable，不冒充无关。已有合法证据的记忆可继续参与选择。
6. 按 dense 相同规则构造预算可行 baseline 原文。启用 raw_memory_review 时先在选择输入中展示这些完整原文，再从已校验证据表按必要需求、记忆轮转填充预算。可选范围是可见原文与可见映射的并集；零映射不再自动淘汰已展示原文。仍允许删除/替换，不强制全留 dense，不创建虚假 coverage。
7. 尚未覆盖的必要需求可使用预留最多 2 次 ANN 发起有针对性的检索；新增候选必须经过同样映射，再重新整体选择。循环有确定预算和终态。
8. ContextPlan 检查最终原始记忆集合；必要时在有限次数内整体修订。最终 reader 只收到原始 Memory，和原有公开选项；预测产生后才能读取 gold。

证据 planner/mapper/selector 不接收 example 对象、任何答案选项或 gold。最终输入可行性通过 callback 提供布尔值、token 数和预算，不把选项文本返给方法。严格区分用户事实与助手建议、明示事实与跨多条证据推断；时间未知保留 unknown。

## 4. 方向一：双预算、多目标、可暂停调度

实现 `evidence_search.py:EvidenceBridgeSearcher`，复用 `SetReranker`、`DependencyRetriever` 和原状态/测量数据结构，不改动原四项评分算术。

- 初始根来自可见 initial_pool。默认以 dense 第一名为首，再按已有 embedding 的最远优先选代表根；确定性 tie-break。`root_selection=discovery` 可复现发现顺序，不依赖 memory ID 年代偏置。
- 前期为 `coverage_roots=6` 个根明确分配工作；剩余资源进入深入；中期释放 `exploration_roots=4` 个新根/pivot 机会。按实际可用根与 ANN 缩放，不能超发。
- 总 ANN 仍 36，搜索逻辑集合仍 512。预留 `gap_ann_calls=2` 给方向三，因此通常 23 次条件 ANN 中约 6 覆盖、11 深入、4 中期探索、2 缺口检索。数字是方法配置，不是论文保证。
- 搜索本身同时预留后续阶段的集合额度，防止初始几个根耗光 512。最终证据选择 LLM 的调用与 token 独立计数，不假装属于原 selection 512 次 R 预算。
- 一个 quantum 最多 1 次新 ANN、24 个新计费集合、8 个完整四项测量。工作区缓存 proposal 和测量游标，恢复不重复 ANN；即使新集合为 0，测量数上限仍约束执行。
- 同一目标默认最多连续 2 个 quantum；只有没有可执行的替代目标时才放宽，发出 `target_fairness_relaxed/no_alternative_target`，避免丢弃最后一个已取得 proposal 的待测工作。未访问根不会永远与正后继在同一零优先级 heap 竞争。
- ANN 耗尽时仍可测已取得 proposal 的未完成候选；没有取完初始 singleton 不能宣布“全部非正”。没有完整四项预算时不拆测量、不生成 A。
- pair 宽度复用 dependency.pair_rescue_width；每状态至多 6 对，和 singleton 交错。pair 不受“任何 singleton 为正”阻止，也不等整个 initial_pool 扫完才获得机会。
- 同题唯一集合计费沿用当前规则，跨任务暖缓存仍收费。每个工作片必须记录前后 ANN/集合数、phase、目标、游标、待测项、切换原因和完成度。

预算分配的准确规则：设初始检索后剩余搜索 ANN 为 B（已扣缺口预留）、初始根数 N、新集合总额度 S、每片新集合上限 Q。B>0 时 C0=min(coverage_roots,N,max(1,floor(B/2)))，否则 C0=0；E0=min(exploration_roots,floor((B-C0)/3))；Z0=min(floor(S*reserve_score_fraction),E0*Q)；E=min(E0,floor(Z0/4))；Z=min(Z0,E*Q)。生产任务搜索从零计费开始，实际前期覆盖 C=min(C0,floor((S-Z)/4))。先将 Z 个集合额度留给中期 E 个机会，前期每个尚未轮到的根再保留 4 个集合，保证四项测量的最小资源。每片评分上限同时取总上限、阶段可用上限和“已计费+Q”的最小值。

典型 B=21、S=512、Q=24 时，C=6、E=4、Z=96，中期释放前最多计费 416 集合。覆盖结束后，ANN 或集合两种深入额度任一使用比例达到 exploration_fraction=0.5 就释放中期探索；没有可执行深入工作或公平切换需要新目标时可提前释放。释放后剩余额度共享，6/11/4 是典型分配，不是不可互借的三个硬 ANN 子预算。已取得 proposal 不因 ANN 耗尽而丢弃，但始终不能借用证据缺口预留的 2 次 ANN。小预算下相应缩减根机会，无完整四项资源时不新发搜索 ANN。

## 5. 方向二：激活、目标留存与转向分离

设 M_before=R(Pe)-R(P)，M_after=R(PGe)-R(PG)，M_group=R(PGe)-R(Pe)，A=M_after-M_before。

- 每个完成测量均记录四个 R、A、两个目标边际和前提边际。
- `A>epsilon && M_after>epsilon` 才进入保留目标的深入队列；epsilon 默认 0，不宣称任意阈值为语义有效性校准。
- 正 A 但目标非正可以进入有限探索队列；默认最大 speculative 深度 2、状态数 8。不能把阶段性负贡献永久剪掉，也不能无限续费。
- 当 PG 优于 PGe，允许选 G 中新目标，前提为 PG 去掉新目标；旧 e 不再强制携带。最多 4 个 pivot、每路径深度 2；状态与路径去重防 e→g→e 循环。外部新发现可晋升为新根，受同一预算与晋升额度约束。
- 所有成功评分的非空 P/Pe/PG/PGe 完整入 archive，不依赖 A 正负。评分跨 batch 失败前已经返回的真实集合也通过公开 measured-set 快照保留；缺项只能标 incomplete，不能推断 A。
- 搜索返回与旧 archive 兼容的 `.bundles/.activations/.state_records/.proposal_batches/.stop_reason/.public_dict()`，并补调度、target transition、候选来源和部分完成信息。任务重启按既有任务级重跑，不伪造 frontier 精确断点续算。

## 6. 方向三：冻结需求、来源证据映射、可修订集合

实现 `evidence_selection.py`。settings 来自 `EvidenceSelectionConfig`；实际服务 backend 使用 `complete_evidence_messages(messages, *, operation, max_tokens, response_format, json_schema)->dict`，保留原始 content、finish_reason、refusal、usage、response_id、protocol。测试/旧后端可提供 plain 模式的 `complete_messages(...)->str`，元数据缺失记为 unknown。此接口使用冻结 generator 配置对应的聊天服务，独立标记为 evidence 调用，不冒充 reader 调用。

### 6.1 数据与接口

`EvidenceSelector(backend, settings, *, generation_feasible, event_sink=None)`：

- `.plan(query)` 返回冻结需求，每项有 ID、需要的信息、必要性和所需阶段/时间说明；至少一项为必要需求，schema 严格校验，无答案选项。
- `.select(query, records, candidate_ids, *, baseline_ids=(), requirements=None, expand=None)` 返回 `EvidenceSelectionResult`，包括 selected_ids、requirements、原文映射、coverage、events/costs、stop；已有 plan 不重复调用。baseline 必须来自同题可见已发现候选。
- `expand(missing_requirements, selected_ids)` 只返回可见真实候选 ID，调用次数受 gap ANN 总额度限制。新候选必须映射，未有新 ID 有明确终止事件。
- `.partial_public_dict()` 在异常后仍可取得已完成需求/映射/候选暴露/选择修订/费用和失败原因。
- 结果可通过 `.public_dict()`、`.steps` 和 `.stop.public_dict()` 接入当前 executor，不改变最后 ContextPlan/reader 请求。

### 6.2 原文与来源

`messages_to_memories` 新增 authoritative `metadata.source_segments`，每段含 role、start、end、source_message_indices，offset 指向 Memory.text 实际内容。旧记录缺少可靠边界时允许 unknown，不凭模糊的 User/Assistant 标记宣称用户明示。

代码沿权威说话人区间和句段边界划分不超过 `max_quote_chars=400` 字符的稳定 span。所有字符均有来源位置，包括结构性 unknown 间隙；超长句再分片，不改变原文。source hash、原文偏移、角色、消息索引和相邻 span ID 均保留。正文中的角色字样不能覆盖权威元数据。

模型返回 `requirement_id、span_ids、claim、kind、relation、time_scope`，不复写 quote。每项 assessment 必须引用所属 unit，其他引用只能来自本次实际可见的同一 memory。代码从 span 原文构造 `fragments`，每片保存准确 quote/start/end/role/premise_group_ids；未知、不可见、跨 memory、空白引用拒绝。一个 assessment 可包含多个片段，以保留否定或时间条件，不将其拼接为伪造的连续引用。

`fully_mapped_ids` 表示全部 unit 成功评估；`eligible_memory_ids` 表示已有合法来源证据，并非最终可选 ID 的完整集合。`raw_review_ids` 是本轮实际展示的 baseline 原文，即使无映射也可选择。原文保留 text、权威 source_segments 与观测顺序，不把助手建议变成用户事实。未评估不等于 irrelevant，来源验证不等于语义支持验证。

局部映射修复保存有效 assessment，仅请求失败 unit/assessment；修复保留必要的可见原文 context_units。失败或额度不足只影响对应片段，完整 ledger 留在 artifact。raw_memory_review=false 提供独立消融；最终 reader 仍只接收所选真实 Memory。

### 6.3 整体选择与缺口反馈

选择器读冻结需求、本轮实际展示的已验证映射和完整 baseline 原文，选择有助个性化回复的集合。直接复核原文时，不将 mapper 的未映射等同无关。输出各需求的支持 IDs 和 covered/partial/missing/ambiguous。覆盖引用仍只能来自已验证、同需求且属于最终 ID 集合的 ledger；单凭选中了原文不能创建 covered。

覆盖依据保存为 `coverage_basis`：mapped_support、inference_with_mapped_support、joint_inference 或 unresolved。引用中存在 inferential fact 时，模型声明的 explicit 由代码保守降为 inference；两个独立 partial 的联合覆盖同样规范化为 inference。记录 declared_kind、有效 kind 和 normalization_reason。不会把 inference 升级为 explicit，不改变 status/relation 或制造 support。单 partial、contradiction、重叠片段不能伪造联合支持；同一 memory 支持不同需求时仍需对应映射。引用与结构校验不代替语义真值验证。

允许引用互相矛盾但属于不同阶段的事实，不默认 latest-wins；同文 query 记忆不一律删除，它只是不能无依据填补历史原因。

在必要需求为 missing/partial/ambiguous 时可调用 expand：以未覆盖的必要需求发起 targeted probe，最多 2 次 ANN，不另开超预算通道。必要需求全部覆盖、但可选需求仍缺失时，以 necessary_requirements_covered 明确终止，不消耗缺口额度。重新映射新候选并进行整体选择。已选集合可删除/替换任何旧项，日志记录每轮 added_ids/removed_ids 与覆盖变化。

最终用实际 generation_feasible 检查。超 reader 预算允许最多 2 次整体修订，不能事后静默截断 selected_ids。最终没有证据可明确输出空集合和缺失覆盖，但必须真实记录为 evidence_state=empty；不因模型格式错误静默回退 dense 或旧 R。

### 6.4 推理预算与失败

默认 query-only planning、映射、整体选择和有限反馈/修订共享 `max_llm_calls=24`。每逻辑请求最多 2 次局部修复、整题最多 6 次修复；输出明确截断的映射批次优先拆小，重分批仍计入 24 次总调用。映射为最终选择、剩余 reader 预算修订及最多两次覆盖修复预留调用，同时保留相应全局 repair 额度。输入预算 16384、映射批预算 6144、输出上限 4096；这些是确定性估算预算，不是物理 tokenizer 保证。保留实际服务 usage 供分析。

响应格式单独配置为 plain/json_object/json_schema，默认 plain，不假定兼容服务支持 schema；实际协议进入运行身份。启动前对配置协议执行一次真实 planner 预检，无静默格式回退。reader 不继承 evidence 的格式限制。解析器只接受完整唯一 JSON 对象及确定包装，拒绝缺尾、重复键、非有限值和多个竞争对象，不自动补字段/括号。仅 `finish_reason=length` 明确认定服务输出截断，其余记录实际类别。

选择输入按完整原文/ledger 记录裁至预算，仍保留 selection_input_margin=256 作为额外余量，不再假定该常数足够容纳完整修复。先按 dense 原排名容纳完整 baseline 原文，再轮转必要/可选需求的完整 ledger 记录。超长记忆作为整条省略并记 omitted_raw_review_ids，不切割原文或序列化 JSON。候选清单、成本、短别名同步；固定 query/需求/格式仍超限时明确失败。

选择请求使用按需求分组的短别名，artifact 保存别名到稳定 evidence ID 的映射。只允许引用该请求可见证据。覆盖行修复冻结已验证 coverage 和 selected_ids，仅重做失败需求；修复输入仅含 pending 需求与所选记忆的合法相关 ledger，不重发全部原文/候选成本。实际附加反馈后再次检查预算，仍超限明确记为 repair 输入超限。reader 预算拒绝则是新的整体选择，可以删/换集合。

启用 allow_unassessed_coverage 时，仅有合法选集 header 且恢复失败局限于覆盖说明的任务，可以继续 reader 容量检查：保留有效 coverage 行，其余内部标为 unassessed、kind=unknown、validation_complete=false，记录原错误。不会虚写 missing/partial/covered，也不会因未验证的 coverage 再发起 gap。选集未知 ID、非法 header、全局 JSON 不可解析、拒答和服务失败仍明确终止。

每次选择记录截断前后 tokens、原文/证据可见与省略 IDs、baseline 保留率、候选去向和恢复状态。新增 reliability_status=coverage_unassessed，原部分映射/截断布尔值仍保留；其他四类完成状态不变。另按 evidence_state=empty/mapped_only/raw_only/mixed 及 coverage_validation_complete 汇总。normal 不等于证据充分。最终 reader 读取所选原始 Memory，不在这里截断原文。

这是 v3 方法变体：它改变了 v2 的映射资格硬门控和覆盖注释失败行为，不能称为纯兼容修复。搜索调度、A 算术、retain/pivot 及 reader 任务保持不变。旧 embedding/reranker 物理超长专项仍暂缓。

## 7. 配置、集成与日志

新 `evidence_config.py` 包含 EvidenceSearchConfig / EvidenceSelectionConfig / EvidenceBridgeConfig；`DependencyRunConfig.evidence_bridge` 通过 YAML 严格加载。新 `configs/evidence_bridge.yaml` 默认方法 `dense, activation, evidence_bridge`，独立输出与缓存目录。所有新方法参数、提示版本与源代码参与 run identity；改配置必须新 run，原 run resume 冻结身份。

日志最低要求：

| 模块 | 必须可观测的内容 |
|---|---|
| planner | query/prompt identity、完整需求、原始响应、schema/修复结果、输入输出和调用费用 |
| scheduler | phase、动作、root代表选择、每目标ANN/集合/片数、前后预算、暂停/切换/停止原因 |
| activation / target | 四项分数、A/M_before/M_after/M_group、retain/speculate/reject、pivot新旧目标与来源、去重原因 |
| archive | 每个完整已测集合、来源、分数、归档原因；失败时缺项明确 |
| evidence | 每候选全文暴露范围、真实说话人、引用校验、需求支持/冲突/未知、mapping batch完成度 |
| selection | 全部候选范围、每轮集合、增删、覆盖变化、完整输入可行性、修订与停止依据 |
| feedback | 缺失需求、targeted query、ANN计费、返回ID、新增/重复、重映射结果 |
| reader/evaluation | 最终原始记忆与ContextPlan、实际请求hash、原始回答、解析结果、gold仅评估、正确性 |
| aggregate | 各模块真实调用/延时、逻辑预算与物理缓存分开、已成功/失败/待处理、按方法指标 |

结构化模块事件必须更新 allowlist，不能让关键字段悄悄丢弃。完整文本、引用和模型原始输出保存任务级 method artifact，并由 ID/hash 关联简短实时事件；凭据/Authorization/私有端点不得进入日志。异常保留之前完成结果，不把未完成判断当作负分。

新方法的模块事件在执行时立即持久化，标记 `record_kind=live`；任务结束时追加的归档事件标记 `record_kind=task_snapshot`，两类不能直接合计动作次数。每个证据事件原子更新 `evidence_live/<task_id>.json`，保存完整请求、响应、原文与映射；可处理的异常/中断再写最终 stop。操作系统强制 SIGKILL 时只能保证此前已落盘事件，任务级续跑从该题重新开始。费用包含失败的真实调用；reader 失败不抹去已经完成的证据选择。调度 pivot 分别统计尝试、成功入队和拒绝，集合删除仅累计实际被接受的修改。

汇总基于 authoritative outcome 的当前成功/终态尝试，不直接累加重试历史。保留原始标签准确率，修复已知 options→(s) 解析问题；重复选项敏感性与同请求重复现象作为明确诊断，不能算新方法收益。

## 8. Linux 运行与打包

新增一键 Linux 启动，安装必要远程推理依赖，离线数据预检和一次实际协议预检后以 detached worker 后台运行，无旧 regression bundle/批准环节依赖。支持部署 override、环境凭据、start/status/log/module-log/summary/stop/resume，恢复使用原 config 和 exact run 目录。

打包包含源码、配置模板、32k原始与processed数据、必要脚本、设计/运行文档及PDF；排除 .venv、缓存、旧outputs和本地凭据。默认无需下载本地模型或启动训练优化器。

训练运行文档写明启动命令、服务要求、方法配置、所有日志路径/字段/查看命令、异常与恢复、如何判读某模块是否有效。不能只写“看日志”，须给真实输出结构和定位过程。

## 9. 完成审查清单

- [x] R1：三个方向都接入正式 executor，默认新方法真正使用，不是未调用模块。
- [x] R2：查询计划无候选/选项/gold；映射无选项/gold；reader后才评估。
- [x] R3：多根有预算机会，ANN与集合双约束；暂停无重复ANN；已取proposal在ANN耗尽后仍可处理。
- [x] R4：完整四项原子计费、pair不被正singleton跳过、暖缓存逻辑计费。
- [x] R5：M_after留存、有界speculation、真实pivot去旧目标、循环去重。
- [x] R6：所有完整已测非空集合归档，部分失败有效分数保全。
- [x] R7：全文划分 span，已验证映射/未评估分别记录；角色、ID、offset及独立前提校验，推断与明示分开。
- [x] R8：整体选择实际支持delete/replace，覆盖与最终ID一致，预算修订不静默截断。
- [x] R9：缺口反馈实际ANN、额度计费、新证据映射、可解释终态。
- [x] R10：关键节点事件无allowlist丢失，完整任务artifact与当前汇总一致，失败仍留证据。
- [x] R11：有意义的边界/机制测试、端到端真实路径本地模拟、全套相关回归；不声称未做的真实模型评估。
- [x] R12：Linux一键后台/状态/停止/恢复/汇总/打包演练；文档命令与实际脚本一致。
- [x] R13：保留已核验的 v1 机制 PDF，v2 文档明确覆盖规则变化；源码审查和验证边界透明。

v1 原始验收见 [历史源码对照审查记录](evidence_bridge_review.md)；v2 历史见 [v2 可靠性修订记录](evidence_bridge_v2_validation.md)。上方历史 R1–R13 清单不替代本轮验收，v3 完成状态以 [v3 修改计划](evidence_bridge_v3_plan.md) 和 [v3 验证记录](evidence_bridge_v3_validation.md) 为准。离线测试不能代替真实模型效果评估。
