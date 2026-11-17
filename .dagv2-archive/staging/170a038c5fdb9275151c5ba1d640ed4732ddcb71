# 既有测试的 discovery frontier 政策核对

静态审查指定六个测试文件，RECONCILE HEAD 为 `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`。未改源码/测试、未运行测试、未 import 新源码、未调用服务。依据 `r17_unread_policy_design_review.md`、独立审查的不变量及 root 随后明确的最终接口：**统一 ordinary residual discovery；显式 `discovery_doc_ids` 提供可信发现来源；缺参数/未知来源仍是 legacy hard。** 设计稿早期仅限 `personal_history_summary` 的建议已被最终决定替代。

**不能机械修改这些旧测试的 pending 断言。** 当前直接 `reader.read(...)` 均未传新 provenance 参数，原路径仍应验证 legacy 行为。以下“需更新”仅指 root 决定把该用例改为生产 controller 的可信 discovery 场景后，需随之更新的政策期待；最好保留 legacy 分支。不要全局改变共用 `read_all` helper 的默认 provenance，意外把所有旧断言同时改义。

## 1. 六个需要明确测试身份的用例

下表 `adaptive`、`prefix`、`headroom` 分别指 `test_v4_adaptive_initial_cap_review.py`、`test_v4_prefix_admission_review.py`、`test_v4_headroom_review.py`。

| 测试名 | 显式 discovery 分支应改变什么 | 必须保留什么 |
|---|---|---|
| adaptive：`test_impossible_or_unverified_structure_floor_keeps_every_source_pending_without_paid_calls` | 从未发出的纯候选留 typed frontier；不能仅因排队就把全部 alias 写 hard unread、令 history pending。保留无 provenance 分支的原期待。 | 没有请求、reasoner sequence/LLM/JSON 消耗为零；不伪造 read/irrelevant/failed；原始来源和 OLD 绑定不改。fixture 的 s1 已是 OLD 的引用来源，不能把全部 aliases 一概宣称无必要关系；新候选与既有证明来源须分别核对。 |
| adaptive：`test_adaptive_headroom_does_not_rescue_a_request_failing_ordinary_full_repair_capacity` | discovery 入场失败本身不产生“已尝试”义务；`pending == {'history'}` 不能再仅由纯候选排队推出。 | 完整 repair 容量仍不足就不得发请求或降 repair 输出额度；LLM/JSON 零消耗；真正 required/旧 hard 工作仍阻塞。是否保留 `InputOverflow` 为 API 表达，由 controller 的既定错误接口决定，不能以去掉异常掩盖强行调用。 |
| adaptive：`test_later_capacity_failure_retains_unread_suffix_and_already_accepted_history` | 最直接的一调用读全政策用例：第一批 s1/s2 完整处理后应 yield，不应在同一次调用自动尝试 s3 并抛后续容量错误。s3 保留可恢复 frontier，不能仅凭 s3 排队使已支持 history pending。 | 首批只有一实际请求，cap=1024；OLD、来源原文及所有真实义务保留。s2 已在实际 wire 中，即使只引用 s1，也绝不能把 s2 归回 never-offered frontier。另一次有合法继续需求的调度才测试 s3 恢复/容量拒绝。 |
| adaptive：`test_changed_payload_after_selection_rejects_before_generation_and_keeps_original_obligations` | 若明确使用 discovery provenance，替换“所有 aliases 必在 unread_obligations”的存储断言为：纯候选仍在 frontier，旧/required 工作不丢。原未知来源分支仍保留原断言。 | 选中后 payload 改变必须拒绝，零生成、零 paid budget；不能借新 frontier 政策绕过 selection identity。 |
| prefix：`test_rebuilt_payload_order_change_rejects_before_generation` | 与上一用例相同：只调整显式 discovery 分支的工作分类/存储，不改变序列化顺序参与 identity 的检查。 | payload 内容相等但 wire 顺序变化仍不可使用旧 admission；零请求/零预算；所有 owner/source 工作均可追溯。 |
| headroom：`test_smaller_initial_window_admits_real_whole_repair_without_dropping_later_sources` | 在可信 discovery 分支，未发送的后缀不能仅因排队造成 `reader.unread_obligations and state.pending == {'history'}`。fixture 的 `type=set` 本身不是保留此额外门槛的理由；本例没有额外“全集/所有历史”完整性证据要求。 | `len(calls.requests)==2` **不改为 1**：这里是同一 batch 的初始请求＋whole-value repair，必须完整处理后才 yield。两份真实引用、完整 repair 原文、JSON 消耗=1、16k 检查、支持整值及全部未发送来源继续保存。 |

仅 `_fitting_prefix`、`_adaptive_fresh_cap` 等预检的测试不表达发布充分性：`test_mixed_binary_probes_install_only_the_winning_candidate`、`test_nonmonotone_no_fit_binary_path_checks_untested_prefixes`、`test_full_candidate_never_counts_floor_and_resets_a_previous_adaptive_choice` 等无需因 frontier 改变数值/选择期待。`test_fallback_uses_largest_window_and_actual_cap_reaches_preflight_request_and_record` 首批已包含全部三条来源，仍是一实际请求；不能把“一批”误改成“一条来源”。

## 2. 必须保留的 hard、mandatory 与快照断言

**已发送、修复及同批原子性。** adaptive 的 `test_length_with_valid_json_never_publishes_and_same_originals_do_not_buy_new_attempts`、`test_actual_repair_overflow_cannot_lower_repair_cap_or_remove_originals_to_force_a_call` 必须继续保留 pending、失败原文及换 identity 不重获调用资格；`test_repair_restores_full_4096_and_keeps_the_exact_initial_source_window` 的两次调用和完整来源也保留。reader-scope 的 `test_frozen_ordinary_restatement_is_slot_failure_then_explicit_ref_can_recover`、`test_named_new_id_becomes_required_failed_draft_on_following_repair`、`test_paid_failed_batch_local_repair_omits_frozen_draft_and_still_recovers` 的 3/3/2 次 scoped 请求是同批修复链，不能在首个 support 后 yield。mandatory-contract 的 `test_global_envelope_repair_can_resubmit_its_not_yet_frozen_counter`、`test_explicit_whole_value_review_unfreezes_only_the_failed_support_drafts`、`test_explicit_duplicate_replacement_ids_can_preserve_the_original_counter` 同理，尤其不能因前半 support 而丢后半 counter。

**手工 unread 与旧 owner。** 以下显式注入 `unread_obligations`，没有 never-offered/可信 discovery 分类凭据，必须保留 hard 含义，不能由新字段缺席推定 optional：

- mandatory-contract：`test_unread_admission_rejects_unowned_or_incomplete_work_without_changing_markers`、`test_owned_unread_keeps_its_exact_variable_set_until_real_processing`、`test_foreign_unrelated_unread_survives_bound_read_and_checkpoint`、`test_same_identity_unread_is_not_erased_when_capacity_prevents_any_call`。
- reader-scope：`test_scope_rejection_preserves_reader_and_source_ownership_before_counting`、`test_whole_closure_capacity_failure_keeps_every_owned_marker_without_generation`、`test_complete_closure_settles_only_its_owned_same_query_marker`。
- proof-projection：`test_unread_work_on_omitted_alternative_source_is_not_erased_or_migrated`，包括 foreign/same owner 两分支。它保护已有未知分类工作，不是要求新纯 discovery 必须 hard。

**mandatory 仍须整批。** mandatory-contract 的 `test_mandatory_sources_are_one_full_batch_without_containing_doc_or_neighbours`、`test_nonterminal_compose_with_only_bound_sources_really_calls_and_solves`、`test_bound_read_includes_actual_transitive_parent_sources` 及 reader-scope 的 `test_unbound_nonterminal_compose_still_pays_for_one_real_request` 不得改为可成功前缀或零调用。共同前提/实际父/相关 counter/已观察 clue 仍完整；`test_audit_closure_reproduces_alternative_routes_counters_failed_evidence_and_current_clues` 中失败和 evidence 记录不能被一次空槽 audit 清除。

**真实依赖与恢复资格。** proof-projection 的 `test_projection_preserves_sourced_unresolved_obligations_and_pending`、`test_terminal_projection_preserves_failed_drafts_whole_reviews_and_their_originals`、`test_unresolved_terminal_target_protects_its_parent_alternatives_even_in_parent_only_repair`、`test_actual_pending_terminal_dependency_keeps_parent_alternatives_and_blocks_certificate` 的阻塞均来自真实义务，保留。`test_audit_eliminated_pending_terminal_sibling_does_not_protect_parent_alternatives` 也保留：不被当前证书采用的 sibling 可以未解，但其记录仍存在，不能变成“全局清 pending”。mandatory-contract 的 `test_switching_to_mandatory_mode_and_renaming_cannot_buy_failed_compose_recovery`、`test_paid_new_batch_may_reuse_required_failed_draft_ids_after_checkpoint` 保留身份/付费/新证据门槛。

**来源完整性。** proof-projection 的 `test_selected_summary_keeps_cumulative_original_sources_and_archived_ancestry`、`test_revoked_summary_ancestor_and_inheriting_descendant_remain_visible`、`test_history_summary_revision_keeps_all_current_targets_and_their_required_sources` 不随 frontier 变宽而削弱；`test_prospective_handoff_and_actual_terminal_share_selected_proof_scope` 仍要求预测与实际相同。没有观察到这些测试需要通过删除 hard 断言来配合新政策。

本核对只给测试政策分类，不证明新实现已满足这些条件，也不把历史摘要或一条 support 当作任何集合/规则/否定/最新值任务的充分证明。
