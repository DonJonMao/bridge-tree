# R17 mandatory proof scope：理论要求与当前保守范围的独立审查

审查提交：`bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`，源码路径 `/Users/mao/projects/dagv2-personamem-v4-reconcile`。本审查只读源码、方法文档、既有 PDF 提取文本和结构报告；另在内存中构造两个无服务合成状态验证范围选择。未修改源码、配置、发布 gate 或运行；未读评价标签、真实模型响应正文，未请求生成或 tokenizer。

## 1. 结论

**必要依赖与相关反证必须保留；“所有保留的历史路线都必须在每次后续调用中共同可见”并不是原方法理论的必然结论。当前实现采用了比实际充分证明更宽的、已经明确写进当前 README 的保守输入范围。**

1. `terminal compose` 不是无条件取全部非终端任务：它沿规划 `inputs` 及这些有效绑定的实际父版本闭包扩展。只有 `audit` 显式把 `step.inputs` 改为全部非终端任务。两者不能混写成一个全局行为。[S1][S2][S3]
2. 对本次 `requested_slots` 中的变量，`known_observations` 包含该变量**全部保留路线**，未按有效、已替代、已撤销、是否为当前 selected proof 过滤；这些路线和 counter 的原文一起成为本次可见来源。对于仅作为额外 audit parent 出现、没有进入 requested slots 的变量，先带入的是有效 selected proof 的父值/来源，而不是必然带入它全部旧路线。[S1][S4]
3. 原方法明确区分 AND 前提与 OR 替代路线，证书选实际充分路线；还要求输入为必要父结论、当前原文、相关反证，并反对无条件重传全部历史。因此，“保留全部 provenance”不能直接推出“全部 provenance 原文每次同窗重读”。[D1][D2][D3]
4. 但当前 README 明确保留全部非终端 audit 输入范围、完整闭包单批复核、未解事项和失败草稿原文；已有只读设计审查也刻意把 audit 范围缩减排除在上一轮修复之外。因此这里可确认的是**原方法必要范围与当前保守输入策略之间的建模差距**，不是新发现的“实现违反当前已经约定的协议”。README 记录的是上一轮实施边界，不是永久禁止对齐原设计；用户已授权严格修正理论/实现偏差。新的范围应按独立协议和证据论证，不能按容量失败直接删源。[D4][D5]
5. R17 第一题终端生成与审计均为 0；结构报告说明它在下游容量接纳处失败。不能据此把“audit 全非终端范围”认定为这题失败的直接原因，亦不能证明删去任何具体来源后可正确作答。[E1][E2]

## 2. 四个应分开的对象

| 对象 | 当前语义和代码 | 保留它是否推出每次完整同窗出现 |
| --- | --- | --- |
| 实际父依赖 | 选中有效 route 的 `parent_versions`，递归到实际依赖。它决定版本新鲜性、pending 阻塞和语义发布身份。一般语义/接地任务还要求携带声明输入的有效绑定；确定性任务可凭合法投影消去未使用输入。 | 当前需要共同解释的有效前提应保留；不能把确定性短路机制不加论证地套到开放偏好选择。[S3][S5][D2] |
| 保留的旧 route provenance | OR 替代证明、旧版本和 summary 祖先记录。退休的摘要不是事实被推翻；祖先真实 counter 可以使后代失效。 | 必须可追踪、可校验、可撤销；原理论没有要求所有旧 route 在每次后续模型调用中同窗。当前输入策略会对 requested variables 整体带入。[S1][S4][D3] |
| 当前请求必须共同可见的材料 | 目前 `_payload` 实际构造出的父绑定、requested-variable 全路线、相关义务、失败原文及当前 identity clues 的来源并集。`mandatory_closure` 整体单批调用。 | **这是当前可执行协议定义的范围**；“完整”须相对于这一定义理解，不能当成原理论已经证明每一成员语义上都不可省。[S1][S6][D4] |
| 未决义务 | `unread_obligations` 的 owner/alias/variables，带来源的 `evidence_obligations`，持久 `failed_batch_reviews`。未知、未读、格式失败不等于无关。 | 与当前实际依赖相关者不能被跳过；无关/被合法短路者仍可留存而不阻塞当前证书。跨身份、跨批覆盖不能自动借用。义务原文不是天然全部成为最终支持引用。[S6][S7][D3][D6] |

`modeling_checklist.json` 的 `nonempty_state_preserving_response_floor` 明确写“actual selected sufficient route”和“do not union all OR alternatives”，但该条同时声明该计量参考**不发送给模型、不作为证据、不解除 pending**。不能把输出额度下限计量中的 selected-proof 范围直接拿来替换真实输入范围。[D7]

## 3. 当前源码究竟怎样生成范围

### 3.1 事实层仍然保持 OR，不是把所有历史路线改成事实 AND

`FactState.valid()` 先筛掉 revoked、superseded、scope/父版本失配的路线。同变量有效路线值一致时，从中选一条来源闭包最小的充分路线；源码注释明确“rather than turning all alternatives into AND”。返回的 `sources[v]` 与 `route_ids[v]` 只对应选中的路线。[S4]

`semantic_dependencies()` 从真实终端变量出发，只沿当前选中 route 的 `parent_versions` 递归；`semantic_inputs_current()` 检查这些依赖及其 pending/版本身份。审计的 requested variable 集合也来自这条实际依赖链，或符号证书的 `binding_dependencies` 与 rule assumptions。[S2][S5]

### 3.2 输入层是一个比 selected proof 更宽的并集

对一次调用，`_payload` 的结构可以概括为：

```text
related = 当前 task.inputs 的有效变量 + 选中路线的实际父闭包
parents = related 中的当前有效值、版本、scope、selected-proof 来源
known = 所有 variable 属于本次 requested variables 的保留 route
obligations / failed = variable 属于 requested variables ∪ related 的相关记录
visible_sources = sources(known ∪ parents ∪ task_outputs ∪ obligations)
                  ∪ retained_sources(failed)
                  ∪ clues(current_identity)
                  ∪ 本次显式 aliases
```

来源是 stable identity 去重后的集合；不会因为相同源被多条路线引用而重复加入 raw span。typed `value`/`output` 内的应用字段不会被递归误当 provenance。不可用原文会拒绝请求，而不是留下一个无法核对的 source ID。[S1]

非审计 `read()` 会把真实父闭包扩入本次 requested variables，让新局部材料能纠正父事实。因此 terminal compose 的 `known` 通常也包含父变量的全部历史路线。审计路径不做这一步扩槽，但 `audit()` 明确改为所有非终端 `inputs`，故可能另带不在当前 selected terminal dependency 中的有效 parent 值及其 selected 原文。[S2][S3]

这里存在**输入容量的并集合取要求**：所有被上述规则纳入的材料必须能同时放下。它没有改变 `FactState.valid()` 的 OR 逻辑，却可能使一条充分证明因为同变量其它存档路线的输入负担而无法进入下游。这是准确的策略描述；不能简写成“OR 逻辑写错成 AND”。

### 3.3 Handoff 检查的是当前协议规定的调用

`_handoff_failures()` 在 prospective state 中检查受新 support 影响的活跃下游任务；变量包含目标输出和有效父闭包。若有可审计终端，又构造同样的全非终端 audit inputs。它用真实 `_payload`、`_fits` 和原有修复预留检查容量；不足时保留失败草稿与必要 counter。[S8]

所以它对当前实现的“将要发出的调用”具有一致性。`capacity_handoff` 所写的“actual required downstream calls fit”并未另外证明该调用中每一条归档 route 都是语义最小必要成员。容量检查正确与范围策略最优是两件事。[D6][S8]

## 4. 哪些是原理论，哪些是后续明确的工程约束

| 规则 | 证据 | 判定 |
| --- | --- | --- |
| 一般语义/实体接地保留必要声明父依赖及实际版本 | 原设计 131 行；local-terminal 9、13、17 行；`_observation` 1215–1225 行 | 原方法明确要求，不能以残余短路名义任意删父输入。 |
| 独立路线是 OR；保留替代路线，证书选充分路线 | local-terminal 13 行；residual v1 17 行；`FactState.valid()` | 原方法与当前事实层一致。 |
| 核验已采用支持与相关已知反证，输入不无条件重传全部历史 | 原设计 216–218、232–242 行 | 原理论的局部必要性边界。这里没有推出“所有同变量旧路线每次全送”。 |
| audit 默认纳入全部有效非终端 parent | `audit()` 452–458 行；README 95 行；上一轮范围审查 53 行 | 为审查提供更广历史上下文的保守策略；当前已明示保留，但未找到原理论要求所有这些输入总是共同必要的论证。 |
| requested variable 的全部 retained routes 和 counters 一起入 wire | `_payload` 492、499–516 行；README 91–95 行 | 当前工程闭包策略。它方便让模型识别旧结论、替代依据和 counter；“保留记录”与“每次全量共同可见”在原理论上仍不同。 |
| 摘要修订保留被替代路线全部旧来源及相关 counters | `summary_revision_sources()` 72–82、`validate_summary_revision()` 108–118 行；README 124–132 行 | 已明确的摘要“兼容增补”契约。旧表示退休不授予删去其历史事实/来源的权力；不能称它只是误留过期摘要。 |
| 祖先反证使依赖其内容的新摘要失效 | `summary_ancestors/is_active_route` 53–70 行；checklist 142 行 | 保真要求；不能只删除祖先关系而保留表面相同的新摘要来绕过反证。 |
| 完整 mandatory closure 单批真实调用 | README 91–98；`read()` 1934–1967 | 当前保守执行策略，旨在不拆开必要共同前提；原理论没有要求全库或全部归档 provenance 都因此变成当前共同前提。 |
| 未决证据直到明确复核前保留；目前不允许跨批累计覆盖 | README 112–121；checklist 343 行；owner guards | 前半是必要正确性边界；“只能当前提供的同批复核覆盖，不能跨批累计”是当前具体协议限制。它已被明示，不是本次可偷偷放宽的实现细节。 |

### PersonaMem 的重要限定

PersonaMem planner 要求每个历史任务都在最终回应选择的结构祖先闭包中（`validate_personal_plan()` 170–178 行），同时提示历史只需 query-relevant 的充分证据而非穷尽所有经历（47–66 行）。因此“全部非终端”也不等于“任意无关任务”。一般语义任务将声明父值作为强制接地输入后，很多计划中全部非终端本来就属于实际终端依赖；是否存在严格额外范围必须逐计划、逐 route 检查。[S9]

### 摘要祖先原文可能已在当前 proof 中，不能仅数旧 route 数量

修订要求新 `source_ids` 覆盖被替代路线的旧原文及相关 counters；这些 ID 会被并集去重。旧摘要 metadata 或 value 的重复可能增加输入长度，但移除旧 route 表示未必减少原文 source 集：其旧来源可能已经全部继承到当前 active summary 中。必须分别测量 raw-source 并集、route metadata、值重复和义务封套，不能用“旧摘要很多”直接证明其原文都是额外负担。[S1][S4]

## 5. 可确认的差距与不能确认的缺陷

**可确认差距 A：依赖范围与 audit parent 范围不是同一个集合。** 请求核验变量从当前证书/实际依赖得出，`audit.inputs` 却来自全部非终端任务。原设计按当前输出的支持及相关 counter 描述审计，而当前实现使用更大的结构范围。该范围是保守上界，不是已经证明的最小闭包；README 已明确保留它，因此不能把它作为本轮未经讨论的 bug 直接改窄。[S2][D3][D4]

**可确认差距 B：provenance 存储完备性被当前输入策略转化为同变量全路线可见性。** 原理论和事实求值允许一条独立充分路线成立；输入层仍把所有同变量路线的源带入共同容量约束。源码并没有单独区分“仅为追溯保留且本轮无复核义务的 route”与“当前必须共同重读的 route”。这是一项有源码依据的建模/工程差距；尚未建立可安全缩减范围的判准，尤其不能漏掉相关 counters、摘要继承、当前未解问题。[S1][S4][D1][D3]

**本轮没有确认的缺陷：** 未见当前实现违反已经明示的 mandatory closure、summary revision、未读 owner 或失败恢复契约；未见因为记录多就把 typed OR 事实错误求成 AND；未见新的“父 span 自动扩到整文档全部 span”路径。上一轮发现的文档扩张已有独立入口修复；当前 `mandatory_closure` 使用精确 `_payload` 来源而非候选文档扩张。[S6][D4][D5]

这也意味着不能在论文中把当前保守策略说成原理论已经要求或证明；应把方法的正确性约束、具体实现的范围上界和有限上下文下的可执行性分开说明。

## 6. 两个独立离线结构探针

在冻结源码上复用 `tests/test_v4_mandatory_contract_review.py` 的 `scoped_fixture()` 及本地 observation/source 校验，向内存状态构造人工观测；socket 与 urllib 均替换为抛错函数。没有真正模型调用、语义蕴涵或准确率断言，也没有保存/修改运行状态。

| 合成状态 | 观察结果 |
| --- | --- |
| requested variables 仅 `history`；先只给 audit `inputs=['history']`，再增加一个已有效但本探针未请求的 `unrelated` task | `supported_parents` 从 1 个增到 2 个，source 从 1 个增到 2 个；`known_observations` 仍只有 history 的 route。验证 audit 额外 parent 与 requested-route 范围是两个机制。 |
| 同一历史值有两条各自一源的 OR 路线，无 counter、无 obligation | `FactState.valid()` 选 1 条 route、1 个 source；`_payload` 仍带 2 条 known route、2 个 source。验证事实层 selected proof 与请求层 provenance 并集不同。 |

总 transport 调用：0。第一个探针是通用 reader 范围单元场景，不是宣称 PersonaMem planner 会接受一个与终端结构无关的任务；真实 PersonaMem 仍受全部任务贡献约束。第二个探针不证明未选路线语义无用，只证明输入策略与 OR 充分路线不相等。

## 7. R17 第一题能说明什么

结构报告读取时记录第一题 `acd74206-37dc-4756-94a8-b99a395d9a21` 自然结束为 `unresolved_or_exhausted`：LLM 18，JSON repair 6，ANN 5；history 11、repair 6，terminal 0、audit 0；2 个 pending variables，4 次 capacity rejection，失败分类 `mandatory_downstream_context_capacity: 2`。[E1]

实际 reader wire 报告共 17 次发送：`joint_read=11`、`joint_read_repair=6`，采用 `shared_history_texts` 的次数为 0。[E2] 这说明新共享文本表示未改变这些实际请求，**不是**共享格式被模型解码失败。未发送的 prospective handoff 需要另行重建；实际 reader wire 统计不能替代其范围归因。

本审查不声称已经找出这些 source 中哪条是不必要证据、不声称全非终端 audit 导致了第一题失败，不推导增加上下文/预算，也不提出按数量截取 proof。要把范围差距升级为具体实现缺陷，至少须在同一冻结状态中逐项说明来源属于：实际选中父证明、相关 counter/祖先继承、待复核义务、还是仅存档备选路线，并证明后者的隔离不会改变反证可见性、实际依赖新鲜性和待办完成语义。

## 8. 对齐原设计的安全实施边界

**建议可在独立候选中实现显式的 compose/audit 证明范围投影，而不改历史取证、summary revision 和失败恢复的复核范围。** 这是有条件的设计建议，不是本报告已实施或已验证的行为，也不保证改变 R17 第一题结果。

### 8.1 按操作目的分开，不能只给所有 `known_observations` 加一个过滤器

- **历史提取及历史 summary compose：** 保持能比较/修订旧候选、发现冲突、引用合法 targets 的完整历史协议。`phase=history_evidence` 中的 `summary_revision_contracts`、whole-value reconciliation、frozen reviews 与 durable failed recovery 依赖这些对象。尤其普通中间 `compose` 也可能是 history summary，不能仅凭 `execution='compose'` 就套终端证明投影。[S1] 的 581–596 行与 [S10]
- **真正终端 response selection：** 从终端声明输入出发，保留每个有效父绑定的 selected sufficient route 与递归 actual parent closure。一般语义接地父依赖仍强制；不把“选一条 proof”误写成任意删除一个声明的父变量。[S3][S4]
- **response audit / 符号证书审计：** 从已有真实 terminal semantic dependencies 或 certificate binding/rule dependencies 出发，替代“全部非终端”作为父范围的默认上界。不能在缺少实际终端/证书身份时猜一个更小集合；仍须复核全部相关已知 counter、冲突和未决问题。[S2][S5]
- **既有失败批次恢复或显式整值复核：** 按本次获准复核的完整原记录处理；若该 request 具有恢复/冲突解决目的，不可为了终端投影而删掉对应 failed drafts、review groups 或原始 source coverage。保留现有付费资格与原子 handoff 解除规则。[S7][S10]

### 8.2 投影必须保留哪些材料

1. **当前 selected active proof 的完整原文和实际父证明。** 使用 `valid()` 的 exact route identity/typed value/scope/version 选择结果；不能根据文案长度、source 数量或本次 capacity 把已选 route 内的来源切片。`source_ids` 已经累积继承的 summary 原文不裁剪。[S4]
2. **相关真实 counter 与其可解释目标。** 保留 actual dependency 变量上的已知 counter；若 counter 指向选中 summary 的祖先，保留其目标语义、祖先关系及原文，不能留下一个悬空 ID。相关冲突不能因为没有 active selected proof 而被过滤为空；需继续显式保留冲突或按原协议阻塞/复核。[S4][S10]
3. **尚未解决的 evidence/failed/unread 事项。** 必要性按同一实际依赖/变量范围定义，不能因某旧 route 从本次 wire 缺席就声称其义务已完成；所有 source coverage、owner 和 checkpoint 行为继续保持。任务被合法短路时可以保留未决记录而不激活，但不能删除记录。[S6][S7]
4. **合法的撤销/修订目标授权。** 当前 schema 的合法 `retract_ids` 来自 wire 中 `known_observations`，而 `_observation()` 的本地 targets 来自 state 中全部同变量 route。过去 wire 同变量全带时二者基本一致；缩减 wire 后必须显式传递并验证本次被提供的合法目标集合，防止模型绕过缩减后的 schema 撤销不可见旧路线，也避免把合法祖先 counter 的目标误隐藏。[S10]
5. **canonical state 与归档不变。** 本次不发送的无 counter、无冲突、无活跃复核义务的独立备选证明仍留在 `FactState.routes`/checkpoint，未来主路线失效时可重新选择、重新接地并审计。它们只是未被当前 proof 采用，不应被写为 `irrelevant` 或自动 `revoked`。[S4]

因此，`selected proof + dependency frontier + all relevant counter/conflict/obligation` 作为**终端调用投影**在概念上与原理论一致；把它当成状态删除、摘要重写或所有阶段通用的 route 过滤，则不安全。

### 8.3 必须形成新的一致调用契约

Handoff、实际 generation、repair 和 token estimation 必须共享同一投影函数与输入身份；纯计量下限不能替代它。所有相关源仍由真实 `_source`/alias 校验，不加隐藏 token 额度，不拆开同一充分证明的共同前提。投影被明确扩大（新 counter、版本改变、当前真实冲突/义务）后要重新计算容量与审计新鲜性。[S1][S5][S8]

最有价值的回归是：两条等值 OR 路线只发送所选证明但归档两者；非所选路线上的相关 counter 仍进入；祖先 counter 仍撤销后代；当前选中 summary 的累计来源不变；冲突变量无 selected value 时不能消失；历史 summary revision/whole review 行为保持；不可见 route 撤销被拒；proof 失效重新选替代路线后重新审计；foreign unread 与无授权 failed recovery 仍阻塞；handoff/估算/实际请求完整一致。必须在独立候选完成这些契约回归并重新冻结后做真实模型验证，不修改 live release。

## 9. 逐条证据索引与版本身份

源码链接均对应本次 `bcbd16f` 文件；行号范围在文字中列出，链接锚定首行。

- **[S1]** [joint_reading.py:477](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:477)，477–554：related/known/obligations/failed 选择，来源收集、去重和 wire。
- **[S2]** [residual_control.py:425](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:425)，425–460：审计变量来自证书或实际语义依赖，452–453 行把 inputs 设为全部非终端。
- **[S3]** [joint_reading.py:1888](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1888)，1888–1901：非审计 requested slots 扩入父闭包；[joint_reading.py:1215](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1215)，1215–1225：强制接地 parent_versions。
- **[S4]** [fact_state.py:53](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/fact_state.py:53)，53–118：祖先、counter 与摘要来源保留；[fact_state.py:132](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/fact_state.py:132)，132–153：OR 中选实际充分路线；229–237：退休旧表示但保留 route。
- **[S5]** [residual_control.py:192](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:192)，192–219：实际语义依赖与发布输入新鲜性。
- **[S6]** [joint_reading.py:1854](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1854)，1854–1877：owner/scope 验证；1902–1967：mandatory source 精确入口、单批、真实容量、失败保留。
- **[S7]** [residual_control.py:315](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:315)，315–339：实际 pending 与局部证书消去；[joint_reading.py:434](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:434)，434–459：失败恢复资格。
- **[S8]** [joint_reading.py:1693](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1693)，1693–1803：prospective handoff 及 audit 范围、容量拒绝。
- **[S9]** [personal_task.py:47](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/personal_task.py:47)，47–66：query-relevant 充分历史；[personal_task.py:170](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/personal_task.py:170)，170–178：全部历史任务须贡献终端；134–145：回应审计语义。
- **[S10]** [joint_reading.py:654](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:654)，654–707：schema 的 offered known/review/obligation IDs；[joint_reading.py:1207](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1207)，1207–1225：本地撤销目标与 parent 校验；1311–1354：ancestor counter 与 history-only whole-value review；1517–1526：持久失败记录。
- **[D1]** [DAGBT_LOCAL_TERMINAL_V1.md:9](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/DAGBT_LOCAL_TERMINAL_V1.md:9)，9–17：父接地、必要来源、AND/OR、实际版本；66 行：terminal input 与 selected source closure 分离。
- **[D2]** [RESIDUAL_MEMORY_DESIGN_f4e38df.md:125](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:125)，125–151：确定性短路与一般语义任务区别、保守活跃需求。
- **[D3]** [RESIDUAL_MEMORY_DESIGN_f4e38df.md:204](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:204)，204–218：局部读取与不无条件重传历史；226–242：实际证书、相关冲突、审计范围。另见 [DAGBT_RESIDUAL_MEMORY_V1.md:15](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/DAGBT_RESIDUAL_MEMORY_V1.md:15)，15–21、48。
- **[D4]** [README_PERSONAMEM_V4.md:91](/Users/mao/projects/dagv2-personamem-v4-reconcile/README_PERSONAMEM_V4.md:91)，91–101：完整闭包、all-nonterminal audit、owner、失败恢复；112–139：未决覆盖、摘要修订和失败草稿。
- **[D5]** [compose_audit_source_scope_review.md:40](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/compose_audit_source_scope_review.md:40)，40–65，尤其 53 行明确此前修复不缩 audit inputs；7、67–84 行描述旧文档扩张缺陷与证据边界。
- **[D6]** [modeling_checklist.json:63](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/modeling_checklist.json:63)，63–82：capacity、unresolved、short-circuit；142：summary provenance；343：显式覆盖和不跨批借用。本文件总体 source_commit 仍为 `50d1ba0`（448 行），引用的是已记录 invariant，不把其旧 runtime 状态冒充 R17 最新结果。
- **[D7]** [modeling_checklist.json:295](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/modeling_checklist.json:295)：计量参考的 selected proof 与非生成边界。
- **[D8]** [method.txt:15](/Users/mao/projects/dagv2/tmp/pdfs/a48_review/method.txt:15)，15–27：任务依赖和剩余求解；92–113：未完成备用分支不再影响输出时停止。该已存在的 PDF 提取文本没有“全部历史 route 每次同窗”的规则，亦不足以为开放偏好选择提供确定性短路证书。
- **[E1]** [r17_structural_monitor.json](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r17_structural_monitor.json)，读取快照 SHA256 `08d303764909cc732ebeed677e30fb7683f4c3c31b61e021a5376f0e2da5bbe7`。运行监控文件后续可能继续更新；以上只引用本次已发布第一行。
- **[E2]** [r17_first_case_wire_review.json](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r17_first_case_wire_review.json)，SHA256 `60bdd4d95a0cd019c7d26e30d20b0851ec42a3987070d467ae252332883875ba`。

本次主要源文件 SHA256：

```text
README_PERSONAMEM_V4.md 1ae46c00cb5d9f67648338e88cb96b93c351141834916470a59da0a49ac26d2c
dagbt/residual_control.py 468223d3a3f0e5995d2ef01464a01d253f6caae57f2bccb594ddb17c716f2330
dagbt/joint_reading.py 41f84e8eccdaa527c753fb6ad7345e83131d00cac1bd1de29c81fd02362c0391
dagbt/fact_state.py e55b9535d2c55ea87be3de59f4c5e1123e0eac06dc7e672827ba466e9c94c91e
dagbt/personal_task.py 7af9cc43b08364ea824c23c4aa2072395720ff945fb1499f62956bd4d889a9a3
modeling_checklist.json 41c10e632e5df7e4bb9e7b13297059f234347d618aa5a2b1898de41efc991bfb
```

## 10. 独立候选实现复核与冻结测试补记

本节仅描述 `dagv2-personamem-v4-reconcile` 后续候选修改；不改写第 1–9 节关于冻结 `bcbd16f` 的基线判断，也不把新源文件行号倒用于旧运行。当前实现显式区分 mandatory terminal/audit proof projection 与完整历史候选复核，并让实际请求、repair 与对应 handoff 使用一致范围；普通 final retrieval 的 document window 仍保持原完整范围，其 handoff 亦不套用终端 compose 投影。

独立回归文件 [test_v4_proof_projection_review.py](/Users/mao/projects/dagv2-personamem-v4-reconcile/tests/test_v4_proof_projection_review.py) 最终运行：

```text
/Users/mao/projects/dagv2/.venv/bin/python -B -m pytest -q tests/test_v4_proof_projection_review.py
32 passed in 0.43s
```

全部请求由脚本 transport 提供，网络调用禁止；使用真实 FactState、reader、部分 controller 和 serializer。测试覆盖选中 AND 证明全部前提保留、等值 OR 归档及重选、非选中路线 counter、冲突、summary 累计来源与祖先反证、历史复核、pending/failed/unread/checkpoint、隐藏撤销 ID 的 schema/本地/repair 拒绝，以及 handoff 与实际请求范围一致。

新增审查发现的一项必要边界已落实：**下游当前输出未决时，父变量“类型值相同”不足以证明其另一条原文对这个下游问题无用。** 因而 terminal pending、evidence obligation 或 failed review 必须保护其相关父/实际祖先备选；仅修 parent slot 的 repair 也保留原任务输出的这种关系。已有“新桥接文本保持同一父值但能推进未决建议”的回归失败，属于首版投影确有遗漏，不能以更新旧 mock 为由略过。独立测试分别覆盖这三类义务和 parent-only repair。

审计与上述未决 compose 的边界不同：若真实证书已合法消去同 terminal task 的 sibling，这个 sibling 的 pending 不应扩张本次 audit 的父备选范围。新增真实 `false AND sibling` 证书与实际 audit fixture 验证只审 decisive 及其 history 依赖，同时保留 sibling 的 obligation 和所有归档；若 decisive 本身 pending，则 candidate 为 None，且本次实际依赖范围内仍保留父备选。不能把这条合法符号短路泛化为开放语义任务的无证据消去。

另一项旧断言“窄充分 proof 已存在时，大等值 OR 必须被拒且强制 pending”在新契约下可合法改变：新路线可以归档，当前调用仍采用窄充分 proof。只要不删除大路线、不切 selected route 内来源、不隐去其相关 counter/义务，这种改变符合本次投影设计。

冻结时文件 SHA256：

```text
tests/test_v4_proof_projection_review.py 43297458c501965ff68d52f9ad8bf35066f080838566aed98ac60496a4fd2093
dagbt/joint_reading.py 8f23b7c8673d9a6c8ca2803753c58e04e014f0046db5343690ce2b577e3bb103
dagbt/residual_control.py 1d281f04f9e20ba042844afab134c53f52923b7618800a29dcc2a68d5009329c
```

这些测试证明的是上述输入范围、状态、授权和阻塞契约，不证明模型会给出更好答案、不证明 R17 首题会被救回，也不代表全量套件或真实服务验证已经通过。全量套件由集成负责人统一执行。
