# PersonaMem v4 candidate requirement audit

Candidate e6677081cdfb33c01db3aaa274a497168f314f78 is committed and clean in isolated RECONCILE. Full26: 2381 passed, 69 warnings, 71.18 seconds, exit 0. All 319 files remained unchanged and were checked against the commit blobs. Evidence: full_tests_26_frozen_ids_schema_receipt.json and r21_tested_frozen_ids_commit.json. Test log SHA256: 4fed28a000d689c880bb8efa283f7085d47385a923f370849b82866662660c42.

RELEASE remains frozen at 6c04637 while R20 completes naturally with known failures. The new source has not been promoted or run as R21. release_ready=false. Historical model results do not validate this source; offline success does not prove answer correctness.

The two new changes require strictly smaller actual complete tokens before choosing review sharing, and expose all current-batch frozen IDs separately from settled-only reference authority. Runtime evidence/scope/counter/coverage/budget guards are unchanged. Independent real Reader regressions failed twice before the schema change and pass afterward. Saved case04 replay adds only the missing ID ban for calls10/11 and preserves the new-batch boundary for call9; it does not establish model success.

## 38 offline requirement checks

All listed tests were included in Full26 for e667. All real-model gates remain pending. Detailed invariants are in modeling_checklist.json.

| Requirement | Regression files |
| --- | --- |
| 1. `task_objective` | `tests/test_v4_personal_task.py` |
| 2. `two_graphs` | `tests/test_v4_control.py` |
| 3. `reachable_contract` | `tests/test_v4_contracts.py` |
| 4. `typed_publication` | `tests/test_v4_control.py` |
| 5. `material_progress` | `tests/test_v4_joint_reading.py`, `tests/test_v4_control.py` |
| 6. `audit_correction` | `tests/test_v4_control.py` |
| 7. `capacity_handoff` | `tests/test_v4_joint_reading.py` |
| 8. `unresolved_evidence` | `tests/test_v4_reader_review.py` |
| 9. `residual_short_circuit` | `tests/test_v4_reader_review.py`, `tests/test_v4_control.py` |
| 10. `paired_evaluation` | `tests/test_v4_release_gate.py` |
| 11. `phase_isolation` | `tests/test_v4_phase_review.py` |
| 12. `whole_value_reconciliation` | `tests/test_v4_reconcile_review.py` |
| 13. `durable_failed_batch` | `tests/test_v4_failed_batch_review.py` |
| 14. `repair_capacity_admission` | `tests/test_v4_headroom_review.py`, `tests/test_v4_adaptive_initial_cap_review.py`, `tests/test_v4_prefix_admission_review.py` |
| 15. `history_summary_revision` | `tests/test_v4_summary_declarations.py`, `tests/test_v4_summary_revision_state.py`, `tests/test_v4_summary_revision_review.py` |
| 16. `idempotent_summary_review` | `tests/test_v4_summary_noop_review.py` |
| 17. `explicit_scope_role_separation` | `tests/test_v4_personal_task.py` |
| 18. `explicit_personal_text_representation` | `tests/test_v4_personal_semantics_review.py`, `tests/test_v4_summary_declarations.py` |
| 19. `actionable_revision_source_feedback` | `tests/test_v4_summary_source_feedback_review.py`, `tests/test_v4_summary_source_feedback_boundaries.py`, `tests/test_v4_summary_source_feedback_trust_review.py` |
| 20. `lossless_whole_review_wire` | `tests/test_v4_whole_review_wire_review.py`, `tests/test_v4_whole_value_repair.py` |
| 21. `adaptive_fresh_history_output_cap` | `tests/test_reasoning_output_cap_review.py`, `tests/test_v4_adaptive_initial_cap.py`, `tests/test_v4_adaptive_initial_cap_review.py`, `tests/test_v4_prefix_admission_review.py` |
| 22. `nonempty_state_preserving_response_floor` | `tests/test_v4_state_preserving_floor_review.py`, `tests/test_v4_adaptive_initial_cap_review.py`, `tests/test_v4_adaptive_initial_cap.py` |
| 23. `explicit_scoped_obligation_coverage_review` | `tests/test_v4_obligation_feedback.py`, `tests/test_v4_obligation_review_feedback_review.py`, `tests/test_v4_whole_review_wire_review.py` |
| 24. `mandatory_source_scope` | `tests/test_v4_mandatory_contract_review.py`, `tests/test_v4_controller_source_scope.py`, `tests/test_v4_partial_failure_scope_review.py` |
| 25. `phase_repair_authority` | `tests/test_v4_mandatory_contract_review.py`, `tests/test_v4_history_wire_integration.py` |
| 26. `lossless_shared_history_input` | `tests/test_v4_history_wire_integration.py`, `tests/test_v4_history_wire_review.py` |
| 27. `actual_proof_input_frontier` | `tests/test_v4_audit_dependency_projection.py`, `tests/test_v4_proof_projection_review.py`, `tests/test_v4_control.py` |
| 28. `request_local_retraction_authority` | `tests/test_v4_proof_projection_review.py` |
| 29. `discovery_frontier_is_not_evidence_obligation` | `tests/test_v4_discovery_frontier.py`, `tests/test_v4_discovery_frontier_review.py` |
| 30. `atomic_batch_then_residual_reevaluation` | `tests/test_v4_discovery_frontier.py`, `tests/test_v4_discovery_frontier_review.py`, `tests/test_v4_reader_review.py` |
| 31. `whole_wire_exposure_and_truthful_paused_state` | `tests/test_v4_discovery_frontier.py`, `tests/test_v4_discovery_frontier_review.py`, `tests/test_v4_reader_scope_implementation.py` |
| 32. `stable_restore_without_free_retries` | `tests/test_v4_discovery_frontier.py`, `tests/test_v4_discovery_frontier_review.py`, `tests/test_v4_summary_source_feedback_review.py` |
| 33. `personal_planner_schema_and_scoped_repair_alignment` | `tests/test_v4_planner_contract_alignment.py`, `tests/test_v4_planner_contract_alignment_review.py` |
| 34. `reader_obligation_and_frozen_reference_schema_alignment` | `tests/test_v4_reader_schema_alignment.py`, `tests/test_v4_obligation_review_feedback_review.py` |
| 35. `ungrounded_future_capacity_is_not_local_fact_invalidity` | `tests/test_v4_handoff_executability.py`, `tests/test_v4_handoff_executability_review.py`, `tests/test_v4_joint_reading.py`, `tests/test_v4_audit_dependency_projection.py` |
| 36. `lossless_failed_review_text_input` | `tests/test_v4_review_wire.py`, `tests/test_v4_review_wire_independent.py`, `tests/test_v4_history_wire_review.py` |
| 37. `actual_complete_review_token_nonincrease_selection` | `tests/test_v4_review_wire_selection.py`, `tests/test_v4_review_wire_selection_review.py` |
| 38. `current_batch_frozen_schema_without_extra_reference_rights` | `tests/test_v4_frozen_ids_schema.py`, `tests/test_v4_frozen_ids_schema_review.py` |

## Incomplete work

- Let R20 finish naturally, execute its actual strict gate and preserve failed closure evidence.
- Promote/bind e667 and complete a fresh fixed14 model run. Do not change questions, budgets, outputs or use labels to tune.
- Obtain real source approval only after the gate passes; build the actual upload tar/checksum; verify installation from that same final archive.
- Execute the locked obsolete-artifact cleanup only after installation verification. Fourteen unique metadata files were copied and verified; no old archives have been deleted. Unique diagnostics and source worktrees remain protected.

The release gate still requires a stopped writer, complete state, all28 successful legal canonical rows,14 actual semantic terminals with fresh complete audits, and exact source/config/data binding. Protocol success does not prove answer correctness.
