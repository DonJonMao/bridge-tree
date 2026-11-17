# R19 固定 14 题结构验证汇总

冻结源码：`0cc2cc78498bcd215252fb8e82d2168868a71b3f`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告未读取标签或评分文件、未评分；报告不包含题目/选项/答案文本。runner 自身在全部任务终态后可能自动评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"execution_failed": 13, "ok": 1} |
| dagbt_residual_memory_v2 | 14 | {"execution_failed": 12, "unresolved_or_exhausted": 2} |

按已保存失败证据分类：original 第 2–14 题只记录到计数服务连接/超时失败；residual 第 1 题为非服务的协议/容量/owner 阻塞，第 2 题混合协议/容量与计数连接失败，第 3–14 题只记录到计数服务连接/超时失败。合计 25 个仅服务失败、1 个混合、1 个仅非服务失败；这是记录分类，不证明外部服务正常时这些题必然成功。

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | unresolved_or_exhausted | 8 | 2 | 5 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; InputOverflow; ProtocolError |
| 2 | unresolved_or_exhausted | 7 | 3 | 3 | 0 | 0 | Already validated observations remain frozen: omit ordinary restatements; use only explicitly offered reviewed_observation_ids when a further review needs them; InputOverflow; TokenizationError |
| 3 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 4 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 5 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 6 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 7 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 8 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 9 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 10 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 11 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 12 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 13 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |
| 14 | execution_failed | None | 0 | 0 | 0 | 0 | TokenizationError |

本轮没有实际 compose/audit 请求；相关零异常计数来自空集合，不能据此宣称终端或审计验证通过。

类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。

出现容量相关事件的题号：[1, 2]。

真实 mandatory 请求结构计数：{"initial_requests_by_operation": {}, "requests_missing_required_sources": 0, "requests_with_extra_visible_sources": 0, "identity_groups_with_multiple_batches": 0, "identity_groups_with_alias_visibility_mismatch": 0, "note": "Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here."}

两臂独立 tokenization 故障汇总：{"original": {"published_rows": 14, "status_counts": {"execution_failed": 13, "ok": 1}, "failed_tokenization_requests": 13, "error_category_counts": {"connection_or_timeout": 13}, "failed_request_http_attempts": 39, "failed_request_http_retries": 26, "failed_request_elapsed_seconds": 595.0336007089354, "attempt_duration_seconds": 585.1161602510838}, "dagbt_residual_memory_v2": {"published_rows": 14, "status_counts": {"execution_failed": 12, "unresolved_or_exhausted": 2}, "failed_tokenization_requests": 13, "error_category_counts": {"connection_or_timeout": 13}, "failed_request_http_attempts": 39, "failed_request_http_retries": 26, "failed_request_elapsed_seconds": 595.2629393751267, "attempt_duration_seconds": 585.3258375820005}}

Tokenization connection_or_timeout 是外部连接/等待失败，与真实 InputOverflow 及模型协议错误分别统计；保存请求已经执行既有有界同请求重试。没有停止、重启或放宽服务及预算。含这类失败的本轮不能据此证明算法质量下降或修改有效。

费用字段只汇总已记录的账本；缺少字段不等于零成本，失败 tokenizer 请求耗时另列。

真实 shared_history_texts 请求结构计数：{"shared_history_request_count": 0, "decode_failures": 0, "missing_decode_instruction": 0, "structure_mismatches": 0, "note": "Actual saved requests containing shared_history_texts, including scoped repairs. Decoding checks preserve original-source spans, nonvalue metadata, scope, and contract; no labels or answer correctness evaluated."}

探索前沿、原文身份与实际曝光检查：{"canonical_rows_reviewed": 14, "reader_reached_cases": 2, "source_identities_rebuilt": 374, "frontier_entries": 496, "exposures_traced_to_wire": 12, "confirmed_failures": 0, "requires_review": 0, "successful_terminal_dependencies_checked": 0, "note": "Canonical source identity, actual request exposure, per-query frontier/read/hard-work disjointness, current terminal bindings and supported audit reviewed. Stored history does not prove every unrecorded historical transition or semantic completeness."}

独立闭合回执 smoke gate：{"executed_by_reader": false, "passed": null, "state": "pending_root_execution", "reason": "Root explicitly retains the production smoke gate; this receipt is structural verification only."}

仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。
