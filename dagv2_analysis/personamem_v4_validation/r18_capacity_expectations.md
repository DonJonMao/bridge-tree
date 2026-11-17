# 8dac 候选对 R17 前两题容量失败的可验证预期

## 结论

**现有结构证据不支持“8dac 会解除 R17 前两题的容量失败”这一预期。** 它修正了 terminal/audit 证明范围的契约，但两题已接受状态恰好都没有可由本次普通等值 OR 投影省掉的路线：每个有值历史变量只有一条 active proof，其余路线是 summary 的退休祖先，祖先原文已累计进入当前 summary。第一题接受状态的来源并集为 37，第二题为 41；两题 retired-only 来源均为 0。

更直接地，已保存的七次 handoff 容量拒绝全部指向 `semantic_compose/response`，没有一次是 `audit_joint`；两题真实 terminal 和 audit 调用数也均为 0。`audit_scope()` 从全部非终端收缩到实际依赖，不能被当作这些既有拒绝已经得到修复的证据。开放语义终端仍需已声明的历史父任务，8dac 不通过符号短路消去这些输入。

这不是证明新一轮两题一定失败。失败时的全部 prospective wire 与当时义务/草稿状态没有在本次重建；模型新输出和轨迹也可能不同。当前能确定的是：**本次补丁对这两题没有已证实的必需来源缩减收益，也没有可报告的 token 降幅；真实完成改善仍未验证。**

## 审查范围与身份

- R17 实际源版本：`bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`，路径 `/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r17`。
- 候选：`8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`，路径 `/Users/mao/projects/dagv2-personamem-v4-reconcile`，审查时工作区干净。
- 只读取前两题已结束的 `result.json` 结构字段、现有结构报告、候选源码和源 diff。没有读取评测标签、选项或预测；没有输出或解释模型自然语言、原文及 typed values。
- 没有 HTTP、tokenization、模型重跑、测试重跑或运行文件修改；没有改变 release、预算、配置、live R17。只新增本报告。

## 两题已保存的失败事实

| 项目 | 第 1 题 `acd74206…` | 第 2 题 `f546a74f…` |
|---|---|---|
| 结果状态 | `unresolved_or_exhausted` | `unresolved_or_exhausted` |
| LLM / JSON repair 使用 | 18/24；6/6 | 13/24；5/6 |
| 真实 history / repair 调用 | 11 / 6 | 7 / 5 |
| 真实 terminal / audit 调用 | 0 / 0 | 0 / 0 |
| handoff 拒绝 | 4 次，均为 `semantic_compose → response` | 3 次，均为 `semantic_compose → response` |
| handoff 记录的 source spans | 37、37、37、44 | 71、71、71 |
| 最终 accepted 来源并集 | 37 | 41 |
| accepted active / retired 路线 | 3 / 2 | 2 / 2 |
| 最终 pending 变量 | `preference_changes`、`constraints` | `getaway_constraints` |
| 另一个直接容量阻塞 | 无记录的 history `InputOverflow` | `getaway_constraints` history `InputOverflow`，27 个 unread groups |

注意：handoff 71 与最终 accepted 41 不是同一份输入。前者含当时 prospective 草稿/复核义务；后者仅计最终接受的 routes。不能将二者相减得到“30 个可删来源”，也不能将第一题 44−37 当作冗余。

第一题还记录了 3 次 history 输出截断，初始输出 cap 为 445、395、352；一次 summary 修订缺失原来源的 repair 要求 19 条原来源、缺失 13 条。最后两次 repair 被 mandatory downstream capacity 占用。第一题实际发送的 17 条 reader 请求全部没有 `shared_history_texts`；不能归因为模型误读共享引用。该 wire 报告不覆盖未发送的 prospective handoff。

第二题失败类别包括 2 项 `obligation_resolution_conditions`、1 项 `mandatory_downstream_context_capacity`；历史恢复阶段还持有相关 failed review 与 evidence obligations。这些义务不能因终端投影而被自动完成或删除。

## 为什么本次投影在这些状态上没有可删的普通 OR

[路线 ancestry 报告](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r17_first_two_route_ancestry_review.json) 与两题 result 的结构一致：

| 题目 / 历史变量 | accepted / active | 当前 active 来源数 | summary 祖先来源变化 | 只存在于祖先的来源 |
|---|---:|---:|---|---:|
| 1 / `music_preferences` | 1 / 1 | 16 | 无修订 | 0 |
| 1 / `past_events` | 2 / 1 | 25 | 19 → 25 | 0 |
| 1 / `interests` | 2 / 1 | 29 | 16 → 29 | 0 |
| 2 / `creative_history` | 2 / 1 | 38 | 17 → 38 | 0 |
| 2 / `current_attitudes` | 2 / 1 | 20 | 17 → 20 | 0 |

候选 [_proof_known()](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:477) 只略去 active、未选中、等值、同 scope/新鲜父版本、无 revision/counter/义务保护的普通 OR 备选。上表所有 active 路线均是当前 selected proof；另外四条退休祖先因 `superseded_by` / 非 active 被保留，四条替代 summary 因 selected 且有 `summary_revision` 被保留。所以在完整 accepted 路线范围内，**投影可略去的路线数为 0**；来源并集也没有通过删除普通 OR 缩减的空间。

即使单独设想去掉退休祖先的元数据，它们也没有任何独占原文可省；当前 summary 继承的 `source_ids` 仍必须完整保留。本补丁实际上连这些祖先 metadata 也不会移除。

失败记录中最后保留的 `preference_changes`、`constraints` 草稿各是 1 条 support，分别有 12 和 9 条 source、无 summary revision；`getaway_constraints` 最后记录有 1 条 12-source support 加 1 项 slot 级失败。对应变量在最终 accepted state 没有历史 route，可见材料未显示“已有更窄且独立充分的等值 route 可以代替失败草稿”。每次 handoff 事件的 `support_draft_ids` 数也均为 1。这里不据此推断各中间草稿的全文、精确原文重叠或语义充分性。

## 按失败机制判断 8dac 的作用

| 机制 | 8dac 修改的边界 | 对本两题的证据判断 |
|---|---|---|
| 普通等值 OR 原文随 terminal 一起膨胀 | 当前请求采用 selected proof，备选仍归档；相关反证/义务保护 | 两题 accepted 状态无此类可略去 OR；没有已证实的省源收益 |
| audit 无条件带所有非终端 | `audit_scope()` 改为实际证书/语义依赖，任务投影不越界 | 两题既有七次拒绝均是 compose；未到实际 audit，不能归因为此，也不能宣称已解 |
| semantic compose 的声明父历史 | 一般语义输入继续接地，保留所有相关的声明父与 actual ancestor | 第 1 题 response 的父任务正是全部 5 个历史任务；第 2 题是全部 3 个。它们没有已认证的更窄终端依赖可应用 |
| summary 修订累计原文 | selected summary 的来源、祖先与 counter 关系继续保留 | 上表累计 25/29/38/20 等 source 不因投影减少；仍可能超过单窗 |
| history 输出截断 / summary 缺源 repair | 历史抽取与中间历史 summary 不启用这次投影 | 首题该直接机制没有被 8dac 修改；不得预报其 repair 消耗自动降低 |
| history 恢复需要旧义务、failed drafts 与来源 | 仍完整复核；`document_windows` 不用终端投影 | 第 2 题 history `InputOverflow` 不在本补丁直接缩域范围内；其 27 groups 不可自动丢弃 |
| 当前 terminal 未决时父原文存在独立价值 | pending/evidence/failed 输出保护父与实际祖先备选，parent-only repair 同样保护 | 即便其他轨迹存在 OR，也不能预期一律取最少来源；必须保留解决当前 gap 所需范围 |

两题 `contract.mode=semantic` 且 expression 是 `var(response)`。证书中的 `false AND sibling` 一类合法确定性消去不能套到这里。源码依据：[compose handoff 的声明输入范围](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1795)、[投影与 obligation 范围](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:499)、[audit_scope](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:425)、[mandatory 单批与 history window](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1984)。

## 下一轮应验证什么，不能预先声称什么

1. **机制预期应设为有条件：** 出现可投影的普通独立 OR 或已认证的 audit 外依赖时，候选应减少该次 payload 的冗余范围，且保持所选 AND、累计 summary、反证与未决义务。对前两题当前保存状态，该可省 OR 数是 0。
2. **前两题应作为仍有容量压力的回归例：** 比较自然结束状态、history 截断/repair 消耗、具体 handoff 操作及容量拒绝、是否真正进入 terminal/audit。记录同次调用的 selected proof / ancestor / counter / obligation 分类后，才能归因容量变化；单看最终 source 数或答案成败不足以归因补丁。
3. **没有精确改善量预报：** 本次没有重建 7 个 prospective payload，没有重算 token，也没有模拟新模型回复。报告不预测 37/44/71 将变成哪个更小数字，不把 accepted state 的投影零变化推成完整运行必定零变化。
4. **仍有的设计容量限制：** 当前契约要求 mandatory compose/audit 的完整充分原文闭包在一次实际请求内放下，还需协议/输出/repair 预留。累计 summary、多个声明父、复核原文可能在没有冗余 OR 时已经超出 16k。若发生这种情况，继续保持 provenance 的本补丁不能凭空让其装下；结果应继续明确未决/容量失败。改变这种单次联合可见性或 summary 来源契约属于后续设计变更，不能伪装成本次投影的自然收益。

## 证据与哈希

结构报告：

```text
r17_first_two_route_ancestry_review.json
  9ac27cacf07aa2a925ab834716a542aedc26d4e9d89af665becae9c6ee19f922
r17_first_case_wire_review.json
  60bdd4d95a0cd019c7d26e30d20b0851ec42a3987070d467ae252332883875ba
r17_first_case_review.json
  35100d283ffa67c7627a670dd17552788d8b6d6649111a3f70a074c4ab629770
r17_structural_monitor.json（读取快照；live monitor 后续可更新）
  149b3f13a97eaf92f2766b2c83fd91742c4fab4784ad4df311be2b67b03a4b6c
```

第一题 attempt 目录 `personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001`：

```text
result.json        9f9d4fa86e3da0b63902c58dc184e2b1db41f1e1bad9ea47cde2f099ab41aa5e
fusion_events.jsonl 8657f7c62ee1f87379d04e00f89903fa9041ba3d329adcc576b39e3a1d92beab
handoff sequences  585, 599, 613, 635
```

第二题 attempt 目录 `personamem/dagbt_residual_memory_v2/attempts/2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0/attempt-001`：

```text
result.json        86f37dcecd1d6b6981bb06da8336aa2efbca56b721b7b9244dcdf5b85d4a2358
fusion_events.jsonl 39735dd2261485de9835cfbf392d5f353470b8c1dce623acd1cf624b05bba9b0
handoff sequences  254, 268, 282
```

以上仅作结构和因果主张边界审查，不构成答案准确率、语义证据充分性或候选已能完成两题的结论。
