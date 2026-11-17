# Mandatory-closure 模式的 unread 生命周期审查

本次仅检查现有源码和既有测试，没有修改源码或测试、执行模型或 tokenization、运行新测试、停止或改变 R15。本文讨论可能的新模式，不表示该模式已经实现或通过验证。

## 当前实际语义

`unread_obligations[(query_identity, source_alias)] = variables` 记录一个具体查询下尚未完成的 source-window 工作。它不是“这个原文在任何地方都没读过”的全局标志，也不同于已经阅读但存在验证失败的 `failed_obligations`，或有明确来源和问题描述的 `evidence_obligations`。

1. `read()` 先计算本次变量及实际父依赖。普通读取根据 doc_ids 枚举全部 mapped spans，并过滤当前 identity 已有 read_states 的 alias；audit 则仍重新读取。之后为所有选中 alias 登记当前 identity 的 unread。
2. 登记发生在容量选择之前。若 prefix 完全无法进入请求，未读标记保留，变量进入 pending；没有因为原文出现在其他请求就视作完成。
3. 处理一个 batch 后，仅移除 `(当前 identity, batch 中 alias)`。即便该次验证失败，已尝试窗口会离开 unread，但失败变量通过 durable failed records / failed markers 继续保持 pending。不能把 unread 移除单独解释为语义成功。
4. `_payload()` 自动加入 known observations、supported parents、任务投影、evidence obligations、failed reviews 和当前 identity clues 所需原文；**它不枚举 unread_obligations**。因此“出现在 visible sources 中”与“属于本次可结算的 unread 工作”目前是两件事。
5. reader 的 pending 是 unread、failed 和 evidence 义务变量的并集。`semantic_inputs_current()` 和 certificate 的实际依赖检查会阻止依赖 pending 变量的成功发布；独立且已被证明无关的分支仍可按已有规则短路，不能为新模式增加全局清空。
6. checkpoint 保存 unread 的 identity、alias、变量集合，也保留 read_states、failed records、clues、controller read_attempts/read_effects。恢复或重命名 query 不会自行解除旧义务。

## 新模式必须分开的两个集合

- **请求必须可见的原文闭包**：为本次 compose/audit 重现实际证明、反证、待解决问题和已失败草稿所需的完整原文。
- **本次允许结算的工作集**：由控制器在调用前明确确定的当前 identity、source alias 和变量任务。原文仅作为闭包、邻接内容、引用或其他 identity 的原文出现，不自动进入这个工作集。

不能用 `batch=[]` 配合 `_payload()` 代替完整闭包模式：这样可见原文虽完整，已有同 identity unread 也不会被现有 pop 逻辑清除。反方向把所有 visible alias 对应的标记全清，同样错误，会跨查询或变量越权结算。

## 建议的最小显式接口

保留现有 document-window 行为作为默认；增加内部关键字参数，例如：

```python
read(..., source_scope="document_windows")
read(..., source_scope="mandatory_closure")
```

新值只允许明确的 semantic compose / terminal compose 或 audit 阶段。检索阶段不能借此跳过新检索原文；`doc_ids=[]`、方法名称、模型输出字段均不得隐式授予模式切换。具体名称可调整，关键是操作阶段、输入范围和记账范围显式且经过验证。

对于没有遗留 unread 的新查询，mandatory 模式应从真实 `_payload` 的完整闭包得到一个显式 batch，登记并处理它的完整工作集；不把父 source 转为整 doc，也不扩张邻居。若完整闭包无法容纳，原规则失败关闭，不截断、选前缀、减少默认 repair 输出或冒充已完成。

**本轮推荐的最小保守边界**是在任何 unread 注册或其他状态修改之前，拒绝以下情况：同 identity 存在闭包外 marker；同 identity 的 marker 登记变量未被本次请求全部覆盖；或存在与本次变量相关的 foreign-identity marker。拒绝时原 map、原文和 provenance 完全保留，交由旧作用域处理，不实现自动迁移。下文“并入已有工作”或“部分变量结算”只是未来可选扩展，不属于这个最小方案。

闭包本身是**一个完整显式 batch**，不再对每个 alias 生成邻接候选。可复用现有完整 `_fits` 准入及实际 repair 检查；此模式不启用 history adaptive output cap。设计仍待整轮 R15 完成后决定，当前不实施。

### 已有同 identity unread

- 在闭包内、且该标记登记的全部变量均由此次请求真实覆盖：可以明确纳入本次工作集，按已有成功或失败转移规则结算。
- 在闭包外：不得删除。可把这些**已经存在的工作**的原文并入这次完整请求，再做精确容量检查；如果不采用这个明确扩展，应拒绝用 mandatory 模式完成该旧工作，交回原 source scope。
- 一个 marker 若登记了多个变量，而本次只请求其中部分，不得按 alias 整体 pop。最小实现可以直接拒绝这类模式切换，要求原作用域完成，避免引入新的部分结算 schema。若选择支持部分结算，则必须显式减去完成或已转入失败义务的变量，并保留其余变量，不能提前把 read_states 标为全部已读。
- 登记新工作不得覆盖丢失已有 marker 的变量集合。现有正常路径按当前 request 整体赋值的逻辑，不能未经核对就套用于跨模式旧工作。

### 已有异 identity unread

即使是相同 alias、曾在 history 读取、在 terminal 中再次可见、被引用、或 audit 返回 supported，旧 marker 都继续保留。它的原查询与依赖版本不同，本次阅读不自动代表旧任务已完成。

最小安全方案不提供跨 query 解除 API：有相关 foreign unread 时显式阻断或交回原查询的正常付费流程；它继续参与 pending 和发布检查。若为了另一个任务的独立进展仍允许本次阅读，也只能生成自己的结算结果，不能清除 foreign markers，更不能将本次成功当作旧义务迁移回执。

新实验输出目录可避免将旧 document-expansion 产生的标记悄悄迁移成新的闭包语义。恢复旧 checkpoint 时，应继续旧模式或失败关闭；不能把历史81个额外 spans 重新解释为从未有过的工作并清零。若未来确需迁移，那是另一个需要明确旧工作身份、范围与完成证据的机制，不属于此次最小接口。

## 失败、容量与重复调用边界

- 保留现有 failed-review readiness：同 task/phase、确有新原文或实际父状态变化、正常 LLM 预留与 JSON repair 预算。切换 source_scope、新 identity 或恢复 checkpoint 都不算新证据。
- 不把已有 invalid read_states 重新注册成普通 fresh unread 来获得一轮免费修复；retained failed drafts 仍必须走显式 paid recovery。
- 完整 batch 的容量失败发生在 generation 前：不移除任何原工作；实际请求失败后沿用 failed marker 转移及原文保存规则。
- `read_progress()` 的输入/效果去重须继续有效；新模式应纳入显式 options / 检查点语义。相同 mode、identity、原文和物质状态不能通过重复调用产生无限“新进展”。
- `_payload` 与 `_fits`/实际发送必须使用同一闭包和 metadata。保留 counter、failed originals、obligations、actual parents、audit instruction 和 repair envelope；不能只验证精简预演请求。

## 现有测试已覆盖什么

以下为代码阅读确认，不是本次重跑结果：

| 文件 / 测试 | 已覆盖的行为 |
| --- | --- |
| `test_residual_review_regressions.py::test_single_and_multiple_successful_windows_have_same_answer_and_sources` | 多窗口正常结束后 unread/failed 清空，结果与单窗口一致。 |
| `...::test_failed_window_without_repair_budget_keeps_later_windows_unread_and_pending` | 已失败窗口与后续 unread 同时保留；无预算时再次调用不生成新请求。 |
| `...::test_checkpoint_preserves_obligation_kind_and_clears_only_completed_windows` | checkpoint 保留 unread 与 failed 的区别；完成剩余窗口仅清 unread，旧失败仍阻止发布。 |
| `test_v4_adaptive_initial_cap_review.py::test_later_capacity_failure_retains_unread_suffix_and_already_accepted_history` | 首窗成功、后窗容量失败时，已接受事实保留，未读后缀继续 pending。 |
| `test_v4_prefix_admission_review.py::test_rebuilt_payload_order_change_rejects_before_generation` | 实际 payload 与容量候选不一致，generation 前拒绝并保留原 unread。 |
| `test_v4_reader_review.py::test_successful_empty_read_cannot_clear_another_querys_evidence_obligation` | 无关查询不能清除 evidence obligation；这是 evidence 义务测试，不能当成 foreign unread 专项测试。 |
| `test_v4_failed_batch_review.py::test_query_rename_or_checkpoint_without_new_original_evidence_cannot_restart_failed_repair` | 改名或恢复不能免费重启失败修复。 |
| `...::test_failed_recovery_cannot_bypass_exhausted_repair_or_normal_llm_budget` | recovery 不能绕过局部/全局 repair 预算和审计预留。 |
| `test_v4_control.py::test_local_projection_cannot_hide_pending_actual_grounding_parent` | 局部结果不能隐藏实际依赖父变量的 pending。 |
| `test_personamem_joint_protocol.py::test_audit_capacity_trial_includes_instruction_before_any_model_request` | audit 指令在容量检查前已进入实际待发送请求。 |

当前测试没有直接证明尚未存在的 mandatory scope 模式能正确处理 same-identity / foreign-identity unread。现有 evidence 或 failed 义务测试不能替代这些新增边界。

## 建议新增的最小回归组

1. 无遗留 marker：父闭包若干原文来自有更多 mapped spans 的 docs；一次 mandatory 请求只包含完整必要闭包，不新增 doc-extra unread，audit 仍须真实执行。
2. 同 identity marker 位于闭包内：仅在完整登记变量已处理后结算；失败转入 failed markers，原文保留。
3. 同 identity marker 位于闭包外：明确并入且计数，或在 generation 前拒绝；绝不能无声删除。包含多个变量且只请求部分时同样检查。
4. 异 identity marker 与本次可见原文重合或不重合：成功 compose/audit 后旧 marker 完全不变；依赖它的 terminal 不能发布。
5. 新模式完整容量失败、模型失败、修复预算耗尽：旧工作/原文/失败类型均保留，不退化为 prefix 截断或 fresh retry。
6. 经过 JSON checkpoint 恢复，模式、工作所有者、变量集合及 failed readiness 不变；改 query/mode 不得到免费修复。
7. 新 counter 撤销父支持，或 handoff 拒绝新 support：保留 counter 与 pending，不能借 closure-mode 结算旁路绕过真实事实更新。
8. 原有正常 document-window 行为不变，邻居及新检索材料继续按原机制处理；无关已证明可短路分支不被新全局阻断。

这组测试验证作用域和状态转移，不需要标签、线上服务或准确率评测。
