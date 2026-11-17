# R20 第 10 题：失败链与实现契约窄查

固定 question index 9，unit `60023d63-4f11-47dc-8cef-82e3ca665a68`；R20 冻结源码 `6c046374008ce2e45f817d6bc9876b3ab927ab18`。只读本题自然失败后的 canonical row、实际保存请求、事件与相关函数；另对保存请求中的实际 schema 做离线校验。未读标签/分数，未调用模型或 tokenizer，未更改源码、测试、运行或守卫。下文不导出题目、记忆、摘要或答案文本。

**未确认一个超出已知 F/R schema 漏表达的新实现契约矛盾。建议按既定固定验证范围直接验证已测试的 e667，不为本题增加推测性修改。** e667 能补齐本题 Call 6 的冻结禁止规则；不能替模型解除未决项，也不保证解决后续容量失败。

## 1. 实际起点与三类独立问题

局部 planner 的 `getaway_constraints` 明确要求时间、预算、地点信息。Call 4–7 始终保留相同三个对应未决描述，顺序虽变、集合未变。它们有局部子问题依据，与 R20 第 1 题仅描述已读范围的未决项不同。但这不证明 planner 要求的每个字段都是最终输出必要条件，更不能因此自动删项。

| 调用 | 已保存请求/响应事实 | 判断 |
| --- | --- | --- |
| 3–4 | 首次两个历史阅读分别曝光 48、47 个来源；Call 4 保留三个未决项 | 此处不出现冻结重复。 |
| 5 | 新的 71-source 批次提交合法可审的 summary revision；仍有三个未决项，却请求解除旧 47-source obligation | 新批次复用旧 known route 不属于同批冻结重述。非空 unresolved 与声明解除已违反实际 schema。 |
| 6 | 普通 observation 完整重述 Call 5 已被冻结的 support；无 settled reference offer，schema 也未给该 ID 禁止规则 | 已知 F/R 缺口：不可重述集合大于可引用集合。它同时仍违反 unresolved 的 schema 条件，因此不能称整份响应本可通过全部 schema。 |
| 7 | 再次返回相同 observation；已有 explicit settled offer 和 `id.not.enum` 禁止，却同时普通重述、引用，且保留未决项并宣称解除两项义务 | 这是已有明确 schema/运行期规则下的不遵从；e667 不会使该响应合法。 |
| 8–10 | `creative_preferences` 三次完整返回相同 `cp1`，均被 79-source synthesis handoff 容量检查拒绝 | 该草稿因 handoff 拒绝退回可编辑，Call 9 重用 ID 合法；Call 10 是新的 durable recovery 批次，也不能从旧批状态推导冻结禁止。 |

离线实际 schema 校验：Call 3、4、8、9、10 合法；Call 5、6 失败于 `slots[0].unresolved.maxItems`；Call 7 另失败于禁止冻结 ID 所在分支。此处“schema 合法”不等于证据充分或可准入运行期。

## 2. 保留责任与容量链

47-source obligation 精确等于 Call 4 全部曝光，71-source obligation 精确等于 Call 5 全部曝光；前者是后者的子集。Call 5 的 17 个引文对两个范围分别仍缺 30、54 个来源，且三个未决项未消失。解除不成立有独立理由，不能靠补冻结 schema 或把 unknown/partial 视为 settled 解决。

最终 getaway failed batch 等于 Call 5–7 的 71-source 窗口；preferences failed batch 等于 Call 10 的 99-source 恢复曝光。已有 71-source 保留范围与历史、偏好支持引文的并集恰为 79，与三次 synthesis handoff 拒绝事件一致。这些来源责任有重叠，不能相加当作独立缺失事实数。

事件 sequence 217 的 synthesis 尚缺未绑定父任务，正确记录 advisory/deferred。后来 sequence 407、421、450 记录严格容量拒绝。窄查 `ResidualControl.grounded` 与真实执行循环表明：父变量有有效绑定即可接地，pending 本身不使 query 必然为 None；handoff 使用同一 grounded 判据。因此目前没有证据把后面三次拒绝认定为另一个“不可执行未来目标错误否决当前草稿”的实现矛盾。

sequence 422 因失败草稿及反馈未变停止当前重复修复；sequence 452 的下一次真实修复预检为 `12338 + 4096 + 256 + 8 = 16698 > 16384`，超出 314 token。该请求未发给模型，随后仍保留未完成责任。

## 3. 结论与下一步

最终状态为 `unresolved_or_exhausted`，pending 为 `creative_preferences`、`getaway_constraints`，audit 未完成；实际 terminal semantic-compose/audit 请求均为 0。LLM 用量为 10/24，JSON repair 为 5/6，ANN 为 3/36，不能把本题概括为“总调用预算耗尽”。

八次实际 Reader 请求均 `finish_reason=stop` 且 deployment tokenization/usage matched；发送内容均无 `shared_history_texts`、`shared_review_texts`。本报告没有逐个重建未发送的容量探测候选，因此不推断所有探测都没有 codec，也不把失败归因于新 wire-selection 逻辑。

e667 补齐的是当前批次最终冻结集合 F 的 schema 禁止表达；可引用 settled 集合 R 仍独立，未决/partial 不获得引用或解除权限，新批和 durable recovery 也不继承旧冻结。本题为已有改动提供额外适用证据，没有提供扩大修复范围的依据。直接验证 e667 后应如实记录剩余语义、遵从和容量失败，不能承诺本题成功或准确率提升。

结构证据：`r20_case10_contract_failure_review.json`，SHA-256 `2252735572aa015c4671ecdef73322a3c23ccefa20225d1c70f74cb09bfeea48`。包含 row/source/request hashes、离线 schema 结果、集合等式、最终预算与选定事件，未包含原文或标签。
