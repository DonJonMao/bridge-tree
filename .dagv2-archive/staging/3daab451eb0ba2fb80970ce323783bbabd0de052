# R16 固定 14 题结构验证汇总

冻结源码：`b9e28a7faa8d419f9f1283574fa095399919c243`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告未读取标签、未导出题目/选项/答案文本、未评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"ok": 14} |
| dagbt_residual_memory_v2 | 14 | {"ok": 6, "unresolved_or_exhausted": 7, "execution_failed": 1} |

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ok | 19 | 4 | 10 | 2 | 2 | 无 |
| 2 | unresolved_or_exhausted | 12 | 4 | 7 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow; ProtocolError |
| 3 | ok | 14 | 3 | 8 | 1 | 1 | 无 |
| 4 | unresolved_or_exhausted | 14 | 6 | 7 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 5 | unresolved_or_exhausted | 13 | 6 | 6 | 0 | 0 | Summary revision must retain every original premise and relevant counter source; mandatory_downstream_context_capacity; InputOverflow |
| 6 | ok | 15 | 3 | 9 | 1 | 1 | 无 |
| 7 | unresolved_or_exhausted | 17 | 5 | 9 | 1 | 1 | mandatory_downstream_context_capacity |
| 8 | ok | 10 | 2 | 5 | 1 | 1 | 无 |
| 9 | ok | 12 | 2 | 7 | 1 | 1 | 无 |
| 10 | unresolved_or_exhausted | 13 | 6 | 6 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 11 | unresolved_or_exhausted | 11 | 5 | 5 | 0 | 0 | obligation_resolution_conditions; mandatory_downstream_context_capacity; InputOverflow |
| 12 | ok | 14 | 3 | 8 | 1 | 1 | 无 |
| 13 | unresolved_or_exhausted | 12 | 6 | 5 | 0 | 0 | obligation_resolution_conditions; mandatory_downstream_context_capacity; InputOverflow |
| 14 | execution_failed | 3 | 2 | 0 | 0 | 0 | Personal evidence semantics requires an explicit nonterminal evidence scope; PersonaMem terminal must compose personal-history evidence into a response selection; Compose requires parents; execution must be retrieval/compose; ProtocolError |

类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。

出现容量相关事件的题号：[2, 4, 5, 7, 10, 11, 13]。

真实 mandatory 请求结构计数：{"initial_requests_by_operation": {"semantic_compose": 8, "audit_joint": 8, "joint_read": 1}, "requests_missing_required_sources": 0, "requests_with_extra_visible_sources": 0, "identity_groups_with_multiple_batches": 0, "identity_groups_with_alias_visibility_mismatch": 0, "note": "Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here."}

仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。
