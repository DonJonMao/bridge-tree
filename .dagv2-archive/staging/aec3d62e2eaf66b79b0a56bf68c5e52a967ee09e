> 独立修订进行中：RELEASE保持6c04637/R20冻结；RECONCILE正在实现review候选的实际token非增选择。现有2194全套证据只适用于6c04637，不代表新修订已验收。

# PersonaMem v4 当前候选需求审查

候选 `6c046374008ce2e45f817d6bc9876b3ab927ab18` 已提交且两个工作区均干净一致；RELEASE 已在旧 R19 自然结束后 fast-forward，并核对全部315测试文件与105运行源码。R20真实模型验证已启动，PID26942，release_ready=false。

## 离线证据

完整命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`：2194 passed、69 warnings、111.64秒、退出0。Full24测试前后315文件不变，root核对315文件与提交blob一致。日志SHA256 `bd57e2bdef78c6a41d601d8db8863334a7ab1c068d3068f0887e50df1ce385f5`；回执 `full_tests_24_review_wire_receipt.json`、`r20_tested_review_wire_commit.json`。

独立审查通过；5个旧集成断言仅调整为撤销新增review表示后比较原wire，纯history碰撞契约不变。完整数据/输出/权限/预算守卫不变。保存的7个真实Reader请求精确无损回放通过，其中2个在含说明后各净省98字节；这不是token或16K准入证明。

## 真实运行状态

旧R19自然结束：original1ok+13服务失败，新方法2unresolved+12服务失败。27个失败分类为25仅服务记录、1混合、1非服务。root实际严格gate退出1，独立封存source/config/data/fixed14/28行一致。无terminal/audit生成，不能宣称相关修复实测成功。最新TCP与实际计数接口检查均成功；R20目前无计数服务失败记录，但不能保证后续可用性。

新候选实际输出 `outputs/v4_validation_r20`、PID26942；`r20_root_launch_receipt.json`核对105运行哈希/配置/固定14/公开题目摘要/数据清单。整轮尚未完成，不能借用R19或旧R18的12/14执行成功结果。不会删换题、增加预算或使用标签调参。

## 36项离线回归索引

真实模型gate均待通过；不等于正确率或形式证明。

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
| 36. `lossless_failed_review_text_input` | `tests/test_v4_review_wire.py`、`tests/test_v4_review_wire_independent.py`、`tests/test_v4_history_wire_review.py` |

## 尚未交付

正式tar、同一tar安装验收、精确旧包清理均未执行。源码通过真实固定14题严格验收后才做审批/构建/安装/清理。既有独特诊断与源码工作树保留。


最新补充：R20已记录首题未解失败，仍让固定14题自然结束；当前不能批准发布。两个旧修复请求实测新review表示各增加9输入tokens，不能以字节减少宣称容量改善；首题实际未使用共享codec，不能混同归因。14份历史metadata已预先保全并独立核对（276682bytes），原归档/staging/诊断/source均未删除；最终tar安装gate保持。
