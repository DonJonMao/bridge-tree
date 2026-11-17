# PersonaMem v4 当前候选需求审查

RELEASE 当前冻结源码 `0cc2cc78498bcd215252fb8e82d2168868a71b3f` 与已测试提交一致；RECONCILE 已开始隔离的无损观察字段共享修订，尚未经完整测试或真实模型验证。
Full23 全套通过；R19 已实际启动，PID 21059，启动核对时 writer=true。真实模型全轮验收仍待完成，release_ready=false。
本文件之前的版本已逐字节存为 `r19_before_running_requirement_audit_candidate.md`。

## 已完成验证

实际命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`：2020 passed、69 warnings、109.93 秒、退出码 0。
日志 `full_tests_23_planner_handoff.txt` SHA256：`41179fccef061102574cbc1ec6b3b4ea1260121e9488e55646de365633f19cae`。
回执 `full_tests_23_planner_handoff_receipt.json` 记录前后 312 文件字节不变；`r19_tested_commit.json` 和 `r19_prelaunch_0cc2cc7.json` 将测试字节绑定到 Git blobs 与两工作区。
实际启动回执 `r19_root_launch_receipt.json` 核对 104 运行源码哈希、配置、固定题组、公开题目摘要、数据清单和真实 writer。
独立新增测试已包含在 2020 总数中，不重复相加。离线回归通过不等于形式证明、真实模型全部成功或答案准确率提高。

## 35 项需求及回归索引

状态均为当前冻结源码离线回归通过、真实模型全轮验收待完成；具体 invariant 与实现位置见 `modeling_checklist.json`。

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
| 33. `personal_planner_schema_and_scoped_repair_alignment` | `tests/test_v4_planner_contract_alignment.py`、`tests/test_v4_planner_contract_alignment_review.py` |
| 34. `reader_obligation_and_frozen_reference_schema_alignment` | `tests/test_v4_reader_schema_alignment.py`、`tests/test_v4_obligation_review_feedback_review.py` |
| 35. `ungrounded_future_capacity_is_not_local_fact_invalidity` | `tests/test_v4_handoff_executability.py`、`tests/test_v4_handoff_executability_review.py`、`tests/test_v4_joint_reading.py`、`tests/test_v4_audit_dependency_projection.py` |

## 本轮修正与边界

1. Planner 的输出 schema 对齐既有 PersonaMem 实际约束；personal-only 修复提供真实前稿及有界累计错误，保留完整原输入，不增加重试预算。三个实际 R18 非法计划均被新 schema 拒绝，尚不代表模型必然生成合法计划。
2. Reader schema 对齐既有 guard：完成义务不能同时保留 unresolved；明确冻结观察仅可按授权引用。合法的部分失败批次修复及 whole-value 解冻仍保留，运行验收规则不放宽。
3. 未具备实际输入的未来下游，其假设容量预测不再否决当前合法证据；自身冲突复核、已具备输入的下游及真实终端/审计仍严格核对完整请求。保留反证原子性，不删除未决义务、不添加自动容量恢复队列。真实必要来源闭包之后仍可能超限。

既有修正保留：任务 DAG 与记忆导航图语义分离；普通发现候选不等于必须清除的证据义务；每个真实批次完整整合后再剩余求解；终端输入按实际证明依赖投影但不删除摘要祖先/反证/必要来源；输入共享编码无损保留原文；恢复身份及请求曝光可追溯。

PersonaMem-v1 32K 历史，完整请求 16384；LLM24、ANN36、JSON repair6、完整修复/终端输出4096，均未扩大。未删换固定题目。代理不读取标签/分数作选题、调参或结构验收；runner 在全部生成终止后自动评分。

## 真实运行与交付

上一轮 R18 在 800c517 自然结束：original 14 ok；residual 12 ok、1 unresolved_or_exhausted、1 execution_failed。实际严格 gate 退出1，旧证据不能替代新源码验收。
R19 用新目录 `outputs/v4_validation_r19` 跑相同固定14题与两个方法，完整自然运行。实时状态以 runner 为准。
只有 writer=false、state=complete、28条成功合法 canonical rows、14条真实终端与新鲜完整审计、源码/配置/数据/题组完全一致，才通过严格验收。
之后仍须源码审批、正式 tar 构建、同一 tar 隔离安装验证和已审定旧包清理。上述交付步骤目前均未执行，没有全量准确率改善结论。

## 后续表示修订（尚未验证）

R19 前两题已出现自然 unresolved，后续两臂又出现计数服务连接/超时，不能验收为通过。root 已读取第一题的独立 Reader 与容量报告；未发现该例 source/owner/frozen 守卫矛盾，但失败复核存在完全相同的长 value/reason 重复序列化。
RECONCILE 仅授权显式观察字段的无损共享；完整原文、原始失败响应、角色、来源、权限、状态及预算不变。实现与独立新测试进行中，2020项旧通过记录不覆盖该修订。源码确认和服务恢复后须做新身份验证，不复用R19失败记录。
