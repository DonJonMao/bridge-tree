# ordinary history 未读范围与充分支持的契约核对

## 结论与判定等级

**已确认的实现事实：ordinary history `document_windows` 会把本次已选择候选文档中的未处理原文登记为相关变量的 unread obligation。即使前一个窗口已产生合法、有来源、当前有效的 summary，后续未处理窗口仍使该变量 pending；当前没有“有充分 support 就解除同变量其余 unread”规则。** `read()` 会继续处理本次窗口队列，直到读完、失败或额度/容量异常。若相关纯 unread 留下，其余事实仍可保留，但实际使用该变量的发布路径会阻塞。

**这不是原理论必然要求的“充分证明必须先读完 local pool”，而是已经写进现有工程文档的保守完成策略。** 原设计要求区分未读、未知、无效与无关，保留待读范围，并允许保守活跃集合偏大；它没有规定所有检索候选都必须成为同变量的强制取证义务。另一方面，原文也没有给出一条足够具体的规则，授权只凭一条 `support` 自动判定同变量尚未读取的候选不再相关。因此，本次不能将这一策略判为违反当前显式工程契约的确证 bug，更不能据此直接清空 unread。

更准确的分类是：**代码与当前工程契约一致；相比“按当前充分依据停止”的高层目标，确实增加了一个局部候选读取完成门槛。该门槛是否应在某类合法充分证明后不再阻塞，仍需明确任务级充分性与剩余未读范围的关系。现有文档不足以支持通用自动解除。** 已观察反证、带源未决证据、失败草稿更不能与纯 unread 混为一谈后一起删除。

## 审查身份与范围

- RECONCILE：`8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`，`/Users/mao/projects/dagv2-personamem-v4-reconcile`。
- RELEASE / R17 源基线：`bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`，`/Users/mao/projects/dagv2-personamem-v4`。
- 只读源码、已有测试、指定设计文档和原 PDF 已存提取 `method.txt`。没有新建测试、运行测试/模型、访问服务、读取评测答案或修改实验。只写本报告。
- 当前范围不验证哪个真实未读片段必要，不测量全量收益，不提出实施方案。以下代码行号对应 8dac；bcbd 对应主体虽行号不同，但所审义务语义相同。

## 1. 三类问题确实分开保存，但发布 pending 将其合并

| 状态 | 何时建立 | 它证明了什么 | 当前解除方式 |
|---|---|---|---|
| `unread_obligations[(query_identity, source_alias)] = variables` | 本次 read 选中原文后、实际分窗/模型读取之前 | 此读取身份/变量范围还有未完成原文处理；不表示模型已发现矛盾或不足 | 该 identity 的该 batch 完成处理后 pop；若处理失败则另存失败义务。仅有其他 support 不会解除 |
| `evidence_obligations`，有 `source_ids` | 已读响应含 `partial/unknown` 或 `slot.unresolved` | 模型已经报告了具体未解决事项；`unresolved` 因无逐项引用图而保守携带本次全部 visible 来源 | 显式 offered ID、原文可见、sourced settled review 覆盖、无剩余 unresolved/partial/失败 |
| `failed_obligations` / `failed_batch_reviews` | 已尝试读取但协议、来源、整值或 handoff 等校验失败 | 某批已经产生的草稿/槽位尚未合法完成，可能含反证 | 既有付费恢复与完整校验/handoff 契约；不因另一次成功响应自动抹掉 |
| 无来源 missing-support gap | 模型尚无支持，但没有带来源未决事项 | 搜索缺口，不是已观察反证 | 当前代码允许合法 scoped support 且无 partial/unresolved/失败时自然解除 |

源码：[初始化分类与 pending union](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:292)（292–342）；[证据义务更新](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1675)（1675–1743）。

这里的 unread 是“此身份下尚未完成处理”，不应夸大为“这份文字此前绝未在任何别的上下文出现”。身份与变量范围独立记录，同文在其他查询下读过也不能自动完成本次工作。

`pending_variables()` 对 unread、failed 与 evidence 的变量做并集。分类没有丢失，但后续发布检查只要碰到相关变量 pending 就阻塞，并不再区分“只是未读”还是“已观察真实冲突”。

## 2. 为何一个 supported summary 仍可能必须继续读

1. 控制器把当前任务 local pool 与必要父文档送入 reader；新 bridge 批次也可单独送入。因此准确范围是**某次调用选中的 `doc_ids` 中、该 identity 尚未处理的 source aliases**，不等于整库、mapper 中所有资料或永远增长的全部检索前沿。[controller 调用](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:670)（670–714）
2. reader 在分窗前从这些文档选 aliases，并将每个 alias 关联本次请求 variables。这里没有等模型判断该 alias 是否必要才登记。[aliases 与入场登记](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1968)（1968–2003）
3. `while pending` 按实际容量读取前缀窗口。即使支持已成立，未纳入当前 batch 的 aliases 仍进入 `prospective_pending`。Handoff 可以做剩余求值和准入检查，但它使用这份保守 pending，不是“summary 足够就放弃队列”的控制分支。[prospective pending](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2292)（2292–2306）
4. 本批有效事实与反证一起整合；只 pop 本 identity 的 batch aliases，剩余 unread 继续进入 state.pending。成功不会触发充分性早停，函数在有 failures 时 break，否则继续队列。[本批提交](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2393)（2393–2421）；[循环退出](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2456)（2456–2458）
5. 若下一个窗口不能放下，reader 保留 unread 并抛 `InputOverflow`。**已有事实仍有效且变量同时 pending** 是合法表示，并不代表已接受 summary 被撤回。[容量失败](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2004)（2004–2017）

已有离线测试直接固定了该行为：[test_later_capacity_failure_retains_unread_suffix_and_already_accepted_history](/Users/mao/projects/dagv2-personamem-v4-reconcile/tests/test_v4_adaptive_initial_cap_review.py:266)。它保留 `state.valid()['history']`，同时 `state.pending == {'history'}`，仅剩 s3 unread 且没有 failed review。本次仅阅读该测试，没有重跑。该例足以证明纯 unread 自身可阻塞，不必假定另有模型未解决证据。

## 3. 阻塞的是实际使用范围，并非所有未读都会否决所有答案

[FactState.valid()](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/fact_state.py:132) 按有效路线、值一致性、scope 和父版本选择充分 route，不因 pending 删除 binding。因此 `supported` 与 pending 并存是真实设计。

发布的第二道检查更严格：

- 符号 `certify_output()` 拒绝 reduction 实际使用变量中的 pending；controller 再拒绝其 actual parent closure 中的 pending。[residual.py:500](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual.py:500)，[controller.candidate:47](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:47)
- 语义 `semantic_inputs_current()` 要求实际 terminal dependency 全部有效且没有 pending。[residual_control.py:211](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:211)
- `active()` 会把相关 pending 任务继续激活；合法 task projection 可消去未使用 sibling 的工作，记录仍留存。[residual_control.py:315](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:315)
- mandatory compose/audit 不能通过改读取模式或换 identity 清掉已有相关 unread，foreign owner 或本次闭包不能覆盖的旧工作会拒绝。[joint_reading.py:1910](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1910)

因此“有 unread 就必须遍历所有任务才能出答案”不准确。**已合法消去且不在当前实际依赖中的分支可以保持未读；本题仍实际采用的同变量绑定，即使 supported，纯 unread 仍是完成门槛。** `local_complete()` 只看有效值/局部投影，不能代替真正发布检查。

## 4. 原理论逐项意味着什么

| 文档原句 / 位置 | 支持的结论 | 不能由它直接推出的结论 |
|---|---|---|
| 4.2：“活跃需求是仍可能影响所需输出或其必要来源核验的需求”；“化简可以多保留某些暂时判断不出的需求” | 完成应受任务/依赖语义控制；保守多保留允许存在 | 不能证明每一个被检索候选都实际相关；也不自动授权将它们全部判无关 |
| 6.2：“格式无效、语义未知、明确无关、尚未读到是四种不同状态” | 未读不能冒充未知、无关或失败；事实与待办应区分 | 不能把同一个 pending 标记当作模型已发现反证的证据 |
| 6.2：“一个阅读批次中的有效事实和反证…作为同一批观测…整合，再统一求值” | 必须完整处理已返回同批观测，不能第一条 support 就忽略后续 counter | 不能从这里推导未发给模型的所有 local windows 也必须读完；“同批”并非整个候选池 |
| 6.3：“正文过长时显式分窗或拆批，记录待读范围” | 未读范围不能消失或假报已读；容量错误应可追溯 | “保留待读记录”不逻辑等于“这些记录永远阻止当前充分输出” |
| 6.3：“第二批…重现…所必需的旧原文”“不能省略关键反证” | 保留共同前提/相关反证，控制窗口真实成本 | 不能因容量紧张清空已观察未决证据；也未提供同变量未读的统一充分性豁免 |
| 7.3：审计针对“当前输出采用的支持及已知相关反证”；“不要求所有已检索原文都先完成与所有规划节点的映射” | 理论没有全部候选 × 全部节点穷尽映射要求 | 这句话禁止的是全交叉映射，不等价于明确允许跳过当前实际需求自己的 local unread |
| 7.3：“无关节点未解不能自动否决一个已有充分依据的输出” | 合法消去分支可以保留未解而不阻塞 | 不能只凭 summary 已 supported 就把同变量剩余原文宣布无关 |

精确来源：[4.2](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:147)、[6.2](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:208)、[6.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:214)、[7.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:238)。

原设计 3.5 还明确证书不证明没有尚未检索到的反证，开放偏好建议只能是 semantic assessment；因此“为了理论安全必须读取所有潜在反证”的说法过强。但这条条件性保证并未定义“已进入当前读取工作队列的未读”和“尚未检索资料”的完整等价规则。[理论边界](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:133)

## 5. 原 PDF 与 PersonaMem 提示支持充分性，但没有提供通用解除规则

原 PDF 提取 [method.txt:23](/Users/mao/projects/dagv2/tmp/pdfs/a48_review/method.txt:23) 要求把确认事实代入剩余式。其具体例子在 [method.txt:92](/Users/mao/projects/dagv2/tmp/pdfs/a48_review/method.txt:92) 说：“因此备用包虽然没有查完，但已经不会改变最终输出，不再需要继续访问。”这里消去的是 `If(true,p,b)` 中的 b 分支；它不是“p 或 s 还有同变量未读窗口时，任何一次 support 都自动清待办”的例子。

当前 PersonaMem 指导也明确：history 需要 query-relevant sufficient evidence，不是全部经历清单；`personal_history_summary` 是可修订表示；unresolved 仅用于实际必要条件，不可杜撰假设性穷尽要求。[personal_task.py:47](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/personal_task.py:47)、[personal_task.py:87](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/personal_task.py:87)

这形成一个真实但应准确描述的张力：**模型可声明“当前来源已足以形成所求 summary”，控制器仍要求完成已登记 local unread 才把该实际依赖视为无 pending。** 它说明“summary sufficient”与“工程读取工作完成”不是同一谓词，不证明任意剩余窗口均已无用。

reader 已有一句“scoped sufficient evidence may resolve a missing-evidence issue without having read every memory”，但对应代码只自然解除**无 source 的 missing-support evidence gap**；不会迁移到 unread 或 sourced obligations。[joint_reading.py:111](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:111)、[joint_reading.py:1687](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1687)。已有 [source-free gap regression](/Users/mao/projects/dagv2-personamem-v4-reconcile/tests/test_v4_reader_review.py:301) 也对应这个窄范围。

## 6. 现有工程契约已经明确这项保守门槛

[DAGBT_RESIDUAL_MEMORY_V1.md:19](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/DAGBT_RESIDUAL_MEMORY_V1.md:19) 明写：“阅读义务按查询身份分别记录未读原文窗口与校验失败批次。窗口成功读取后只关闭对应的未读义务；失败字段、反证和其他查询的未读义务继续阻塞相关证书。” 同文还要求 checkpoint 保留分类，旧快照保守 pending。

[README_PERSONAMEM_V4.md:104](/Users/mao/projects/dagv2-personamem-v4-reconcile/README_PERSONAMEM_V4.md:104) 明写不能通过读取模式、新查询、checkpoint 清除旧 unread，闭包不能覆盖原 owner/scope 时拒绝。这与现行实现及既有测试一致，不是未记录的偶发行为。

原 Goal 的 [6.2–6.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/CODEX_GOAL_RESIDUAL_MEMORY_f4e38df.md:194) 还规定未完成判读槽位“若它可能影响证书或揭示相关反证，不能忽略”；但“可能影响”本身仍需要保守建模。此处未给出将所有普通检索命中一律必要或一律可放弃的规则。

审查 bcbd → 8dac diff 以及 AST 对比确认：`pending_variables`、snapshot/restore、`_update_evidence_obligations`、`local_complete`、`semantic_inputs_current`、`grounded`、`active`、`read_progress` 均未改变；普通 document_windows 的登记/逐窗关闭/循环继续语义也未修改。8dac 的 terminal/audit 投影并不修订这一策略。

## 7. 本次能确认与不能确认的边界

- **能确认：** 存在 pure unread + supported summary 的保守 pending；本次 selected local pool 的剩余窗口会继续读取；后续容量失败可在没有 failed review 的情况下保留有效 summary 并阻塞其实际依赖发布。
- **能确认：** 这比单凭当前合法 sourced support 判局部完成更强；原理论没有证明该更强门槛是必要条件；原高层充分性目标不能被写成“要求读完所有检索材料”。
- **不能确认：** 该门槛违反现有工程契约。文档和测试明确支持它，原设计又允许保守需求偏大。
- **不能据此自动解除：** 同变量任何 support 后的全部 unread、已读 sourced unresolved、失败草稿或 counter。支持记录、语义充分性判断与对剩余工作的合法排除是不同证据。
- **已经合法的例外：** 与当前证书实际依赖无关且被合法表达式消去的分支可以保持未读；无 source 的纯搜索缺口可被 scoped support 解除。这两条现有规则不等于同变量 local unread 的通用豁免。
- **仍缺的理论明确性：** 当前资料不足以断言什么形式的历史充分性判断可以让某一实际依赖的剩余普通 unread 从“发布阻塞”变为仅保留记录。此处记录边界，不提出代码实现或新实验方案。

本报告不把该策略归因为 R17 全部失败，不声称修改它会降低来源数或提升准确率，也不以容量压力作为省略证据的理由。

## 版本哈希

```text
RELEASE dagbt/joint_reading.py
41f84e8eccdaa527c753fb6ad7345e83131d00cac1bd1de29c81fd02362c0391
RELEASE dagbt/residual_control.py
468223d3a3f0e5995d2ef01464a01d253f6caae57f2bccb594ddb17c716f2330
RECONCILE dagbt/joint_reading.py
8f23b7c8673d9a6c8ca2803753c58e04e014f0046db5343690ce2b577e3bb103
RECONCILE dagbt/residual_control.py
1d281f04f9e20ba042844afab134c53f52923b7618800a29dcc2a68d5009329c
docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md
615a609af60085d3ea022a0ba6ea75b8e8677e551cfb71e67f39d6c6baddb22f
docs/CODEX_GOAL_RESIDUAL_MEMORY_f4e38df.md
ee1ce89a350be9008b530249deb12d210beeb1a7ca3fb87291809dd3ce86d4f4
docs/DAGBT_RESIDUAL_MEMORY_V1.md（两工作区相同）
dfff59314d7c53bea3a3497bf76eefa440c87ef885f8e741c107c453fb6e7f07
RECONCILE README_PERSONAMEM_V4.md
4c87b4437e93bdcc9c9265bba044be0e1c6e2b8659d6130cdc1035547ebcaee9
dagbt/personal_task.py（两工作区相同）
7af9cc43b08364ea824c23c4aa2072395720ff945fb1499f62956bd4d889a9a3
原 PDF 已存提取 method.txt
933086f8cf9b027dcb9de0499daf30a4518d85c663252e95ba9c7996693d90b5
```
