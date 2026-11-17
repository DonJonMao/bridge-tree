# R17 固定 14 题结构验证汇总

冻结源码：`bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告未读取标签、未导出题目/选项/答案文本、未评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"ok": 14} |
| dagbt_residual_memory_v2 | 14 | {"ok": 6, "unresolved_or_exhausted": 7, "execution_failed": 1} |

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | unresolved_or_exhausted | 18 | 6 | 11 | 0 | 0 | mandatory_downstream_context_capacity |
| 2 | unresolved_or_exhausted | 13 | 5 | 7 | 0 | 0 | obligation_resolution_conditions; mandatory_downstream_context_capacity; InputOverflow |
| 3 | ok | 14 | 3 | 8 | 1 | 1 | 无 |
| 4 | unresolved_or_exhausted | 13 | 6 | 6 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 5 | ok | 13 | 4 | 6 | 1 | 1 | 无 |
| 6 | ok | 14 | 5 | 6 | 1 | 1 | 无 |
| 7 | ok | 11 | 1 | 7 | 1 | 1 | 无 |
| 8 | unresolved_or_exhausted | 19 | 6 | 9 | 2 | 1 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; InputOverflow |
| 9 | ok | 14 | 3 | 8 | 1 | 1 | 无 |
| 10 | unresolved_or_exhausted | 13 | 6 | 6 | 0 | 0 | mandatory_downstream_context_capacity; obligation_resolution_conditions; InputOverflow |
| 11 | ok | 11 | 2 | 6 | 1 | 1 | 无 |
| 12 | unresolved_or_exhausted | 13 | 1 | 10 | 1 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 13 | unresolved_or_exhausted | 12 | 4 | 7 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 14 | execution_failed | 3 | 2 | 0 | 0 | 0 | PersonaMem terminal must compose personal-history evidence into a response selection; Compose requires parents; execution must be retrieval/compose; Personal evidence semantics requires an explicit nonterminal evidence scope; ProtocolError |

类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。

出现容量相关事件的题号：[1, 2, 4, 8, 10, 12, 13]。

真实 mandatory 请求结构计数：{"initial_requests_by_operation": {"semantic_compose": 9, "audit_joint": 7}, "requests_missing_required_sources": 0, "requests_with_extra_visible_sources": 0, "identity_groups_with_multiple_batches": 0, "identity_groups_with_alias_visibility_mismatch": 0, "note": "Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here."}

真实 shared_history_texts 请求结构计数：{"shared_history_request_count": 24, "decode_failures": 0, "missing_decode_instruction": 0, "structure_mismatches": 0, "note": "Actual saved requests containing shared_history_texts, including scoped repairs. Decoding checks preserve original-source spans, nonvalue metadata, scope, and contract; no labels or answer correctness evaluated."}

仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。
