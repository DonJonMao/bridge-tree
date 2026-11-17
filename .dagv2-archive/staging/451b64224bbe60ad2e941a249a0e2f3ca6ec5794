# R20 固定 14 题结构验证汇总

冻结源码：`6c046374008ce2e45f817d6bc9876b3ab927ab18`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告未读取标签或评分文件、未评分；报告不包含题目/选项/答案文本。runner 自身在全部任务终态后可能自动评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"ok": 14} |
| dagbt_residual_memory_v2 | 14 | {"ok": 9, "unresolved_or_exhausted": 5} |

按已保存 tokenizer 与非 tokenizer 失败证据分类（题号从 1 开始；类别是观测证据，不是反事实归因）：{"original": {"tokenization_failure_evidence_only": [], "non_tokenization_failure_evidence_only": [], "mixed_tokenization_and_other_failure_evidence": [], "other_unclassified_failed_cases": []}, "dagbt_residual_memory_v2": {"tokenization_failure_evidence_only": [], "non_tokenization_failure_evidence_only": [1, 2, 4, 10, 11], "mixed_tokenization_and_other_failure_evidence": [], "other_unclassified_failed_cases": []}}

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | unresolved_or_exhausted | 11 | 6 | 4 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; obligation_resolution_conditions; mandatory_downstream_context_capacity; InputOverflow |
| 2 | unresolved_or_exhausted | 10 | 5 | 4 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; mandatory_downstream_context_capacity; InputOverflow |
| 3 | ok | 8 | 2 | 3 | 1 | 1 | 无 |
| 4 | unresolved_or_exhausted | 11 | 4 | 4 | 2 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them |
| 5 | ok | 8 | 1 | 4 | 1 | 1 | 无 |
| 6 | ok | 12 | 3 | 5 | 1 | 1 | 无 |
| 7 | ok | 6 | 0 | 3 | 1 | 1 | 无 |
| 8 | ok | 6 | 0 | 3 | 1 | 1 | 无 |
| 9 | ok | 6 | 0 | 3 | 1 | 1 | 无 |
| 10 | unresolved_or_exhausted | 10 | 5 | 4 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; mandatory_downstream_context_capacity; InputOverflow |
| 11 | unresolved_or_exhausted | 9 | 4 | 4 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; mandatory_downstream_context_capacity; InputOverflow |
| 12 | ok | 8 | 1 | 4 | 1 | 1 | 无 |
| 13 | ok | 7 | 0 | 4 | 1 | 1 | 无 |
| 14 | ok | 5 | 1 | 1 | 1 | 1 | 无 |

实际终端与审计请求按保存材料检查；计数不替代语义正确性。

类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。

出现容量相关事件的题号：[1, 2, 10, 11]。

真实 mandatory 请求结构计数：{"initial_requests_by_operation": {"semantic_compose": 11, "audit_joint": 9, "joint_read": 2}, "requests_missing_required_sources": 0, "requests_with_extra_visible_sources": 0, "identity_groups_with_multiple_batches": 1, "identity_groups_with_alias_visibility_mismatch": 0, "note": "Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here."}

两臂独立 tokenization 故障汇总：{"original": {"published_rows": 14, "status_counts": {"ok": 14}, "failed_tokenization_requests": 0, "error_category_counts": {}, "failed_request_http_attempts": 0, "failed_request_http_retries": 0, "failed_request_elapsed_seconds": 0, "attempt_duration_seconds": 0}, "dagbt_residual_memory_v2": {"published_rows": 14, "status_counts": {"ok": 9, "unresolved_or_exhausted": 5}, "failed_tokenization_requests": 0, "error_category_counts": {}, "failed_request_http_attempts": 0, "failed_request_http_retries": 0, "failed_request_elapsed_seconds": 0, "attempt_duration_seconds": 0}}

Tokenization connection_or_timeout 是外部连接/等待失败，与真实 InputOverflow 及模型协议错误分别统计；保存请求已经执行既有有界同请求重试。没有停止、重启或放宽服务及预算。含这类失败的本轮不能据此证明算法质量下降或修改有效。

费用字段只汇总已记录的账本；缺少字段不等于零成本，失败 tokenizer 请求耗时另列。

真实 shared_history_texts 请求结构计数：{"shared_history_request_count": 25, "decode_failures": 0, "missing_decode_instruction": 0, "structure_mismatches": 0, "note": "Actual saved requests containing shared_history_texts, including scoped repairs. Decoding checks preserve original-source spans, nonvalue metadata, scope, and contract; no labels or answer correctness evaluated."}

真实 shared_review_texts 请求结构计数：{"review_wire_request_count": 4, "decode_failures": 0, "missing_decode_instruction": 0, "structure_mismatches": 0, "note": "Actual saved shared_review_texts requests only. Exact decoding/repacking does not prove model comprehension or equivalence to an unavailable pre-encoding runtime object. Zero requests is no online validation."}

探索前沿、原文身份与实际曝光检查：{"canonical_rows_reviewed": 14, "reader_reached_cases": 14, "source_identities_rebuilt": 2265, "frontier_entries": 2695, "exposures_traced_to_wire": 95, "confirmed_failures": 0, "requires_review": 0, "successful_terminal_dependencies_checked": 9, "note": "Canonical source identity, actual request exposure, per-query frontier/read/hard-work disjointness, current terminal bindings and supported audit reviewed. Stored history does not prove every unrecorded historical transition or semantic completeness."}

独立闭合回执 smoke gate：{"executed_by_reader": false, "passed": null, "state": "pending_root_execution", "reason": "Root explicitly retains the production smoke gate; this receipt is structural verification only."}

仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。
