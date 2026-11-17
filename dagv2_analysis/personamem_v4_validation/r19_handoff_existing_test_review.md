# R19：既有 handoff 测试的只读静态审查

结论：**本次审查未发现需要因“尚未接地的未来目标改为 advisory”而修改期望的既有测试。** 现有真实容量拒绝用例主要覆盖已经能够接地的下游、当前自身冲突复核，或实际审计；这些 strict 断言必须保留。新政策应由新增的独立用例覆盖，不能用放宽旧断言代替。

本报告只读检查源码、既有测试及文件哈希。没有运行 pytest、fullsuite、模型、tokenizer 或其他服务，没有读取 gold、评分或实验答案，没有修改源码、既有测试或运行结果。下文是静态执行路径判断，**不是本次测试运行通过的声明**。

## 审查对象与政策边界

- 冻结参考：`/Users/mao/projects/dagv2-personamem-v4`，提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`。
- 当前候选：`/Users/mao/projects/dagv2-personamem-v4-reconcile`。
- 候选 `joint_reading.py` SHA256：`e27b1f321995c0e933fbdfbf069671c1edf1f52ec1505ebf7a79093967a8e077`。
- `residual_control.py` SHA256：`b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211`。
- `fact_state.py` SHA256：`e55b9535d2c55ea87be3de59f4c5e1123e0eac06dc7e672827ba466e9c94c91e`。

候选只在 `controller.grounded(target) is None` 且不是当前 `conflict_recheck` 时，把未来容量超限记为 `joint_support_handoff_deferred`。已经接地的下游、当前自身冲突、审计和独立 symbolic format 容量检查仍可拒绝新 support。同批合法 counter 仍整合；预测日志不解除义务、不产生重试、不改预算。

关键解释：`FactState.valid()`（冻结文件第 132 行起）不因变量在 `pending` 中就抹去其有效值；`ResidualControl.grounded()`（第 282 行起）检查父任务的投影或有效父值，**并不把任意 pending 直接等同于无法接地**。因此一个带旧失败记录的用例仍可能有 grounded downstream，不能仅看 pending 就改其拒绝期望。

## 需修改的旧期望

**无。** 搜索范围包含 RECONCILE 全部测试中的 `_handoff_failures`、`citation_capacity`、`joint_support_capacity_rejected`、容量共享夹具及真实 mandatory-closure 拒绝用例；逐项对照冻结夹具与当前分支条件。新增的 `test_v4_handoff_executability*.py` 不属于要改写的旧测试，本报告不代替 contracts 的新增覆盖审查。

如果后续实际定向测试失败，应先核对候选源码、提示长度变化及真实夹具状态；本报告没有授权为了通过而修改容量预算、减少原文或放宽 strict 断言。

## 必须保留：已经接地的真实下游

| 既有位置 | 静态依据 | 必须保留的断言 |
| --- | --- | --- |
| `tests/test_v4_joint_reading.py:491`，`capacity_fixture`；`:531`，`test_actual_handoff_capacity_requires_explicit_sufficient_citation_repair` | 只有 `history → suggestion` 两任务。prospective 整合 broad/narrow support 后，唯一父变量 history 已有值；suggestion 的 grounded query 存在，没有缺失兄弟父任务。 | broad 触发 citation repair；修复收到原草稿和所有原来源；模型明确提供充分 narrow proof 后方可接受。仍须两次请求、无 pending、选中 narrow 来源、保留全部 mapper 原文。 |
| 同文件 `:550`，`test_larger_same_value_or_proof_is_archived_without_expanding_selected_handoff` | 旧 narrow 路径已充分绑定 history，新 broad 是同值独立 OR 备选；下游仍接地，选用充分路径。 | 完整存档 broad 路径，旧路径和值保持，不能扩张选中的必要闭包；一请求完成且无失败记录。 |
| 同文件 `:268`，`test_replaying_old_proof_does_not_exempt_new_sources_or_drop_a_counter` | counter 只撤销旧 `s1` 路径；`new-alternative` 的 `s1+s2` 是不同 support identity，prospective 中仍绑定 history=piano。suggestion 可接地，针对 suggestion 的 `_fits=False` 仍严格拒绝新路径。 | novel alternative 有 citation_capacity；旧 replay 不因新容量检查误报；合法 counter 撤销旧路径；实际状态不可因被拒绝的新 support 获得 history。 |
| 同文件 `:574`，`test_rejected_large_support_cannot_discard_a_valid_counter_in_same_batch` | counter 只撤销旧窄路径；prospective broad 新路径仍绑定 history，使 suggestion 接地；其真实宽闭包仍超限。 | broad 拒绝后 counter 仍保留；旧路径 revoked、history 未绑定且 pending。 |
| `tests/test_v4_failed_batch_review.py:268`，`test_handoff_failure_keeps_original_marker_but_does_not_roll_back_valid_counter` | 修复后的 counter 撤销旧 piano；新独立 support 绑定 painting。旧失败 marker/pending 本身不令有效父值消失；因此 suggestion 仍可接地。 | 必须仍有 citation_capacity；prospective 检查不可修改真实 routes/markers；合法 counter 不回滚；新 support 拒绝后旧失败记录及 pending 留存。 |
| 同文件 `:28` 的 `failed_capacity`、`:62` 的 checkpoint 测试、`:306` 的真实充分证明恢复测试 | 继承 grounded 的 capacity_fixture。broad 不适配而 narrow 可适配；后续恢复明确复核原草稿和原文。 | 初次拒绝/失败标记/原文存档必须存在；仅合法且充分的显式复核后解除，不能因 advisory 新政策自动释放。 |
| `tests/test_v4_reader_review.py:260`，`test_handoff_capacity_uses_the_same_batchs_validated_obligation_resolution` | 同批明确解决旧 obligation、完整复核其他来源后，narrow support 绑定 history，下游接地且闭包适配。 | 同批已验证解除应进入 prospective 范围计算；最终只用充分必要来源，无 pending，真实 semantic payload 适配。 |

## 必须保留：自身冲突、已撤销路径与重放

| 既有位置 | 静态依据与保留要求 |
| --- | --- |
| `tests/test_v4_joint_reading.py:246`，`test_legacy_ordered_route_is_reused_without_resurrection_after_a_counter` | revoked 路径的 replay 不会重新创建有效路径，history 仍无值；新检查会包含 history 本身的 `conflict_recheck`。该 retrieval 无父，query 本身可接地；即便其它未来目标 advisory，此自身严格检查仍 `_fits=False` 并拒绝。必须保留反证后不可复活、原 route identity、replay 被拒绝等断言。 |
| 同文件 `:590`，`test_conflicting_values_cannot_bypass_capacity_admission_by_becoming_unbound` | piano 与 painting 两个不同 whole 值导致 history 不绑定，触发当前 history 自身复核。必须保留容量拒绝及实际检查 history 的断言；真实旧值不能被 prospective 检查修改。 |
| `tests/test_v4_reader_review.py:18`，`capacity_downgrade`，以及 `:45`、`:59`、`:86` 的派生测试 | 冲突草稿受到 history 自身复核的容量限制；模型随后显式降为 partial/unresolved。该支路没有被政策放宽。必须保留 pending、完整实际已读原文、异查询不能清除义务、checkpoint 可恢复等断言。 |
| `tests/test_v4_joint_reading.py:229`，`test_existing_proof_replay_skips_new_capacity_admission_and_ignores_citation_order` | 活跃 proof 的相同 identity 重放在新 support 过滤处直接跳过；排序或理由变化不能生成新容量准入。必须仍完全不调用 `_fits`，routes/version 不变。 |

## 必须保留：实际审计、范围等价和实际调用拒绝

- `tests/test_v4_reader_review.py:123`：已认证的 `a=False` 消去 later 分支，不能因被消去分支宽而拒绝；仍检查决定性原文的真实 audit。
- 同文件 `:139`：即使终端任务没有声明变量，真实 `audit_joint` 容量失败仍必须拒绝支持；不能将 ready audit 归为未来预测。
- `tests/test_v4_audit_dependency_projection.py:98`：prospective audit 与实际 audit 的 task、slots、parents、source scope 必须相同；被消去分支的 pending/obligation 仍留存，不混入当前证明。
- `tests/test_v4_proof_projection_review.py:477`：新充分路径绑定唯一父，prospective terminal 与实际 terminal 都接地；选中证明范围、父版本及原文必须一致。
- 同文件 `:513`：通用 retrieval 终端仍按原文档窗口规则保留来源，不可因新 advisory 分支把它变成 compose 投影。
- `tests/test_v4_reader_scope_implementation.py:58`、`tests/test_v4_discovery_frontier_review.py:138`、`tests/test_v4_mandatory_contract_review.py:201`：直接调用真实 mandatory closure 的容量拒绝、零模型请求、原文/义务保留及禁止窗口回退不变。未来预测许可不意味着真实调用可以超过容量。
- `_handoff_failures` 末尾的 symbolic terminal format 仍独立用真实序列化计数比较预算，未使用 deferred 条件。本次全文搜索没有发现专门以名称或断言直接覆盖其 format 容量超限的既有用例；这属于新增测试覆盖议题，**不是可放宽格式检查或修改旧期望的理由**。

## 显式模拟 handoff 失败的既有测试不应改写

以下测试替换了 `_handoff_failures` 本身，检验的是收到真实/明确拒绝后的原子性与恢复权限，不依赖新的 grounded 分支：

- `tests/test_v4_summary_source_feedback_boundaries.py:72`：补齐修订引用不能绕过 handoff 拒绝、退役旧摘要或丢弃失败记录。
- `tests/test_v4_summary_revision_review.py:172`：明确拒绝的新修订不能发布，也不能先退役原摘要。
- `tests/test_v4_obligation_review_feedback_review.py:347`：覆盖审查成功不能跳过明确 handoff 拒绝及 obligation rollback。
- 同文件 `:301`：模拟在 handoff 时改变 obligation，原覆盖反馈须失效；此处不模拟容量拒绝。
- `tests/test_v4_summary_noop_review.py:135`：先注入容量失败再恢复真实方法；相同事实的显式付费复核与 acknowledgement 决定是否解除失败，无事实版本变化不能产生免费重试。活跃旧 proof 重放本来就跳过新 support 准入，advisory 不改变权限。

## 既有文件身份核对

以下十个文件在检查时 RECONCILE 与冻结 RELEASE **逐字节相同**，对应 scoped `git diff` 为空：

| 文件（均在 tests/） | RECONCILE SHA256 |
| --- | --- |
| test_personamem_joint_protocol.py | `84420478e64946d039dcc511bac119017559d49bdbdcf7ef1be5fb515716152c` |
| test_v4_joint_reading.py | `6f5a3feaf1e1c1a290674aa394a6d2b20a9125eaab7e649cb1b5d532a94092a2` |
| test_v4_failed_batch_review.py | `ccba71b71b1155fee22d14c5cc74e4e6255e181d8835e343cbcd6a0ec9e70f4e` |
| test_v4_reader_review.py | `f44339e7bdeff12859f6062bc13c4543520c59a13ed4a6929bca3e317451c629` |
| test_v4_proof_projection_review.py | `822f719718bf37622b9b11165d147e10fe9c9d16335310c24679c9a3e9be2f4a` |
| test_v4_audit_dependency_projection.py | `f638f086957d16ba65154386a6cd8e396d2efbd39848b7e23ec9e079b5720547` |
| test_v4_summary_source_feedback_boundaries.py | `7fedb420717b05f76e6d91844ccc84f6dc66a81a1873fcee42c9ebc8a546cebe` |
| test_v4_summary_noop_review.py | `08a29f5d36c800e8d67c14f5c750d4530e161eb9c59bb16136cc4f33c8f276c8` |
| test_v4_summary_revision_review.py | `c35c7abdf82ee5941653ec57b859f79ba88fee4db52994954f89f4f3cc32b53d` |
| test_v4_obligation_review_feedback_review.py | `bfeb9e1f5b8efe7e51c13d89b6270dc341295525f937c31a1a6cdfcec24f7a78` |

本报告不回填冻结运行、不宣称 R19 实验通过或修复后效果改善。是否运行定向测试及任何既有测试改动均由 root 负责；本次建议是保留以上旧断言原样。
