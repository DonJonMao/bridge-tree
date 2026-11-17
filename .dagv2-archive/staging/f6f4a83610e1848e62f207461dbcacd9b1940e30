# PersonaMem v4 当前候选需求审查

已验证基线为 `800c51763ea3a2bfcad459b4413d41c6432db52e`；RELEASE 保留该冻结提交，RECONCILE 的后续修订已授权且尚未验证。
该基线全套离线通过；R18 已自然结束，original 14 ok、新方法 12 ok/2 failed，实际严格 gate 退出 1，`release_ready=false`。
旧状态逐字节保存在 `requirement_audit_pre_800c517.md`；历史运行不能替代当前源码验证。

## 已完成的验证

实际完整命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`：1938 passed、69 warnings、111.93 秒，退出码 0。
日志 `full_tests_22_discovery_restore.txt` SHA256：`47852ce77cc6412a55319635d2822f16aeca2d18a1b4afbe88dd3703c67faba0`。
回执 `full_tests_22_discovery_restore_receipt.json` 记录测试前后 306 文件不变；`frontier_final_tested_commit.json` 与 `r18_prelaunch_800c517.json` 绑定测试字节、Git blobs、两工作区及 104 个运行源码哈希。
独立 frontier 35 例包含在 1938 总数中，不能重复相加。Full21 的 5 个失败及其初始证据完整保留；修正后的 Full22 才是当前通过记录。

## 32 项需求及证据索引

每项状态为“800c517 基线离线回归通过，R18 真实模型全轮验收失败，后续修订尚未验证”。测试通过不等于形式证明或模型质量保证。

| 要求 | 回归文件 |
| --- | --- |
| 1. `task_objective` | `tests/test_v4_personal_task.py` |
| 2. `two_graphs` | `tests/test_v4_control.py` |
| 3. `reachable_contract` | `tests/test_v4_contracts.py` |
| 4. `typed_publication` | `tests/test_v4_control.py` |
| 5. `material_progress` | `tests/test_v4_joint_reading.py`、`tests/test_v4_control.py` |
| 6. `audit_correction` | `tests/test_v4_control.py` |
| 7. `capacity_handoff` | `tests/test_v4_joint_reading.py` |
| 8. `unresolved_evidence` | `tests/test_v4_reader_review.py` |
| 9. `residual_short_circuit` | `tests/test_v4_reader_review.py`、`tests/test_v4_control.py` |
| 10. `paired_evaluation` | `tests/test_v4_release_gate.py` |
| 11. `phase_isolation` | `tests/test_v4_phase_review.py` |
| 12. `whole_value_reconciliation` | `tests/test_v4_reconcile_review.py` |
| 13. `durable_failed_batch` | `tests/test_v4_failed_batch_review.py` |
| 14. `repair_capacity_admission` | `tests/test_v4_headroom_review.py`、`tests/test_v4_adaptive_initial_cap_review.py`、`tests/test_v4_prefix_admission_review.py` |
| 15. `history_summary_revision` | `tests/test_v4_summary_declarations.py`、`tests/test_v4_summary_revision_state.py`、`tests/test_v4_summary_revision_review.py` |
| 16. `idempotent_summary_review` | `tests/test_v4_summary_noop_review.py` |
| 17. `explicit_scope_role_separation` | `tests/test_v4_personal_task.py` |
| 18. `explicit_personal_text_representation` | `tests/test_v4_personal_semantics_review.py`、`tests/test_v4_summary_declarations.py` |
| 19. `actionable_revision_source_feedback` | `tests/test_v4_summary_source_feedback_review.py`、`tests/test_v4_summary_source_feedback_boundaries.py`、`tests/test_v4_summary_source_feedback_trust_review.py` |
| 20. `lossless_whole_review_wire` | `tests/test_v4_whole_review_wire_review.py`、`tests/test_v4_whole_value_repair.py` |
| 21. `adaptive_fresh_history_output_cap` | `tests/test_reasoning_output_cap_review.py`、`tests/test_v4_adaptive_initial_cap.py`、`tests/test_v4_adaptive_initial_cap_review.py`、`tests/test_v4_prefix_admission_review.py` |
| 22. `nonempty_state_preserving_response_floor` | `tests/test_v4_state_preserving_floor_review.py`、`tests/test_v4_adaptive_initial_cap_review.py`、`tests/test_v4_adaptive_initial_cap.py` |
| 23. `explicit_scoped_obligation_coverage_review` | `tests/test_v4_obligation_feedback.py`、`tests/test_v4_obligation_review_feedback_review.py`、`tests/test_v4_whole_review_wire_review.py` |
| 24. `mandatory_source_scope` | `tests/test_v4_mandatory_contract_review.py`、`tests/test_v4_controller_source_scope.py`、`tests/test_v4_partial_failure_scope_review.py` |
| 25. `phase_repair_authority` | `tests/test_v4_mandatory_contract_review.py`、`tests/test_v4_history_wire_integration.py` |
| 26. `lossless_shared_history_input` | `tests/test_v4_history_wire_integration.py`、`tests/test_v4_history_wire_review.py` |
| 27. `actual_proof_input_frontier` | `tests/test_v4_audit_dependency_projection.py`、`tests/test_v4_proof_projection_review.py`、`tests/test_v4_control.py` |
| 28. `request_local_retraction_authority` | `tests/test_v4_proof_projection_review.py` |
| 29. `discovery_frontier_is_not_evidence_obligation` | `tests/test_v4_discovery_frontier.py`、`tests/test_v4_discovery_frontier_review.py` |
| 30. `atomic_batch_then_residual_reevaluation` | `tests/test_v4_discovery_frontier.py`、`tests/test_v4_discovery_frontier_review.py`、`tests/test_v4_reader_review.py` |
| 31. `whole_wire_exposure_and_truthful_paused_state` | `tests/test_v4_discovery_frontier.py`、`tests/test_v4_discovery_frontier_review.py`、`tests/test_v4_reader_scope_implementation.py` |
| 32. `stable_restore_without_free_retries` | `tests/test_v4_discovery_frontier.py`、`tests/test_v4_discovery_frontier_review.py`、`tests/test_v4_summary_source_feedback_review.py` |

## 最新修复与理论边界

原实现把普通发现队列全部当成发布前必须处理的证据义务，阻碍每批新证据后的剩余求解。
现在显式区分纯候选、已尝试未完成工作和必要证据；只有可核对来源的普通未发送候选能暂停。
整个真实批次的槽位、观察、反证与有界修复全部处理后交还控制器，仍有需求时先恢复本地前沿。
已知必要原文、未决/部分证据、失败草稿、反证和完整性契约继续阻塞，不能因换查询身份或容量失败变为可忽略候选。

mandatory 合成/审计继续一次提供当前完整必要来源闭包。实际证明依赖投影仅排除可安全独立的普通等值正向 OR 备选；保留摘要祖先、累计原文、反证和当前复核关系。
输入曝光覆盖整个实际 wire，包括邻接、父来源、未引用原文、恢复与 terminal-only 修复；日志区分 returned、failed 与 not_sent，不等同于 HTTP 成功或逐原文语义分类。

恢复以稳定原文 ID 和完整 span 身份重绑定可执行索引；历史请求 alias/identity 不改写，另存当前 alias。
改名、排队、暂停和曝光日志本身不产生语义进展、不重置重试权限；旧无分类依据的 snapshot 保守保留硬义务。
具体契约见源码 `docs/RESIDUAL_FRONTIER_POLICY_V2.md`、独立 `discovery_frontier_full21_followup_review.md` 和 `frontier_full21_incremental_static_review.md`。

## 真实运行与剩余交付

R17 在旧 bcbd16f 自然结束：original 14 ok；residual 6 ok、7 unresolved_or_exhausted、1 execution_failed，严格 gate 失败。
R18 用 800c517、固定 14 题、原配置及独立新输出目录运行，实际启动 PID 10667。
最新进度以 runner 与 `r18_structural_monitor.json` 为准；首题通过只证明该题执行及审计结构，不能代表全部 14 题或答案正确。

PersonaMem-v1 使用 32K 历史；16384 为继承的完整请求容量。LLM24、ANN36、JSON repair6、完整修复/终端输出4096等原预算未扩大。
必要闭包仍可能超容量，模型仍可能产生不合法或不足的证据；当前修复不保证所有任务成功或准确率提高。
代理不读取 gold/评分作选题、调参或结构验收；runner 在全部题目/方法生成终止后会自动加载标签评分，两者不能混淆。

待 R18 全部自然结束，核对无活跃writer、state=complete、28条成功合法记录、14条真实终端回应和新鲜完整审计、源码/配置/数据/题组身份。
通过后才能源码审批、正式打包、同一 tar 的隔离安装验收及已审定清理。正式包、安装回执和删除操作目前均未执行。

## R18 闭合与当前修订

实际 root gate 回执：`r18_root_closed_gate_receipt.json`。第13题的独立容量/冻结重述/未决范围报告与第14题 planner 报告已保留。第14题 schema 对齐和局部修复反馈在隔离工作区实施；第13题跨 owner 容量阻塞的机制修正尚在设计审查。1938 项测试不能作为新修订通过证据。
