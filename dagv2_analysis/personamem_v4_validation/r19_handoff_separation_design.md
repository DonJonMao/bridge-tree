# R19 handoff 分离设计：观察有效性、证据保存与真实下游可执行性

状态：本文主体是基于冻结 R18 源码与已保存轨迹的静态设计，起草时尚未实施；root 随后授权并选定的最小实施范围见第 10 节。设计取证未重新运行模型、分词器、网络、评分或标签读取。R18 的失败结果不回填、不重分类为成功。基线源码为 `800c51763ea3a2bfcad459b4413d41c6432db52e`；具体 case13 数量证据见同目录 `r18_case13_capacity_scope_review.md`。

## 1. 建议选择的通用规则

**真实 `grounded(target) is None`、因另一必要父项尚未绑定而无法执行的未来调用，只产生 advisory，不拒绝已经完整通过本地验证的观察。** 有效事实和反证按原设计 §6.2 整批整合；独立证据可以被保存/绑定，但不因此宣称下游已执行、终端已审计或答案可发布。

保留三个严格边界：

1. 新支持使自身变量产生冲突、需要当前 owner 的 `conflict_recheck`，不是“缺另一个父项”的普通未来调用；继续当前必要复核与容量检查。
2. 真实已接地、范围/阶段/owner 权限允许执行的 compose，以及真正就绪证书的 audit、terminal format，仍必须完整携带实际必要来源，经过现有实际 wire 容量检查。
3. 本地 schema、来源、类型、范围、父版本、counter、whole-value、summary-revision、unresolved/failed recovery 的任何违规，仍按原规则失败和有界修复。advisory 不能冲销这些失败。

这是一项明确的工程策略调整。原 handoff checklist 要求“整合支持前确保下一实际必要调用能容纳”，现代码还在未接地目标上制造当前中间态预测请求并实施否决。原设计并未要求每个尚无法执行的未来调用先适配才保存独立观察。不能把当前实现说成无缘由的拼写错误，也不能借此取消实际调用的容量门槛。

不建议以 `S_new ⊆ H_external` 作为唯一准入豁免：那只是针对当前来源构型的窄例外。该包含关系适合做可证的阻塞归因，不能决定本地事实真假。

## 2. 三种判断分别回答什么

| 判断 | 所回答的问题 | 允许产生的结果 | 不允许替代的判断 |
| --- | --- | --- | --- |
| 观察本地有效性 | 此响应是否对实际展示的原始文本、scope、父版本与契约提供合法观察？ | 支持、counter、partial、unresolved 或 scoped validation failure | 不承诺未来上下文容量；合法 support 也不等于最终答案正确 |
| 证据保存与绑定 | 整批事实/反证完成验证后，哪些 route 可以进入事实状态？哪些真实义务继续保留？ | 原子整合合法 row；保留原始来源、版本、义务和失败记录；允许有效事实与 pending 并存 | 不把未决义务降格为日志；不把未运行的终端标完成 |
| 当前操作可执行性 | 现在是否有真实 query、合法完整来源闭包、适用 owner/阶段以及预算，能够执行此操作？ | 执行、advisory、scope-blocked、capacity-blocked 或 budget-blocked | 不以假想 future overflow 证明独立观察无效 |

现有 `FactState.valid()` 已允许有合法支持的变量与 pending 并存；`candidate()`、真实依赖与发布审计再处理 pending。无需为了 advisory 新建第二个不受版本约束的“有效证据仓库”，也不应把已验证父证据放在永不绑定的临时仓库中，造成父项永远无法就绪的死锁。

“保存”不意味着自动接纳所有模型文字：未通过本地验证的 draft 仍只是失败记录；合法 partial 与 unresolved 也不会变成完整 support。

## 3. `query=None` 与真实操作的判定

`grounded()` 不是 pending 检测器。它可利用一个仍有真实未决义务、但已存在合法值的父项；因此不能简单规定“有 pending 就禁止 compose”。某些已接地的父项复核 compose 可能有权解决该 pending，必须按它的实际 scope 和 owner 权限判断。

建议把未来操作评估分为以下原因码：

| 状态 | 判定 | handoff 动作 |
| --- | --- | --- |
| `future_unbound_parent` | prospective 整批状态下，真实 grounded=None；缺失的是其他必要父项，而非借新冲突使自己变未绑定 | 仅 advisory；不产生该 row 的 citation repair |
| `current_conflict_recheck` | 新 row 使自身 demand 发生冲突，需要当前 owner 复核 | 保留现有严格预检/repair；不能因 query=None 获得豁免 |
| `executable_compose` | query 已接地且真实 mandatory scope、阶段和复核权限可被接纳 | 检查实际完整 wire；超限仍阻塞/有界修复 |
| `scope_blocked` | query 非空，但实际 mandatory scope 需要尚无权接管的另一 query 的 unread/failed 工作 | 返回真实 owner；不是当前 row 的语义错误；不能因为文本可见而越权解决 |
| `ready_audit_or_format` | 真实证书/terminal 依赖就绪，需要实际 audit 或输出格式操作 | 独立严格检查；别处存在 query=None 不得跳过这一分支 |

最小第一版可只改变 `future_unbound_parent` 分支，并保持 query 非空分支的现有严格预检，减少接口变动。若需要完整区分 `scope_blocked`，应从 `_mandatory_scope_payload` 抽出无副作用的 scope-admission 判断；不能为了预测调用它并提前改变 reader 状态，也不能将“count 能放下”误当“该 owner 有权执行”。

未来 advisory 如继续保留当前 provisional payload 的计数，必须标注 `provisional=true`、`executable=false`，不得称为最终闭包下界。最小版也可只记录未绑定原因而不额外计数。当前实际 audit 的既有计数仍正常执行。

## 4. 最小接口及数据流

将 `_handoff_failures(...)` 的一个失败字典概念上拆为：

```text
HandoffAssessment {
  required_failures: {(variable, draft_id): feedback},
  deferred_targets: [FutureHandoffRecord],
  target_blocks: [ActualTargetBlock]
}
```

`required_failures` 保留可执行必要调用/当前 conflict recheck 的严格 gate。`deferred_targets` 不进入局部 `failures`、不触发同 draft JSON repair、不把 fresh support 人为设为 pending。`target_blocks` 记录实际 scope/capacity owner 和操作状态；是否增加恢复队列属于第 7 节的第二阶段，不能只改名称便宣称能恢复。

建议 `FutureHandoffRecord` 至少带有：target demand、未接地原因/缺失父变量、draft support 稳定身份、program/scope/实际 parent versions、相关 owner 及 obligation/failed record 的 ID 与内容 hash；可附带 source-set hash、已有计数和预算。不要使用 alias、日志序号、一次性 request ordinal 作为等价性身份。

评估必须基于同批合法支持、counter、summary revision 后的 prospective 状态。不能先忽略 counter 接纳 support，再声称下游仍由旧父项接地。所有 advisory/target-block 记录在本批最终验证与整合边界提交，不能由失败的 speculative probe 提前修改 durable 状态。

最小版不改变以下流程：

- `valid` row 仍走同一 `FactState.integrate`，由版本、scope 和 counter 规则决定绑定；原文和 route 仍按稳定身份保留。
- `_release_failed_reviews` 仍必须来自实际被 offer 的 failed ID、准确源范围、局部修复验证与现有 recovery 契约。advisory 不是 recovered ID，不给它添加“已解决”资格。
- 未决义务、failed record 和 unread scope 按现有合法复核路径清除；本例两项各带两条描述的 49/75 来源义务继续分别保存。
- 本轮不把既有 R18 failed draft 转为 support，也不修改 R18 计数、状态、失败文件或结果。

## 5. 可证归因：引用缩短究竟能改变什么

对某次已经构造出来的 projected payload，定义：

- `S_new`：某新 row 实际稳定 `source_id` 集合。
- `H_external`：**该 payload 中实际保留**、属于别的 owner 的硬 obligation/failed record 来源并集；排除已合法 recovered 的记录。不能从全局 reader 的所有义务随意 union。
- `P_new`：该 row 的真实 transitive parent 依赖，必须和 source overlap 分开记录。

若 `S_new ⊆ H_external`，则对任意只缩引用的 `S' ⊆ S_new`：

`H_external ∪ S' = H_external`。

这严格证明新 row 的引用缩短不能减小这部分原始来源闭包。它**不证明**缩短 typed value、删除冗余说明或其他合法序列化变化一定无法节省足够 token；source-set 相同也不是完整 wire-token 恒定的数学证明。

case13 保存轨迹支持更具体但有限的事实：call7→8 的引用 13→12，终端闭包均 75，input 仅少 8 token，仍超 1564；8→9 的预检请求 hash 完全相同。所以当时反复反馈“缩本 draft 的引用”缺少有效来源杠杆，不应把它写成已找到可以消除 75 段的修复。

`downstream_blocked_by_existing_obligations` 可以附上这个包含关系、每个来源保留 owner 和记录身份。这是结构性归因；若未额外证明固定部分本身超限，不应写“无论此 row 怎样改总量必超”。

## 6. 三类容量问题必须分开

### A. 新 draft 自己增加必要来源

若 `S_new - H_external` 非空，新的必要来源确实有它自己的贡献。case13 call10 的 26 个引用中 12 个在已有 75 段外，下游为 87；这与 call7/8/9 不同。但贡献存在不等于证明它单独导致所有超额。

- 若对应目标仍真正未接地：按通用规则保存合法证据、记录 advisory；不为假想未来调用立刻否决它。
- 若是当前 conflict recheck、真实已就绪 compose/audit：继续现有充分引用修复。缩短必须由模型重新给出充分原文证明，并保留必要 counter，不能按 token 自动截断。
- 代价必须承认：未接地时保存的超宽 proof，后来真实闭包可能仍放不下。通用分离修复了过早否决，不保证后续都能成功。

### B. 已有固定支持闭包过宽

已有合法支持来源过宽、没有可解除的临时义务时，不得称为某个“未决 owner 清掉即可”的问题。新独立 row 也不应因这个既有结构被认定本地无效。

真实调用仍阻塞；只能通过合法的新完整同值 OR proof、显式 summary revision 或实际证据修正改变闭包，或者保持原证据并如实停机。不能自动缩既有 proof、把 AND 前提变成 OR、只保留表面相同值就抛弃 counter ancestry，也不能保证有可行窄证明。

### C. 终端/audit 自身超限

终端生成的本地协议、真实选择/格式输出、就绪 audit 都不是普通 history evidence 的延后例外。真正必要闭包必须完整且能适配；否则不生成伪证书，不标 audit_complete，不输出成功状态。

同一个 batch 内，一条独立历史支持的未来目标尚未接地，并不豁免同批另一条支持触发的真实 ready audit。评估需要逐目标分类，再合并所有仍适用的严格拒绝。

## 7. controller 如何回到 owner，而不靠日志假装进展

### 第一阶段：最小分离，保留现有调度

advisory 不应成为新的语义 pending。case13 真正未决的 `user_profile` 已自然保留在 `active()`；另一个尚无值的必要父项也仍活跃。保存独立 `past_experiences` support 是实际材料变化，reader 的既有 material signature 会反映它。

但 `user_profile` 的原 query/parent/program identity 已有容量 exhaustion：**仅记录 blocker owner 或多打印一条日志，不能清除 `exhausted`、`read_attempts`、`read_effects`、`compose_exhausted`，不能重置修复额度，也不能用 `forced_demands` 绕过 failed recovery。** 若当前 owner 没有合法新动作，就允许诚实地保持 blocked/最终失败。

因此第一阶段能够避免无效的本地 citation repair，也能继续仍合法的其他父项工作；不能宣称它已经具备“返回任何 solved owner 重做证明”的通用能力。

### 第二阶段：若要支持实际 overflow 后的有界 owner 恢复

现有 controller 不会因为真实 terminal 容量失败，自动重新读取一个已解决且无 pending 的 owner。要补这一能力，需要独立的 `capacity_reviews` 调度记录，而不是伪造 evidence unresolved 或全局重新规划。

建议只由一次**真实已接地的 mandatory 容量失败**创建记录，绑定：target/phase、完整 closure fingerprint、实际 count/预算、所选 route/owner scope/parent versions、可复核源范围。以它请求的材料指纹去重、checkpoint 持久化，并排除在语义 material signature 之外。队列记录/消费自身都不算进展。

一条 owner review 要启动，至少满足：

1. 该 owner 的 selected route 对真实闭包有可追踪贡献；选择 owner 依据实际 route/源归属，不根据最终正确标签。
2. 可以在原始合法 scope 中提供它应见的完整来源、counter 和 revision ancestry；review 请求本身也经过相同 wire 检查。
3. 存在现有预算允许的 scoped review/repair；不会凭一个新 query 名称洗白旧 failed recovery，也不以清空 exhaustion 开始新一轮。
4. 该精确材料状态未尝试过。只有真实相关来源、父版本、selected route、义务或程序状态发生合法变化，才可能形成新的可调度 fingerprint；不能让日志/alias 变化产生重试。

响应路径复用已有证据契约：独立完整同值窄 proof 可作为新的 OR route；改变/整合历史 summary 必须显式 summary_revision，携带所需旧证据与 counter ancestry。旧 route 不被默默改写。新的所选 route 会更新事实版本，依赖它的终端/certificate 必须重新验证。若 owner review 重现同样材料、无法适配或额度用尽，关闭该次恢复，保留实际 blocker，允许停止。

这不是第一阶段改一行 `continue` 能自动获得的能力，应单独界定实现/测试范围。若 root 只做第一阶段，发布说明应明确“实际闭包之后仍可能无法容纳，暂不新增 solved-owner 的容量复核队列”。

## 8. 必须保留的反例与评审矩阵

以下是应补/保留的检查设计；起草本矩阵时尚未执行测试，随后授权的有限验证见第 10 节。

| 场景 | 预期 |
| --- | --- |
| 缺兄弟父项；本地合法 support 的引用全在另一 owner 的 75-source 硬义务内 | 接纳合法整批事实；记录 advisory/准确 owner 归因；不为该引用重复修复；75-source 义务完整保留 |
| 缺兄弟父项；fresh support 另加 12 来源 | 同样先保存合法事实；记录可能宽 proof；后来真实就绪时必须做实际容量检查 |
| 新 row 与同 owner 原有值冲突，导致 grounded=None | 不获得未来未接地豁免；保留当前 conflict recheck、counter 与 whole-value 规则 |
| 一般真实下一 join：宽新 proof 超限，充分窄 proof 可适配 | 保留 `test_actual_handoff_capacity_requires_explicit_sufficient_citation_repair` 的机制；不能取消其修复能力 |
| 他人义务暂时解除，此前保存的 proof 变成真实闭包主要来源 | 实际 gate 仍拒绝超限；第一阶段可停机，第二阶段仅合法 owner review；不把先前 admission 当永久容量证书 |
| 已有 fixed support 本身过宽 | 不自动丢证据；真实调用阻塞，只有合法 proof revision/OR alternative 可能改变它 |
| 合法 counter 与受 capacity 阻塞的支持同批出现 | counter 继续受保护并原子整合；支持的容量结果不能吞 counter |
| source overlap 相同但 parent versions/scope 不同 | 不视为独立等价证据；维持真实依赖和版本失效 |
| 声称 recovered failed ID，但局部失败未真正解决 | 不释放 failed record；advisory 不成为 release 条件 |
| 真实 ready certificate 的 audit 超限，另一 future target 未接地 | audit 仍严格失败，不因另一 advisory 通过 |
| 合法短路证书已排除独立 pending 兄弟 | 继续现有实际 audit 投影，不能把所有全局 pending 原文强灌回已排除依赖 |
| 同 blocker 重复日志或 checkpoint/restore | 不产生材料进展、不增加预算、不重开同状态调用；snapshot 保留身份 |

## 9. 修复范围与不保证的结果

本提议解决的是：把尚不能执行的未来操作容量预测，误当独立观察本地有效性条件；以及将跨 owner 临时硬义务引起的来源闭包，笼统反馈成“当前 draft 缩引用”的修复目标。

它不保证原始证据足够、不保证义务一定能解除、不保证 16K 能容纳实际最终闭包、不保证全部失败消失，也不保证有效作答准确率提高。case13 的 49→75 保守义务增长仍存在，不能借这个修改删除或自动合并两项 obligation。frozen restatement 契约与 planner 字段过细是独立问题。

root 正在另行处理的 schema 镜像边界：`resolved_obligation_ids` 非空必须与空 unresolved 一致；显式提供的 frozen review ID 不应在普通 observations 中重述、但可引用；`resolved_failed_batch_ids` 不能一概要求 unresolved 为空，因为合法有来源的 partial 修复可解决格式失败并保留真实证据问题。本设计不修改 `_schema` 或相邻说明，也不以 schema 小改声称 handoff 或 case13 已解决。

建议先由 root 确定是否采用第一阶段的通用分离，以及是否把第二阶段 owner capacity-review 队列纳入同一补丁。无论哪种范围，都需要新运行验证，不改变冻结 R18 的失败事实。

## 10. root 选定的最小实施范围与有限验证

root 随后授权在 `dagv2-personamem-v4-reconcile` 实施第一阶段，生产修改仅限 `_handoff_failures`；没有修改 RELEASE、residual_control 生产调度或历史测试，没有 commit。root 的 `_schema` 修改与本函数分别保留。

实现保留函数原有失败字典返回值，没有引入第 4 节的结构化返回类型，也没有 capacity-review 队列。check 附加 speculative 标记；真正 grounded=None 且不属于自身 conflict recheck 的目标，继续沿原完整 wire 做预检。若超限，只记 `joint_support_handoff_deferred` 事件，不生成局部 citation failure。真实接地分支、当前 conflict、audit、symbolic format 保留原 strict gate。

事件包含 missing parent demands/variables、实际 parent versions、program identity/revision、实际 source span 数与稳定来源集合 hash、上下文限额，以及 `provisional=true`、`executable=false`、`capacity_fits=false`。它不声称拥有 `_fits` 没有返回的精确 token 数。没有增加 pending、forced demands、exhaustion reset、semantic material signature 项或新的付费恢复路径。

本 agent 新增 `tests/test_v4_handoff_executability.py`，先在未改 handoff 逻辑上观察到 2 failed、2 passed：缺失另一父项时，新 proof 自己带独占来源仍被未来容量否决，且实际读取会额外消费本地 repair。修改后这 4 项通过。随后与既有 `test_v4_joint_reading.py`、`test_v4_audit_dependency_projection.py` 一起定向执行，53 passed；`git diff --check` 通过。均为 scripted/offline 测试，无真实服务调用；没有跑 full suite、R18 重演或评分。contracts agent 的独立测试由 root 另行汇总。

最终选定边界是：后来真实闭包仍可能超限并如实失败；本补丁不新增 solved-owner 的容量恢复或 summary 改写能力。后续验证不能把这项延后判断解释为保证任务成功。
