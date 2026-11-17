# R19 第 1 题：容量与 owner 阻塞只读核查

对象：`acd74206-37dc-4756-94a8-b99a395d9a21`，源码 `0cc2cc78498bcd215252fb8e82d2168868a71b3f`。仅分析已保存轨迹与源码/设计；未读标签或评分，未调用模型、网络或 tokenizer，未跑测试、改源、停止/重启运行。没有导出问题、选项、原文或模型摘要。

## 结论

1. **constraints 下一合法恢复窗口的容量超限已确认。** 最小已检查 prefix 的 77-source 请求，完整预算为 `12391 + 4096 + 256 + 8 = 16751`，比 16384 超 **367 token**。48 个 prefix 全部被计数，没有只试大窗口便放弃。
2. **response 的直接错误是 scope/owner 阻塞，不是已经测量出的终端容量超限。** constraints 留有 75 条真实尝试后未完成的 hard unread；response 当前请求包含其父变量，因此在 mandatory scope guard 被拒绝，尚未进入真实终端容量计数或生成。
3. **不能据此声称整道题或 75 段必要原文在 16K 下天然不可行。** 之前同 75-source 的实际 repair7/8 分别以 11229/10911 input 成功入场；后来保留 durable failed record 后的候选输入更大。剩余全局预算仍有 16 LLM、4 repair、32 ANN。
4. **确认存在通用的无损 wire 表示优化机会：同一长值和解释在不同元数据角色中重复序列化，而现有 sharing 不覆盖 durable failed-batch 部分。** 这些角色不能删掉或合并语义；目前没有新表示的完整 token 测量，不能保证净省 367 token、恢复成功或答案正确。
5. 未发现此次 scope guard 错将无关 owner 的材料当成终端依赖，也未发现纯候选被强制作为 75-source 的原因。新的未接地 handoff 策略在本例没有产生 rejection 或 deferred 事件，不能将此次失败归因于它。

## 事实链与状态区别

计划有四个无父输入 retrieval：`attended_events`、`music_preferences`、`cultural_interests`、`constraints`；`response` 是依赖这四项的语义 compose。

前四次历史读取（call2–5）分别取得合法支持，最终来源数为 6、19、17、8，四个历史变量版本均为 1、response 为 0，没有已整合 contradiction route 或 revoked route。constraints 的 call5 同时保留一项带 **50-source** 的 unresolved evidence obligation。`joint_read_completed.complete=true` 只表示该批没有协议失败，不代表这项语义义务消失。

constraints 随后读取另一窗口（call6，实际可见 75 段），并执行 call7、8 两次 scoped repair；仍留下 frozen observation 普通重述的槽位失败。reader agent 独立负责其 schema/draft 契约诊断，本报告不以“容量”替代该较早的协议错误。

最终保留：

| 对象 | 数量/范围 |
| --- | --- |
| constraints 合法支持 | 8 source，版本 1 |
| constraints evidence obligation | 1 项、50 source、1 条描述 |
| constraints failed batch | 1 项、75 source、1 个 validated observation |
| hard unread obligation | **75 条**，同属 query `126f244edfaa76f76bd28e89f85b58026df8cd3055726a43229efa605073e99e`，变量均为 constraints |
| pending | 只有 constraints |
| 容量失败后的剩余候选 | **48 个邻接 prefix 组**，不是 48 条 hard unread |
| 全局剩余额度 | 16 LLM、4 JSON repair、32 ANN |
| terminal / audit 调用 | 0 / 0 |

50-source obligation 是 failed75 的子集，support8 也保留。75 段曾真实进入 call6/7/8 的请求；这里不能把它们重新标为从未尝试的 discovery，以使终端通过。其余未发送候选仍按 frontier 保留，不等于事实或语义义务。

## 精确容量证据

call6 的 fresh-history 预检采用既有自适应输出 cap 651，真实 input=9998，总量 10913；该选择预测可留出后续 4096 repair output，并不保证未来生成的失败元数据始终可容纳。call7/8 均保留正常 4096 output reserve，实际完整总量 15589/15271，能够入场。

event358 结束失败批次后，`_fitting_prefix` 对剩余 48 组按 length-first、二分、未试 prefix fallback 的冻结顺序检查。event359–454 恰有 **96 条**计数，即每组 initial/repair envelope 两项。failed-batch 已存在，fresh-history 自适应 cap 不再适用于这次 durable recovery；它仍需遵守原有完整 repair 额度和范围。

| 请求 | source | initial input | repair-envelope input | 加 4360 后 | 超额 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 最小 prefix1，events369/370 | 77，8 docs | 12303 | 12391 | **16751** | **367** |
| 完整 prefix48，events359/360 | 123 | 15296 | 15384 | 19744 | 3360 |

prefix1 只新增 2 段；旧的 75 段按稳定来源身份保留、去重，不是 50+75 重复原文。全部已检查 prefix 的最小完整总量就是 16751。所有这些计数均保存为 `token_count_is_estimate=false`；本报告没有重新分词。

关键保存请求身份：

- initial12303：`2258b373538f5fb023eca925e07e50f983415841738005a43ba9ada4e239336d`。
- repair-envelope12391：`fef9a210542e44605cd183baca93c2831ca226b65c0d8e7ab3338734f2fcda41`。

这是**当前序列化、完整修复预留、现有 pending/failed 状态和既定 prefix 顺序下**的实际容量拒绝。未保存/未检查的替代无损表示、无新增来源的假设输入、其他尚未桥接窗口，不在这项证明内。服务器记录的更大 max_model_len 不改变本实验的 16384 预算。

## 为什么回到 response 仍不能执行

event455：constraints 抛出 `InputOverflow: Local sources/parents/counters exceed real wire capacity`。控制器将这个 query/parent/program identity 加入 exhausted。

event456：四个父值均已存在，`grounded(response)` 可得到 query；但 `_read` 加入实际父变量，`_mandatory_scope_payload` 发现相关 constraints unread 属于另一 query，抛出 `mandatory_closure cannot settle relevant unread work owned by another query`。此处发生在真实 response `_fits` 之前。

这个 guard 符合当前契约：看得见另一 owner 的原文，并不赋予 response 对其历史 failed slot/未决事项的复核权限。constraints 也是该 response 的实际父项，不是被安全短路排除的无关兄弟。本例不能通过删除 owner、换 query、清空 pending 或让 terminal 代签失败恢复来“修好”。

全局预算未耗尽也不自动授权重复同一失败请求：当前 batch 的两次局部 repair 已用完，durable recovery 需要合法新材料/真实父变化及预算，且它自身要能入场。constraints bridge 保存为 initialized、仅 1 ANN、还有前沿；但控制器在本次局部 InputOverflow 后不会继续该 identity 的下一桥接。这是当前保守停止路径，**不是所有可能桥接或所有 16K 表示均无解的证明**。本例没有后续真实材料变化，因此也未证明发生了“变化后应重新激活却没有”的错误。

## 可证重复材料与理论契约的关系

`RESIDUAL_MEMORY_DESIGN_f4e38df.md` §6.2 要求有效事实和反证整批保留，§6.3 要求只带当前需求及必要原文/父项/反证、修复只处理失败字段且真实计数。frontier policy 要求保留已尝试未完成的 owner/scope，mandatory compose/audit 不拆散共同必要闭包。由此可做的优化边界是**无损表示共享**，不是减少事实、原文、义务或失败角色。

最终 durable failed record 与当前 known route 可直接验证下列字节相同的字符串：

| 字段 | 原始 UTF-8 bytes | SHA256 | 明确结构出现次数 |
| --- | ---: | --- | ---: |
| value | 766 | `3aec6e5a838b3c23faa280b0ce1667c5a87dc8423fe78ce50779eac389b4c901` | 3 |
| reason | 384 | `f0d36cb71a4ac12f8eea1ac09a3219e2513436901670ee69318d7b9d2e0f8baf` | 3 |

三处位置分别是 `known_observations[0]`、`failed_batch_reviews[0].failed[0].slot.observations[0]`、`failed_batch_reviews[0].validated_observations[0]` 的相同字段。`invalid_response` 是原始响应字符串，解码后还有第四份相同 value/reason。另有 summary_revision.reason 在两个结构角色中逐字相同；这些角色的 ID、来源命名空间和校验意义不能因为文本相等就合并。

本次 constraints 无父项，`history_wire.pack` 只从 supported_parents 的长 text value 选共享项，所以不覆盖这里。普通 `_wire_data` 的 known table 至少需 8 行，本例只有 1 行；whole-value review group 为空，其专门共享分支也不适用。`_failed_payload` 保留上述 failed/validated/raw 部分；它已去除 `seen_source_ids`，所以 snapshot 里 source_ids/seen_source_ids 的重复**没有算作 wire 冗余**。

上述重复由已保存记录与固定 `_payload`/remap 规则确定，字符串 value/reason 不受来源 alias remap 改写。本报告没有重建/反序列化未发送的完整 77-source 计数请求，也没有拿保存 JSON 字节数当作实际 wire token 分解。可以确认当前实现有尚未覆盖的通用无损共享空间；不能说这些重复角色本身违反证据协议，更不能假设新解码说明和引用开销之后仍足以省下 367 token。

若 root 后续评审这一方向，需要的证据是：新表示完整 decode 后与原 canonical payload 相同；所有原文、owner、scope、版本、counter 和失败记录保留；invalid_response 如编码也必须逐字恢复；实际 initial 与 structured-repair 完整模板分别计数，含新增解码说明；全局/局部预算不变。即使表示能适配，仍需模型完成真实 scoped repair；不能据离线压缩推断任务或答案已成功。

## 可证明与未证明的边界

已证明的失败链为：带源未决事项保留 → scoped repair 后仍有协议失败 → 75-source durable 失败范围保留 → 77-source 最小下一恢复请求超限 → 当前 owner exhausted → 实际 response 因该 owner 未完成而被阻塞。

目前没有证据支持放宽 source/owner/pending/counter 语义。较早 frozen-restatement 的 schema/model遵从由 reader 的独立报告解释。容量侧已确认表示冗余的通用优化机会，但没有证明这项改动能修复本例；也没有证明该题在不变 16K、合法无损表示下不可完成。原设计 §5.4 本就不主张当前调度全局最优，§6.3 也未保证任意修复都能适配。

机器可读证据、48 prefix 对应计数、来源集合 hash 和源码/轨迹 hash 见 `r19_case01_capacity_owner_review.json`，SHA256：`6ef3edeaac2833fc1ac7b4c008aae552ad2dfc1ed51980df6ffc6b5f8e7e2216`。本题失败结果与正在自然运行的 R19 均未修改。
