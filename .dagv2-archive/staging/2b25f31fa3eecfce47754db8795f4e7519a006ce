> 状态更新：下文是最后已验证的 8dac 提交记录。RECONCILE 当前正在实施独立审查后的探索前沿分离，1880 项测试不能用于证明新字节通过。R17 已在 bcbd16f 自然结束并失败；下一轮须待新候选完整测试、提交和身份核对后另行启动。

# PersonaMem v4 当前候选需求审查

候选是隔离目录 `dagv2-personamem-v4-reconcile` 的干净提交 `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`。
运行目录 `dagv2-personamem-v4` 仍是 `bcbd16f`，R17 writer PID 96297 本次实查存活；不能把 R17 当作新候选的模型验证。
新候选 R18 尚未启动，`release_ready=false`。本文覆盖当前需求映射和证据状态，不承诺代码无误或模型回答正确。
旧版详细审查完整保存为 `requirement_audit_through_50d1ba0.md`；其中的历史运行状态不得用作当前状态。

## 已完成的验证

完整命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`：1880 passed、69 warnings、106.15 秒，退出码 0。
日志 `full_tests_20_proof_scope.txt` SHA256 为 `98023913f92ea84c12bb2a48c7e56768b57c536861f92b3cd23ead45ba979ed7`。
`full_tests_20_proof_scope_receipt.json` 记录测试前后 303 个文件不变；`reconcile_8dac32b_validation.json` 绑定提交及 104 个运行源码哈希。
这些是现有测试的复用记录，本次没有重跑测试、改源码或调用模型/tokenizer。
新增范围修正包含独立 32 例与 controller 10 例，已包含在 1880 总数中，不能重复相加。
高容量协议夹具仅验证语义和边界，不证明 16K 请求能够容纳真实材料。

## 28 项需求及证据索引

下表沿用已审查的要求和回归映射。每项的当前状态均为“当前源码全套离线通过，当前源码真实模型验证未完成”。
测试存在且全套通过不等同于逐项形式证明；实际运行限制见后文。

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

## 最新修复与理论边界

事实状态已按 OR 选择一条充分路线；原输入却重新带入其它归档路线，且审计父任务范围比实际依赖更大。
当前 `audit_scope` 使用实际证书/语义依赖、规则及真实祖先，并精确到变量，避免同任务其它输出扩大审计。
终端合成仍须具有声明所需父依据，不能在答案尚未形成前假设某个父变量无用。
只有普通、等值、有效、非选中且不涉及当前复核/修订/反证的备选正向路线可不进入当前 mandatory 请求。
归档、来源、版本、摘要祖先、反证和未解决事项没有删除；当前摘要继承的累计来源不裁剪。
下游仍未决时，同一个父值相等不能证明其新原文无用；pending、evidence、failed 输出仍保护相关父备选，包含 parent-only repair。
历史阅读与中间历史合成保持完整范围，普通 final retrieval 不使用这项 mandatory 投影。
所有生产观察校验路径只接受本次实际提供的撤销目标 ID，与 schema 一致。

原设计 `docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md` 3.4/6.3/7.3 分别规定一般语义父接地、当前需求必要材料、实际支持及相关反证审计。
“完整必要闭包须单次共同可见”“摘要修订继承全部旧来源”“未决义务不跨批借用覆盖”是当前明确的执行契约；不能把全部归档记录都推断成每次必要输入，也不能静默裁剪真正必要来源。
独立说明见 `r17_mandatory_proof_scope_review.md` 第 10 节与 `r17_selected_proof_dependency_review.md`。

## 真实运行证据和未完成事项

R16 在旧源码自然完成：original 14 ok；residual 6 ok、7 unresolved_or_exhausted、1 execution_failed。
R17 在 bcbd16f 上继续运行，实时状态以 runner 和 `r17_structural_monitor.json` 为准，不以本文快照代替。
目前前三个失败的类型包含容量不足、来源复核条件不满足、修复次数耗尽；前两题已接受摘要来源并集为 37/41，删除退休祖先元数据也不减少原文来源。
因此最新的 OR 输入投影未被证明能解决这些具体失败；R18 必须如实检查，不能从离线通过推断成功。
无损共享文本已经在 R17 部分真实请求中正确解码；这仅支持传输结构，不证明答案准确。

PersonaMem 数据为 v1 32K 历史版本；16384 是原实验的完整单请求预算，不是数据长度或顶会统一预算。
LLM 24、ANN 36、JSON repair 6、完整修复/终端输出 4096 等原约束未提高。
当前范围内，必要来源或未解复核材料仍可能超过容量，模型也可能遗漏字段或来源；不能把所有残余失败归为实现 bug。

下一步：R17 自然结束并封存 → 切换经测源码 → 核对代码/配置/数据/固定 14 题 → 新 R18 → 生产 smoke gate。
只有真实通过后才进行源码审批、正式 tar、该 tar 的隔离安装验收及已审定清单的清理。
正式包、安装回执、旧包删除均尚未执行。当前没有新版准确率提升结论，也没有使用标签调整生成。
