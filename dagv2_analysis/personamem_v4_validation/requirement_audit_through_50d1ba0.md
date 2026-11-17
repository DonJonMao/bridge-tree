# PersonaMem v4 当前候选需求对照审计

当前审计对象是冻结提交 `50d1ba0b2edb623384e51ac42ea12b36e5b69229`。
release 目录 `/Users/mao/projects/dagv2-personamem-v4` 与隔离修改目录
`/Users/mao/projects/dagv2-personamem-v4-reconcile` 的 HEAD 均为该提交，且工作树 clean。
本次仅只读复核源码、既有测试日志和候选收据，并更新 analysis 中这份报告与
`modeling_checklist.json`；未修改源码、重跑测试、读取评价标签、调用生成或 tokenizer 服务。

**当前结论：实现及离线边界审查通过，真实模型验收尚未通过，`release_ready=false`。**
R12 使用标准配置和固定 14 题启动后，已因具体首题失败链被主代理人工停止，PID 66449
对应 writer 已不存活；没有已发布首题 row。本报告记录为 `stopped`，不是自然算法终态，
也不是准确率结果。精确证据见 `r12_first_case_review.md`。
R13 首题已自然发布 `budget_exhausted`；主代理随后人工停止整跑，writer 已不存活。
R14 首题已自然发布 `unresolved_or_exhausted`；随后主代理人工停止整跑，writer 已不存活。
当前 R15 在冻结 `50d1ba0`、相同标准配置和固定 14 题上运行，主代理与候选收据确认
PID 75877、writer 存活；R15 为 `running`、`passed=false`。
正式上传包、最终包安装验收和交付后的清理仍待完成。

## 证据绑定与固定预算

- `full_tests_17b_obligation_review.txt` 实际末行为 **1709 passed、69 warnings、103.60s**。
  本次重新核对日志 SHA-256，与 `validation_candidate.json` 一致；没有重新执行全套。
- 候选收据的 **103 个源码文件 hash 全部匹配** release，配置文件 hash 也匹配。
  收据绑定当前提交，`release_ready=false`。
- `a48dc8d` 与实际部署基线 `a5b993a` 均是当前提交祖先。
  本次提交只改 reader、README 和三份测试，没有修改 Reasoner、配置、数据或模型服务设置。
  先前逐项相等检查已确认模型/embedding 名称和端点与部署基线相同；这不鉴定远端权重。
- 本次实际解析 `configs/personamem-v4.json`：context **16384**，ANN **36**，LLM **24**，
  JSON repair **6**，每请求 repair 上限 **2**，配置输出上限 **4096**，Reader **0**，
  set-score **0**，input margin **256**，固定安全 margin **8**，保留 audit 调用 **1**。
  本次义务反馈及显式冻结行复核未增加任何上述预算；此前特定初次历史请求的缩额政策保留。

离线测试证明执行契约和已覆盖边界，不证明模型能完成所有题目、答案更准确或论文创新性。

## 需求与当前实现

| 需求 | 复核结论及边界 |
|---|---|
| 双层 DAG 的含义分离 | 上层保留任务和 `inputs` 依赖，下层保留 dense/bridge 首次发现的导航关系。导航边仍为 `retrieval_proposal`、`dependency_claim=false`，来源需先被发现且文档真实存在；导航发现不会自动成为逻辑支持。本次未改这些规则。 |
| 残余求解和合法短路 | 根据实际未解变量、pending 及父依赖闭包控制工作；局部证明可暂停已消去需求，决定性依据被反驳后重新激活。原文未解义务不能因预算、改名或新日志而消失。本次仅改变有限准入时的输出分配。 |
| PersonaMem 任务目标 | 个人历史为中间证据，终端为原始用户请求的完整个性化回应选择。history、terminal、audit 保持各自阶段与输出契约；语义判断不伪称符号证书。当前工作是推理评测适配，不是参数训练。 |
| scope 与角色分离 | 历史变量需显式 entity/time scope；相同 scope 字符串不会合并变量、任务依赖或阶段。实体、时间、输出目标和截止位置保持独立。 |
| 显式历史文本语义 | 个人非终端、无有限域、非确定性 text 必须显式选择历史摘要或原子事实。不能按变量名称猜测；atomic、generic、有限域、非 text、terminal 和确定性表达式不获得摘要修订权。 |
| 摘要修订与事实反驳 | 摘要修订需验证精确当前 route/version、scope、实际父版本、旧来源及反证闭包，并通过下游实际容量检查。旧 route 保留在 ancestry；真实反证与摘要替代分开，祖先反证仍能使后继失效。无自动 union、自动覆盖或“最新值优先”。 |
| 精确 no-op 和来源祖先 | 完整验证后，内容和 proof 完全相同的修订不新建/退休 route、不升版本，保留祖先与依赖终端。普通重复 proof 不能重建无祖先的 OR 路径；真实新来源或实际父版本仍保留 OR 语义。 |
| 可执行的来源反馈 | 仅对通过先验资格校验的摘要修订，报告实际选中目标所缺的完整来源身份；不按引用数量替代身份。可信反馈与错误及原草稿绑定，持久化使用稳定 ID，再严格映射为当前 alias。代码不自动补来源或解除义务。 |
| 义务差集与显式本批冻结引用 | 仅当完整来源覆盖是唯一失败条件时提供逐义务 required/covered/missing 差集，并绑定当前失败 slot 及义务完整快照。仅本次 paid batch 当前 repair 明确提供的有效、settled、完整可见冻结行可被显式引用；不自动累积，不借用 known/global/跨窗口/跨 query/durable 行。摘要 proof 不被自动补来源。 |
| 原文、失败草稿与整值复核 | 不一致的整值由模型结合原始来源显式复核。失败草稿、反证及来源跨查询身份持久化；只有新原文或实际父绑定变化才允许在原预算内恢复，且通过完整验证和 handoff 后才解除对应义务。 |
| 无损 whole-review wire | 与顶层完全相同且 ID 唯一的已知 route 可用有序引用表示；值、来源、父版本、祖先和反证可完整重建。不匹配或歧义组保持原样。forecast 和实际 repair 共用编码；编码本身不删来源或改变预算。 |
| 首次历史 adaptive cap | 每个候选前缀先检查 full cap，再检查合格的 fresh personal-history adaptive cap；较大可入场缩额窗口不再被较小 full 窗口抢先。普通 `_fits` 仍必须通过。终端、audit、已有 repair、durable recovery、无新来源、无有效 baseline 或不具备修复预算不启用 adaptive。搜索不承诺非单调计数的全局最大前缀。详见下一节。 |
| 精确容量与下游准入 | 估计、实际请求及 transport 检查使用同一实际 cap。真正 repair 仍保留完整 4096，并对最终 wire 重新计数。mandatory downstream handoff 继续检查；不能依赖 forecast 代替实际准入。 |
| 预算和截断边界 | `finish_reason=length` 在解析前即视为失败，即使返回文本是合法 JSON。初次缩额后仅使用原有有界 repair；无 cap 增减生成循环，也不把失败草稿作为成功事实。 |
| 公平评测 | 两组使用相同公开题目和 cutoff-safe 历史；生成不读评价标签。固定 14 题按公开类型顺序选择。评分另行执行，报告同题含失败与双方有效子集；失败计零，缺失和损坏不混入临时分母。 |
| 发布门槛 | `check_smoke` 仍需检查 writer 停止且 complete、两组全部有效、源码/配置/数据/题目 hash 匹配、语义终端与新鲜 audit 完成。R12 人工停止；R13/R14 均先有首题自然失败、后整跑停止；R15 运行中且尚未通过门槛。 |

## 本次 adaptive cap 的具体边界

每个 `trial(size)` 先检查该候选的满 4096 准入；若失败，才检查该候选合格的 adaptive cap。
先测完整剩余前缀，再沿既有二分路径提议候选；仅当没有命中时补查尚未测试的前缀。
每个接受候选都经过精确检查；token packing 非单调，因此不承诺找到全局最大可入场前缀。
较大的合格 adaptive 窗口可以优先于较小 full 窗口；同一候选若 full 可入场则不测 floor。
候选的 aliases、cap 和 payload identity 独立保存，仅最终选中时安装 `_fresh_initial_selection`
并发出一次选择事件；探测不能覆盖已选额度，选中 full 路径会清除旧 adaptive 状态。
候选普通 `_fits` 仍需通过；下降的只是 fresh 历史首次 draft 的实际输出 cap，
没有提高上下文、调用或 repair 预算，也不丢弃来源与义务。

设 C=4096、T=16384、M=256+8；B 是初次请求输入，F 是完整整值复核空草稿 forecast 输入：

`cap = min(C, T − B − M, T − F − C − M)`

B 用选定 cap 的实际 payload 重新计数；若需要只向下收缩并复核到自洽，没有生成重试。
未知初次草稿预留等于真实下发的 cap，repair 输出仍为 C。实际 repair 可能包含更大的
草稿或重复表示，因此仍执行自身精确计数，不能把 forecast 解释为必定修复成功的证明。

当前下限来自**非空、保留当前已知状态的完整响应计量封套**，不再是空 observations 骨架。
每个 requested slot 都需有 `FactState.valid()` 的完整有效值及实际选中充分 route；按精确
target 保留完整 value、scope、实际父版本、旧/父/反证来源闭包和所需 revision 包装。
不会把所有 OR 备选来源变成 AND，也不会让原子事实获得摘要修订权。

每条既存未解义务另有一条 unknown 保留行：value=null，完整来源列表，reason 连接全部原始
descriptions，slot.unresolved 逐项保留，resolved_obligation_ids=[]。不按描述数量重复整组
来源，也不把这些来源自动当成当前摘要的支持。请求中省略、改写或重复可信义务不能降低额度。

所有 alias、原文坐标/角色/内容、已知 route、声明、scope、父版本及义务都须与当前可信状态
一致；无值、冲突、撤回、过期、缺槽位或无法完整映射时不启用 adaptive。
完整 assistant 聊天封套经部署侧精确计数，仍要求明确非估算的正整数；它是工作量额度政策，
不是 raw completion 数学下界，也不保证新增内容、后续修复或语义正确性。计量材料不进入
生成 prompt、不发布为答案、不修改 FactState/义务/预算，不会自动补模型引用或清除 pending。

Reasoner 的 `output_token_cap` 必须为 1..配置上限内的严格整数。`estimate`、`_payload`、
`request`、`_preflight`、记录中的 `output_token_reserve` 及 transport 实际 payload 同步，
不修改全局设置；不同 cap 区分生成缓存身份，同 cap 缓存重放仍按既有预算收费。
选择的数据序列化身份需与即将发送的请求一致，变化即拒绝；不能把旧选择套在新请求上。
修复请求、终端和 audit 保留原额度。

三份新回归分别覆盖底层 cap/transport、结构计量与重新计数、reader 独立边界；独立文件
`test_v4_adaptive_initial_cap_review.py` 的 **24 例**包含：较大 adaptive 窗口优先、精确窗口准入、
结构额度等号边界、额度不足零生成和零 LLM/repair 消耗、非 fresh 排除、真实 cap 一致、
repair 恢复 4096、实际 repair 超限不丢原文、合法 JSON 截断仍失败、原输入/改名不买新尝试、
后续窗口不可入场时保留未读后缀和已接受历史、选择后请求改变时零生成。
新增独立 `test_v4_state_preserving_floor_review.py` 的 **21 例**覆盖无有效值、冲突/撤回/
过期、OR 单一 target、实际父来源和版本、原子权限、53-source 及无来源义务、严格 alias、
可信义务删改拒绝和计量隔离；旧 24 例改为使用真实有效摘要，两文件共 **45 例**通过。
新增 `test_v4_prefix_admission_review.py` 的 **12 例**覆盖混合二分探测的最终元数据绑定、
仅选择时安装/发事件、full 不计 floor 且清除旧选择、floor 拒绝回退、非单调 no-fit 补查、
无有效 baseline 与非 fresh 边界、实际请求序列化顺序变化时零生成拒绝。这两份 prefix/adaptive
独立文件共 **36 例**通过；reader 另有真实预算流程回归。
这些检查已纳入当前提交的 **1709** 例全套结果，没有在此报告更新中重跑。

## 本次义务修复契约

义务要求复核其全部原始来源，与摘要只保存必要支持来源是两个契约。完整覆盖可由同一
变量的合法 support、contradiction 和真正无关的 irrelevant 行联合完成；不要求把全部
义务来源塞进摘要 proof，也不授权把未查证来源统一标成 irrelevant。unresolved、sourced
partial/unknown、错误 ID、不可见来源或其他校验失败仍不释放义务。

`repair_scope.failed` 的 slot 项新增 `obligation_review_sources` 列表，按义务提供
`obligation_id`、完整 `required_source_ids`、`covered_source_ids` 和 `missing_source_ids`。
仅当覆盖不足是唯一失败条件才提供；内部绑定精确 failed-slot digest 与义务完整快照 digest。
差集不受通用反馈 240 字截断影响。错误、slot 或义务变化时旧反馈失效；模型同名嵌套字段
仍是未可信草稿。持久化用稳定来源 ID，重新展示时严格映射为当前 alias，不能缺失或歧义映射。

仅列出 missing 来源不能解决冻结行不允许重述的问题，因此新增显式、局部引用协议：
输入 `frozen_observation_reviews` 提供 `slot_observation_ids` 及 `observations`。
前者只指向同一 failed 项原 slot 中完整且严格 typed digest 相同的行；其余须提供完整原行。
输出 `reviewed_observation_ids` 只能引用当前 paid batch 当前 repair 内存授权的本变量
有效、frozen、settled 行。必须同时匹配内存原行、实际传输完整行和当前可见原文。
不能引用本响应新行、另一变量、known/global、前一窗口/query 或 durable 历史行；同响应
引用与正常 observations 同 ID 重叠也拒绝，防止篡改重述被静默忽略。

覆盖只取本次正常 reported 有效行与这些明确引用的并集。没有引用就不自动借用早先来源；
无新原文或实际父绑定变化不能通过改名/恢复买到新尝试。来源、反证、义务、repair 额度、
实际容量计数和 mandatory downstream handoff 仍保留；handoff 拒绝会回滚义务释放。

独立 `test_v4_obligation_review_feedback_review.py` 的 **17 例**覆盖 53 required/3 covered
准确反馈 50 missing、显式 frozen3+真实 irrelevant50 可完成而 support 仍仅 3 来源、缺 1
失败、各类非法/变更/不可见引用、候选与快照绑定、严格 remap、durable/零免费重试及 handoff
回滚。reader 自有测试另覆盖反馈及引用生命周期。首次全套发现旧 whole-wire 语义夹具
18 次重复文本因新增提示使离线 forecast 总量 16301→16438，超限 54；仅该语义 case
减为 8 次重复并保留真实引用/完整逆变换断言。生产 guard、16k/4096 预算以及独立精确
容量边界测试均未放宽。最终完整收据为 **1709 passed**。

## R9–R15 的真实证据与未完成部分

R9 在 `6483c38` 已观察到显式 summary、精确 no-op 和保留来源的真实摘要扩展，但整题未通过。
事件摘要修订反复遗漏同一组 13/22 旧来源，新增等量 alias 未满足身份保留；首题最终 unresolved。
`b160f3a` 加入精确来源身份反馈和引用规则优先级。详见 `r9_first_case_review.md`、
`r9_protocol_contract_review.md`。内存中补齐来源可通过局部状态检查，不是模型成功或准确率证据。

R10 首题因 fresh forecast 拒绝剩余前缀而未完成，后续 `5afd8ab` 做了无损 whole-review 引用。
归档 wire 的 6 个旧 hash 全部重建匹配；两个部署计数确认最小 forecast 8915→7766，
总量 16222≤16384；最大仍超限。该历史取证只证明当时状态的最小前缀恢复准入。

**R11 在 `5afd8ab` 被人工停止，不是算法自然终态。** 主代理已确认 PID 63325 不存活；
首题没有已发布 row、attempt result 或最终 fusion snapshot，因此不能写成最终作答失败或准确率。
`past_events` 的 15 个普通前缀均可容纳，但全部 fresh whole-review forecast 被拒。
最小 F=8478，旧双 4096 预留总量 16934，比 16384 多 550；最大总量 17818。
终端第 22 次调用停止时在途、audit 尚未发起。详见 `r11_first_case_review.md/.json`。
本次 cap 公式对应这两个已知 F 的算术额度分别为 3546 和 2662；这不是新服务验证结果。

**R12 已人工停止、未通过。** 使用冻结 `0eafe26`、标准配置和固定 14 题。其首题在
100 个可见来源的窗口分配 cap 34（空骨架 floor 24），call 9 实际 length 截断。call 10
的首轮 repair 使用完整 4096，实际可入场且 finish=stop，但遗漏旧 7 个引用中的 5 个；
为修正此问题构造的第二轮 repair 总量 16479，比 16384 多 95。另有既存 53-source
evidence obligation，不能把大输入简单归因于 277 字摘要。停止时没有 row、attempt result
或 fusion snapshot，终端及 audit 尚未发起；不是自然算法终态。该例支持后续审查非空
状态保留计量基线，但不能将实现的严格截断/来源拒绝写成协议绕过。后续候选仍须真实两组
结果及 `check_smoke` 验收；本报告不宣称准确率提升或全量零失败。

## R12 归档状态下的非空 floor 实际计量

本次只读取既有 `r12_state_floor_tokenization.json` 和 reconstruction 报告，没有运行计量脚本。
报告的 reader SHA-256 与冻结 `7118489` 源码一致；R12 保存状态的实际 call 9 wire 可完整
重建，**195 个已记录前缀 wire hash 全部匹配**。计量模板精确保留选中摘要的 7 个支持来源，
另有 1 条 unknown 义务保留 53 个来源与 2 条原始未解描述，不解决任何义务，state 不变。

部署计数给出非空 floor **565**；旧 cap **34** 被拒。原满 4096 路径在该保存状态无可入场
前缀；当时 `7118489` 的规则选中 **39 prefix groups、92 个可见来源**，实际 cap **581**。
初次输入 10687，总 11532；forecast 输入 11443，加 581、完整 repair 4096 与 264 余量后
总量恰为 **16384**。剩余来源继续保留为待处理工作。

报告记录 **2 次成功 tokenizer HTTP、1 次计数缓存命中、0 次生成**；这是在原状态下的
容量政策验证，不是对新窗口的模型生成、引用修复或整题成功验证，不能据此断言 581 足够
新增摘要或不再截断。该报告对应当时满 4096 前缀优先政策，不能当作本次统一前缀准入的运行结果。

**R13 首题自然发布 `budget_exhausted`，之后整跑人工停止、未通过。** 冻结源码 `7118489`。
已发布 row、attempt result 和 fusion snapshot 均存在；不能把首题自然终态混同后续人工 stop。
规划 1 次、历史 18 次、终端语义窗口 4 次，共 23/24 LLM；18 个历史窗口全部完成，零 repair。
四个终端调用属于同一个 `JointReader.read()` 的窗口循环，不能据此宣称控制器重复 composition。
下一终端窗口在生成前因预算被拒；剩余 1 次调用保留给 audit，audit 尚未开始。
若最后窗口及单次 audit 都成功，当前路径至少需要 25 次调用。失败窗口仍以四条 failed review
保留完整 40-source context；没有 unread 标记不等于义务已解决。详见 `r13_first_case_review.md/.json`。

**`25fc384` 统一前缀政策的归档容量核验。** `r14_prefix_admission_replay.json` 的 reader hash
与当时冻结源码一致；本次源码已变化。该同一 R12 保存状态的原始 wire 完整重建。旧 full 选择为 16 groups、
35 可见来源、cap 4096；当时真实 `_fitting_prefix` 选中全部剩余 70 groups，窗口 71 来源、
总可见 88 来源、cap 516、非空 floor 324。初次输入 10761，初次总量 11541；forecast
11508 + cap 516 + repair 4096 + margin 264 = 16384。选择 identity 与实际 payload 相同，
仅一个选择事件，状态/义务不变。已有报告记录 2 次成功 tokenizer HTTP、0 次生成；
本次审计没有调用服务。它只证明新政策实际选择了更大且已核验的窗口，不证明生成、语义或整题成功。

**R14 首题自然发布 `unresolved_or_exhausted`，之后整跑人工停止、未通过。** 冻结 `25fc384`。
LLM 13/24、ANN 4、JSON repair 6/6，终端和 audit 调用均为 0，不是总 LLM 预算耗尽。
音乐历史 cap425/floor410 截断，随后 full4096 repair 通过，说明非空 floor 不保证生成长度充分。
事件历史 cap569/floor505 及其 repair 均正常返回，正确请求释放 offered 义务、全部 53 来源
可见、无 partial/unresolved，但 support 仅覆盖 3、缺 50；旧反馈未给出具体差集。
该失败 review 持续保留 93 来源；后续 6 次 support admission 拒绝涉及 mandatory semantic
composition 的 95 可见来源，另有实际 repair 总量 16627，超限 243。R14 采用的四历史节点
plan 也不同于 R13，不能把聚合调用数差异归因为前缀策略的单一效果。
详见 `r14_first_case_review.md/.json`；首题自然结果不能混同之后人工 stop。

**新增义务反馈在 R14 保存窗口下的精确容量核验。**
`r14_obligation_repair_tokenization.json` 重建旧 call7 完整 wire，并用生产 helper 构造
53/3/50 差集及 1 个原 slot 冻结引用（无需重复完整行）。93 个来源仍保留，状态与义务不变。
部署计数得新 repair 输入 11783，完整输出 4096、余量 264，总 **16143≤16384**，剩余 241；
旧输入 11007，增加 776。该报告有 1 次 tokenizer HTTP、0 生成。
最终 `r14_obligation_repair_current_source_reuse.json` 的 reader hash 与当前 `50d1ba0`
一致，重建的新 wire hash 与上述已计量 wire 完全相同；manifest/config、tokenization
参数及计量实现的绑定已记录，因此复用该精确计数，新增网络计量和生成均为 0。
本次审计仅读既有报告，未调用服务。这只证明该保存窗口的容量，不证明模型会正确审查
50 个来源、引用修复、其他前缀选择或全题成功。

**R15 当前运行中、未通过。** 主代理及候选收据记录 PID 75877，冻结源码 `50d1ba0`、标准
配置、固定 14 题。启动不等于成功，最终仍以完整两组结果和 release gate 为准。

## 正式包、安装验收及清理

1. 真实门槛通过后，才能将准确提交、冻结资产及测试收据绑定到正式上传包，并核对凭据排除、
   SHA-256 和 tar 往返。当前没有由此审计认定的正式交付包。
2. `verify_final_archive_install.py` 已准备，但对最终正式包的隔离安装验收尚未执行。
   helper 和模拟测试不能代替最终包验收；需核对冻结资产、兼容索引和私有凭据迁移。
3. 按已授权清单清理过时发行包与重复 payload 仍待交付后执行，保留唯一实验原始证据和必要诊断。
   本次未执行 cleanup。

本提交保留非空状态计量、逐候选 full/adaptive 准入、实际预算及来源契约，新增精确义务差集
和明确的同 batch 冻结行复核引用。离线检查及归档容量验证通过，R15 真实门槛仍待完成。仍可能出现模型遗漏、超长未解原文
义务无法单次容纳、输出截断及预算内无法完成；不能由静态审计宣称这些风险已经消失。
