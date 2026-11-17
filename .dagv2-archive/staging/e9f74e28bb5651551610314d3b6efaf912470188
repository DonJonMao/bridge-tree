# 未读候选与证据义务：两页决策稿

最终审议决定（覆盖早期窄试行建议）：适用于全部 ordinary residual document_windows；无新增模型 ACK 字段。RELEASE/R17 保持 bcbd16f；RECONCILE 从 8dac32b 实施，须独立验证和新运行身份。本文为设计说明，不是已验证效果结论。依据原 `docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md`、`r17_unread_sufficiency_contract_review.md`，并与独立反证审查定点互核。

**结论：可以区分。原理论未要求同变量候选池穷尽；但不能把实现改成“任何 support 都清 unread”。** §2.2 将事实 Γ、待读 C、前沿 H 分开；§5.1/5.3 要求读后重求解；§6.2 要求整个实际响应的事实/反证原子处理；§7.3 审计采用的支持和已知相关反证。当前把排队候选一概作为发布阻塞，是额外工程策略。修改它不需要把旧 README 当作用户禁令，但会取消“本次已排队候选全部读完”这项额外覆盖保证，必须如实记录。

## 1. 最小数据结构与不变量

保留三类工作，不能只从 `pending_variables()` 的并集中删一项：

| 类别 | 身份/来源 | 发布语义 |
| --- | --- | --- |
| `discovery_frontier` | ordinary window 候选；source ID/hash、owner query、任务/变量/scope、父/程序版本、顺序/发现路径、从未实际尝试的凭据 | 可暂停，保持 unknown；不宣称读过、无关或已解决 |
| `attempted_work` | 实际请求完整 wire 的 source/slot/scope/version 身份；含 in-flight、协议失败、partial/unresolved、未完成修复 | 已尝试未完成者继续 hard-block；不得回退纯前沿 |
| `required_evidence_work` | 当前证明共同前提、实际父/规则来源、已知反证、带源未决、失败草稿、明确定位线索 | 即使从未发送也不能 optional；沿既有来源/修复/审计规则完成 |

检索命中关系不自动等于必要取证关系。相反，已读记录说“附件 R 决定当前适用规则”，R 虽尚未发给模型，也不是纯 optional 候选。来源在别的 query 中读过，不等于完成本 scope；新 query 也不能洗掉旧 owner 下仍相关的失败或义务。

## 2. promote → settle → yield

**enqueue：** 仅合格 ordinary 候选进入 typed frontier；分类在调度时确定，不能到超限后为获得成功而临时更名。未发送且无已知必要关系才有资格，不是只看 `ever_offered=false`。

**promote：** 冻结并记录实际请求的完整 wire scope，随后将涉及工作置为 attempted/in-flight。范围包括邻接原文、旧父、修复和 failed-review 所携带的来源；不能只看选窗 alias 前缀、citation 或 `read_states`。请求是否实际发生不明、崩溃或输出截断，均保守保留阻塞。

**settle：** 校验整个响应所有必需 slots、出现过的草稿、同批 counter、重复 ID、来源/scope 与全部有界修复，再原子整合有效事实及反证。只关闭本 scope 已合法完成的处理；partial、unknown、unresolved、失败草稿、必要后续定位关系按原机制保留。不能第一条 support 后返回，也不能仅凭一个成功 sibling 解除失败输出。

**yield：** 一个实际发送 batch 完整处理后，ordinary reader 交还 controller，保留未发送队列。控制器免费重求解：仍无充分输出则恢复原队列/必要取证；具备当前充分支持则进入真正终端与审计。此处改变控制权边界，不增加独立模型调用、摘要器、匹配器或预算。batch 已正确处理但含未解事实，也可返回控制器；这些 hard blockers 仍阻止使用相应依赖发布。

**pause/resume：** 对纯前沿记录 `paused_for_current_output`，保留 source、owner、范围、版本、顺序及发现身份。不能写 resolved/irrelevant/all_sources_reviewed。恢复不重跑已完成 dense，不重置 LLM/JSON repair 额度；旧 failed review 仍需真实新原文或实际父变化与原付费资格。入队/出队、换 identity 或写暂停状态不算新语义进展，不能制造重试循环。新来源/反证/父版本改变后按原规则使旧证明和依赖终端失效。

## 3. 可见但没有 observation，不等于未读或无关

实际 wire 包含 s1、s2，而响应仅引用 s1：**s2 永远不能被倒退分类为 never-offered frontier**。若必需槽位遗漏、协议未完成、存在 partial/unresolved 或相应失败/证据义务，继续保留 attempted/observed 阻塞。

如果完整必需槽位通过现有联合阅读协议、明确没有 unresolved，并且全部草稿/反证和修复校验完成，未引用 s2 可记为“本次批次语义评估已接受、无新增 observation”。不能只依据“没有 citation”作此判定，也不能将它记为 irrelevant。空 observations 不创造支持；没有有效绑定的任务仍未解。旧 sourced obligations 不因空槽位而消失，仍需明确 offered ID 和完整 sourced review。

这是一项**有条件的整批语义判断**，不证明模型实际利用了每一段或绝未漏 counter。它与原模型解释的可靠性边界一致；不要求额外做每个 source × 每个节点的全量 mapping。采用现有必需槽位协议判断本批评估完成；不增加模型范围 ACK 字段，不把任何 echo 当作语义正确证明。实际 wire 范围和状态由程序记录。

## 4. 发布边界：证书与开放语义分别处理

**symbolic certificate：** 对固定 K、当前合法 Γ 与非空 Ω，仍由原认证器证明所有允许完成满足契约；实际依赖闭包中所有 attempted/required hard blockers 必须解除。允许保留纯候选前沿不等于证明未来材料不会修改 Γ。原 §3.5 本来就不证明没有未发现反证；不能把条件性证书夸大为全语料无反证证书。

**semantic_assessment：** 历史 support 只提供可供下游使用的绑定，不直接完成建议。必须有真正终端生成、采用支持及已知相关反证的审计，并解除全部实际依赖/终端已观察未决和失败。完成级别仍是 semantic_assessment，不伪造有限域证书，不改变实质输出契约 K，不声称是全记忆下最优回答。

共同反例：已有适用规则与确切违例见证，可以在当前条件下否定；只有“异常待查 DEL-08”线索则不能。已知更正、对象/时间冲突仍需处理。完整规则、全部失败项、全集集合、事件不存在、精确最新/最大记录等任务，不能用找到一个 support 替代其完整性或范围要求。mandatory compose/audit 本身超限也不能把共同前提降级为探索前沿。

## 5. 最终适用范围与旧快照

统一适用于全部 ordinary residual `document_windows`，不按 PersonaMem、summary、数值、布尔等类型分组豁免。区分依据是实际工作身份：有明确发现来源、在当前范围从未发送、且无已知必要证据关系的候选，方可进入纯探索前沿。类型和输出语义原本的完整规则、全集、全称、缺失或极值要求继续生效；仅找到一个 support 不会代替合法 Γ 或原认证器。mandatory compose/audit、共同前提及已知 hard blockers 均保持约束。

旧泛化 unread checkpoint 缺少 never-offered/必要性分类凭据时，一律保留旧 hard-block 含义；不得批量迁移。新快照保存前沿、实际请求范围、attempted 和真实义务；恢复不改变 owner/版本、失败恢复资格和预算。新停止策略须有新的运行/方法身份，不能静默施加于 R17 或已冻结结果。

**最终决定：** 实施 general ordinary residual 的明确状态分离和每批返回控制器；不用新增模型 ACK。原理论足以支持这个明确分类设计，不支持“任何 support 自动跳过同变量其他材料”。该设计仍需边界测试和独立全量验证，不保证准确率提升、不会遗漏潜在反证或立即解决现有真实失败。
