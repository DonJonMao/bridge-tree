# R20 同批冻结 ID 表达修复：实现与定向验收

基线 RECONCILE `e02c8cc5349aca3222319927f05cf573a765c58c`；仅本代理拥有的 `dagbt/joint_reading.py` 和新增 `tests/test_v4_frozen_ids_schema.py` 有改动。README 属于 root，另一个新独立测试文件属于 contracts。未修改 RELEASE、旧测试、Reasoner、token counter、codec、配置或运行状态；未启动新线上实验、服务请求、整套回归或 commit。

实施前，contracts 的真实 Reader 回归在原始源码 `f7a01fd53130d1782766c1fbdb09cc43d7ead1ca864e77c5597272b896cb7490` 上 2 failed：第二轮实际 schema 仍接受本 batch 已冻结的 unknown/partial 普通重述。原失败凭据 `r20_frozen_ids_schema_baseline_failure_receipt.json` SHA-256 `ab2988c8d43aae37aabc8f302ba9a7612359efc5486e2015535484df67157334`。

实现：下一轮 repair 输入增加 `repair_scope.frozen_observation_ids:{variable:[sorted IDs]}`，只取当前 batch 全部解冻检查之后、当前 failed variables 的非空 frozen 集。schema 对每个变量禁普通重述 F∪R（保留旧 offers-only 禁令），引用仍严格只许 R。prompt 只在有该字段的请求中补充“禁止重述不授予引用/解除权限”，明确列出 unknown/partial 不会变成 settled review。现有 runtime guard、预算、义务范围/解除规则保持原样。字段完整进入 repair identity、两种 wire 候选、schema 和真实计数。

冻结待 root 终验的文件：

- `dagbt/joint_reading.py` SHA-256 `263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`
- 新测试 SHA-256 `be760da512c3a71e5ca11b6ceb708d6ddfe8991d70598f69367a77ac6598e3f4`

我方新增测试 **11 passed / 0.23s**；随后含该文件的 11 个相关测试文件 **242 passed / 2.14s**，exit=0；`git diff --check` 通过。测试命令均使用 `/Users/mao/projects/dagv2/.venv/bin/python -B -m pytest -q -p no:cacheprovider`。

相关文件：`test_v4_frozen_ids_schema.py`、`test_personamem_joint_protocol.py`、`test_v4_joint_reading.py`、`test_v4_mandatory_contract_review.py`、`test_v4_obligation_feedback.py`、`test_v4_obligation_review_feedback_review.py`、`test_v4_reconcile_review.py`、`test_v4_failed_batch_review.py`、`test_v4_summary_source_feedback_review.py`、`test_v4_summary_revision_review.py`、`test_v4_review_wire_selection.py`。

新增覆盖包括真实 whole-value 解冻与 counter 保留、真实 summary 反证冲突解冻、缺源 draft 可编辑、真实 handoff 容量拒绝后原 ID 可修复、durable checkpoint 后新 batch 隔离、known route 不导入、同 ID 不同变量、旧 offers-only 兼容、合法 settled 引用仍可完整解除，以及新字段进入两个完整 wire 候选和计数/选择身份。contracts 另报告同一源码 hash 的独立 21 passed，由其单独封存凭据。

此前 selector 版 Full25 的 2349 passed 只适用于 e02c8cc。该新源码尚待 root 的完整 diff 复核和 Full26；本 receipt 不将历史整套成绩当成当前源码成绩，也不宣称修复后一定消除原始 semantic 未决或提升准确率。

case02/04 只读报告已按 root 审阅修订：owner-blocked handoff 现状符合现有 `HANDOFF_EXECUTABILITY_POLICY.md`，只保留未来 policy 扩展候选，未纳入本补丁。修订 MD SHA-256 `ea48e5fafdfd55532cec431950d754a2d6a621c1ac1101b51fbb8404e2135880`；旧 hash 与修订理由保留于末节，证据 JSON 不变。
