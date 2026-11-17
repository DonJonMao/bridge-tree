# R18 固定 14 题结构验证汇总

冻结源码：`800c51763ea3a2bfcad459b4413d41c6432db52e`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告分析未读取标签或评分文件、未导出题目/选项/答案文本、未评分；runner 自身在全部任务终态后可能自动评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"ok": 14} |
| dagbt_residual_memory_v2 | 14 | {"ok": 12, "unresolved_or_exhausted": 1, "execution_failed": 1} |

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ok | 7 | 1 | 3 | 1 | 1 | 无 |
| 2 | ok | 7 | 0 | 4 | 1 | 1 | 无 |
| 3 | ok | 7 | 1 | 3 | 1 | 1 | 无 |
| 4 | ok | 7 | 0 | 4 | 1 | 1 | 无 |
| 5 | ok | 8 | 0 | 5 | 1 | 1 | 无 |
| 6 | ok | 6 | 0 | 3 | 1 | 1 | 无 |
| 7 | ok | 7 | 1 | 3 | 1 | 1 | 无 |
| 8 | ok | 6 | 0 | 3 | 1 | 1 | 无 |
| 9 | ok | 7 | 1 | 3 | 1 | 1 | 无 |
| 10 | ok | 7 | 1 | 3 | 1 | 1 | 无 |
| 11 | ok | 8 | 2 | 3 | 1 | 1 | 无 |
| 12 | ok | 8 | 0 | 5 | 1 | 1 | 无 |
| 13 | unresolved_or_exhausted | 11 | 6 | 4 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; mandatory_downstream_context_capacity; InputOverflow |
| 14 | execution_failed | 3 | 2 | 0 | 0 | 0 | Compose requires parents; execution must be retrieval/compose; PersonaMem requires semantic/text response selection, not symbolic fact certification; ProtocolError |

类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。

出现容量相关事件的题号：[13]。

真实 mandatory 请求结构计数：{"initial_requests_by_operation": {"semantic_compose": 12, "audit_joint": 12}, "requests_missing_required_sources": 0, "requests_with_extra_visible_sources": 0, "identity_groups_with_multiple_batches": 0, "identity_groups_with_alias_visibility_mismatch": 0, "note": "Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here."}

真实 shared_history_texts 请求结构计数：{"shared_history_request_count": 27, "decode_failures": 0, "missing_decode_instruction": 0, "structure_mismatches": 0, "note": "Actual saved requests containing shared_history_texts, including scoped repairs. Decoding checks preserve original-source spans, nonvalue metadata, scope, and contract; no labels or answer correctness evaluated."}

探索前沿、原文身份与实际曝光检查：{"canonical_rows_reviewed": 14, "reader_reached_cases": 13, "source_identities_rebuilt": 2145, "frontier_entries": 2942, "exposures_traced_to_wire": 78, "confirmed_failures": 0, "requires_review": 0, "successful_terminal_dependencies_checked": 12, "note": "Canonical source identity, actual request exposure, per-query frontier/read/hard-work disjointness, current terminal bindings and supported audit reviewed. Stored history does not prove every unrecorded historical transition or semantic completeness."}

独立闭合回执 smoke gate：{"executed_by_reader": false, "passed": null, "state": "pending_root_execution", "reason": "Root explicitly retains the production smoke gate; this receipt is structural verification only."}

仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。
