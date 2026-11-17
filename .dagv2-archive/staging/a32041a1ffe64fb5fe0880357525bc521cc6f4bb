# R20 第 2、4 题失败链与最小协议修复设计

审查 RELEASE 冻结版本 `6c046374008ce2e45f817d6bc9876b3ab927ab18` 的已发布 rows、实际 requests、events 与源码；以第 1 题的独立报告作比较。未读标签/评分，未调用模型/tokenizer，未改运行、源码或状态。本文不导出题目、选项、答案、记忆原文。证据 JSON：`r20_cases02_04_failure_review.json`，SHA-256 `4ab3874a45fb371d0a329615b7a44d733da74087e9b296cdf89833f541d61b27`。读取集合已逐文件复核未变化。

## 结论

第 2 题是**历史语义未决 → 未完成原文复核 → 模型冻结重述违规 → 保留失败原文 → 下游容量拒绝**的复合链。第 4 题是**terminal 支持/弃答表述不一致 → 真正的选项区分未决 → unknown 不能解除义务 → 重述同批冻结 unknown**，没有已记录的容量失败。两题都有预算剩余，因此不能合并为“预算太小”。

确认一个可最小修复的实现缺口：runtime 禁止重述当前 batch 的全部冻结 observation，但实际 schema 只禁止其中**获准 settled review 引用**的 observation。unknown/partial 不允许被引用是正确的；因此它们反而没有进入 schema 的禁止重述集合。应把禁止集合 F 与引用集合 R 分开，完整表达现有 guard；不增加 unknown/partial 解除义务的能力。

另记录一个需单独论证的控制 policy 扩展候选：handoff 预测对 grounded future target 继续既有容量检查，而真正 compose 还受到跨 query owner 的 unread guard 限制。已绑定但仍 pending 的父节点能使前者硬拒绝一个新支持，而实际目标仍被 owner 阻塞。`docs/HANDOFF_EXECUTABILITY_POLICY.md` 已明确把此情形保留在原有检查范围，本次没有扩展调度恢复。因此这符合既定 policy 边界，**不是本报告已证明的新代码/理论矛盾**。未来若扩展，不能删除 unread、放松真实容量检查或混入本轮 F/R 补丁。

## 第 2 题：最早错误与失败主链

unit `f546a74f-54de-40d0-9d88-8b0e30467d7b`。最终 `unresolved_or_exhausted`，audit=false；LLM 10/24、repair 5/6、ANN 3/36。版本为 creative_history=1、getaway_constraints=1、creative_preferences=0、context_summary=0、response=0；前两个 pending 是 getaway_constraints 与 creative_preferences。没有实际 terminal/audit 请求。

最早技术错误是 planner Call 1 未给 context_summary 声明 evidence_semantics，Call 2 已修复，消耗一次 repair。这不是足以解释终态的首个不可恢复点。

计划含 creative_history、getaway_constraints、creative_preferences 三个 retrieval，然后一个 context_summary compose，再到 response。所有 Reader 请求 finish=stop、usage matched，未出现截断或服务失败；这些请求既没有 shared_review_texts，也没有 shared_history_texts。

| Call | 操作/任务 | 来源数 | Input / output cap | 结构与后果 |
| ---: | --- | ---: | --- | --- |
| 3 | history | 48 | 7373 / 4096 | support，16 引文，无 unresolved。 |
| 4 | getaway | 49 | 7391 / 4096 | support，16 引文；同时声称缺少出行时间、预算、地点、同行者等具体约束信息。 |
| 5 | getaway | 74 | 9993 / 658 | 重复同一支持并 summary revision，声称解除 49-source issue，但实际只复核 16，缺 33。 |
| 6、7 | getaway repair | 74 | 11188、10871 / 4096 | 同时引用已冻结 ID 并原样重述；离线实际 schema 均在 slots[0]/oneOf 失败。 |
| 8、9 | preferences / repair | 47 | 7349、7769 / 4096 | 相同 16-source 支持被 context_summary 85-source handoff 容量拒绝；出现 unchanged repair。 |
| 10 | preferences durable repair | 99 | 11856 / 4096 | 同一支持仍被相同 handoff 拒绝；下一 repair 输入 12284，加 4096 输出、256 margin、8 overhead 为 16644 > 16384，无法发送。 |

getaway 最后保留 74-source failed batch 与 74 hard unread；preferences 保留 99-source failed batch 与 99 hard unread。实际 InputOverflow 位于事件 337、492；85-source handoff 拒绝位于 401、415、444；repair input unavailable 位于 446。

精确集合：G=Call 5 的 74-source 窗口，H=history 的 16 引文，P=preferences 的 16 引文；`|G∪H|=83`，`|G∪H∪P|=85`，P 相对前两者仅新增 s51、s52。因此反复要求修改 preferences 最短引文，所针对的新增来源只是未来整体负载的一小部分。未重新计数删去两段后的 wire，不能声称减少这两个来源即可适配。Call 5/6/7 的 observation 完全相同；Call 8/9/10 的 preferences observation 也完全相同。

这里的 constraints 缺口与 case 1 的“已读范围说明”不同：它确实指出缺少具体信息；但 planner/Reader 是否把可选历史维度提升成必需前提，需要结合当前用户请求的必要性继续审查。证据不足以自动称其无关，也不能要求任何未提到预算/地点的开放式推荐都失败。最小建模方向是明确区分“必要且未满足的条件”与“历史没有记录的可选维度”，由模型提供语义理由并保留真实未决；不能由 controller 自动清空或转 irrelevant。

## 第 4 题：semantic 未决与 schema/runtime 缺口

unit `5370f186-0028-41f4-b436-c48575899fca`。最终 `unresolved_or_exhausted`，audit=false；LLM 11/24、repair 4/6、ANN 4/36。五个变量版本均为 1，只有 response pending。errors=[]，无 InputOverflow、无 handoff capacity rejection、无实际 audit。

planner Call 1 未保持末端原问题逐字一致，Call 2 已修复。Calls 3–6 的四个历史节点均成功，48 sources，14–18 引文，无 unresolved。尤其 constraints 明确记录未见时间/材料/技能限制，但没有把这种 absence 变成 unresolved；这与第 2 题形成具体建模行为差异。

- Call 7：18-source semantic_compose（8631 input）返回 response support，值精确等于一个公开选项，同时给出选项均不够适配的 unresolved；顶层 semantic_answer/prediction 为 null。此处是终端声明不一致，所有输出仍通过实际 schema。
- Call 8：terminal-only repair（7135 input）slots=[]，semantic_answer 精确复制 supported value，prediction 合法且匹配；格式一致性修复成功。它没有权限取消此前关于选项区分的 unresolved，所以 batch.complete=true 不等于整题可发布。
- Call 9：新的 semantic batch（9552 input）response 返回 sourced unknown/null，只覆盖旧 18-source issue 的 16 个来源，却声称解除旧 issue。unknown 不是 settled review，且旧覆盖还少 2；因此解除被正确拒绝，并产生同描述的 16-source 未决责任。
- Calls 10、11：7934、7962 input，原样重述相同 unknown。runtime 禁止该同批冻结行重述；实际 schema 均通过。Call 11 已有明确 omit restatements 的反馈，模型仍未遵从；不能全归因于 schema，也不能错误声称模型违反了此处并不存在的 not.enum。

最终保留 response 的 18-source、16-source evidence obligations 及 18-source failed batch，**hard unread 为 0**。所有 Reader 请求 finish=stop、usage matched；terminal 五次请求用了 shared_history_texts，未用 shared_review_texts。

初始 unresolved 表达相对选项适配难以区分，是现有 terminal 指导允许保留的真实主张。未看 gold，不能认定应选哪项，也不能把它等同于 case 1 的范围备注或强行选最像的选项。协议修复要让“已有支持”与“仍不能区分”的输出更一致；F/R 修复只能减少无效重述，**不能证明原 semantic 未决已消失或本题必成功**。

## 与第 1 题的比较和控制候选

| 维度 | 第 1 题 | 第 2 题 | 第 4 题 |
| --- | --- | --- | --- |
| 最早 Reader 语义问题 | 范围说明进 unresolved，未指出必要缺口 | 指出具体缺失约束，其必要性待核 | terminal support 与不能区分选项并存 |
| 原文 obligation | 50，复核 3，缺 47 | 49，复核 16，缺 33 | 18，后续 unknown 16；又留 16 |
| 冻结重述 | support，已有 schema 禁令 | support，已有 schema 禁令 | unknown，同批 runtime 禁、schema 未表达 |
| 实际容量后果 | 原 owner 80-source 保留；future target 多次 80-source 拒绝 | 保留 74，future target 85；repair 16644>16384 | 无容量失败证据 |
| 必要修复边界 | 不自动删范围责任 | 不自动判约束无关 | 不把 unknown 引用视为 settled、不强迫选项 |

`_handoff_failures`（2025 起）复制 evidence/failed obligations，却没有复制 unread_obligations；它通过 grounded 检查后直接 `_payload/_fits`。`_mandatory_scope_payload`（2208 起）真正运行前会禁止其他 query owner 的相关 unread。case 2 在 preference handoff 时 getaway 已有 binding 但仍有其 owner 的未完成工作，说明 grounding 与实际运行的 owner 权限是两种不同条件。case 1 也出现后续支持全部包含于既有 80-source 保留集、反复缩短引文却不改变整体闭包。当前 policy 明示：“父输入齐全但仍存在其他查询的范围或复核权限阻塞时，继续原有检查；本次没有新增这类阻塞的调度恢复。”故这里不能直接认定代码偏离既定设计。

若将来有意扩展该 policy，可以独立论证在只读 prospective check 中复用真正 owner/executability 判定：owner-blocked 未来目标的容量预测标为 advisory/deferred，保留证据与 pending；真正可执行的 compose/audit 仍严格查同一个原文闭包。需同时设计如何恢复原 owner 的工作，并专门测试当前冲突复核、owner 改变、同 query 未读范围、actual terminal/audit，不能简单令所有 pending 都绕过 admission，更不能让另一个 query 代为结清旧责任。本报告未实现或测试此候选，也不建议在本轮 F/R 补丁中变更此既定 policy。

## 已授权下一小修：F/R 分离的精确 API

新增输入 metadata，**不改变模型输出字段、runtime guard 或义务解除规则**：

```json
{"repair_scope": {"frozen_observation_ids": {"response": ["current_batch_id"]}}}
```

令 `F_v = sorted({rid for (variable,rid) in frozen if variable==v})`，仅输出本轮请求的 failed variables 中非空的项，整体为空则省略字段。`R_v` 仍严格由当前 `_offer_frozen_reviews` 的 slot references / complete rows 构成，满足 `R_v⊆F_v`。引用资格不从 F 推导。

1. **构造时点**：每个 batch 在 `joint_reading.py:2405` 初始化空 frozen。正常 observation 验证后加入；summary revision 来源/有效性失败在 2649、whole-value 分歧在 2659、handoff 拒绝在 2679 解冻。等这些处理全部结束，构造下一轮 repair_scope 时从最终 frozen 取 F，再做 offer、repair identity、wire selection、真实 token count。不要从本轮输出原始 observation 列表推断 F。
2. **schema**：按 variable 的 oneOf branch，对普通 `observations.items.properties.id` 设置 `not.enum = F_v ∪ R_v`。兼容旧仅含合法 offers 的输入仍保留 R 的既有禁止；新生产路径的 union 仍等于 F。`reviewed_observation_ids.items.enum` 继续只为 R；无 R 的变量继续不能引用。不得给 unknown/partial 生成 settled offers。
3. **prompt**：说明 frozen_observation_ids 是 controller 给出的本批次不可重述 ID；它只是禁止普通重述/修改，不是引用或解除许可。只有 frozen_observation_reviews 明确 offered 的 ID 才能走 reviewed_observation_ids，且仍要满足原文覆盖、scope、反证、unresolved 等 guard。
4. **wire/count**：新增字段留在普通 repair_scope，不注册压缩授权或新的历史共享。deepcopy/pack/unpack 必须原样保留；plain/packed 候选与最终发送请求都带它。该字段参与 semantic repair identity 与 schema/prompt 的真实 token 数；不只添加 schema 而遗漏实际计数，不读取线上服务来确认。
5. **batch/变量隔离**：Call 9 是新 batch，旧已知 route ID 此时不因存在历史而被冻结；unknown 通过本 batch validation 后，Calls 10/11 才禁止。v1 的 ID 不得限制 v2 的同名 ID。known_observations、retained failed rows、旧 batch、旧 durable records 都不是 F 的来源。只要 whole-value/source/handoff 已解冻，其原 ID 仍须可编辑；不要因它出现在失败草稿里再次冻结。
6. **runtime 边界**：保留真实 row guard、counter 保护、reviewed rows 校验和 evidence discharge 原样。合法新 ID 的 unknown 可以仍旧 unresolved；不能靠改 ID、保留空 unresolved 或引用一个 frozen unknown 把语义问题变成成功。

生产 fixture 最小测试应包含：

- 真实 `_read` 两轮：第一轮 sourced unknown/partial 验证后因义务仍未结清进入 repair；第二轮 actual request 明示该 ID 并由 actual schema 拒绝普通重述，R 为空，unknown/partial 引用仍无权；新字段出现前在 e02c8cc 基线上独立失败。
- 保存 case 4 Calls 10/11 结构 fixture：旧 schema 通过；加入实际 F 的新 schema 拒绝同一 unknown 重述；Call 9 作为新 batch不错误禁止旧 known ID。不得读取 gold/调用服务。
- support/contradiction/irrelevant 的 F/R 并存：正常 explicit frozen review 仍可用，重复到普通 observations 仍失败；旧 offers-only schema 禁令继续有效。
- 同 ID 不同变量、整个新 batch、durable 失败记录均隔离；F 仅包含当前 batch 已验证且未解冻的 ID。
- whole-value/summary source/handoff 解冻后原 ID 继续可改，合法 counter 仍被冻结。真实修复输入的 plain/packed round trip、repair identity 与实际计数均涵盖新字段。

反例与风险：真正必要的预算/无障碍限制缺失仍应 unresolved；真正相互抵触/无可区分选项不能强制支持；unknown/partial 永不因在 F 中而获得 settled review 权；schema 只是显式约束，模型仍可能违规。新增文字有 token 成本，测试应确认容量 gate 仍诚实，不扩预算、不删除原文或义务。该小修完成后需用新的源码测试凭据，不能沿用先前 selector 版的 Full25 结果宣称新补丁已通过。

## 审阅修订

初版 MD SHA-256 `b94a75949f3c2c161d0d279b24931d56f32efad1591d594704f2f6f79f9e058a`。root 复核既有 `HANDOFF_EXECUTABILITY_POLICY.md` 后，本版将 owner-blocked handoff 的解释更正为**已声明范围之外的未来 policy 扩展候选**，撤回“新控制一致性问题”的定性。底层集合、事件和源码行为证据未变；证据 JSON 未改。该修订不改变已批准 F/R 协议表达补丁的范围。
