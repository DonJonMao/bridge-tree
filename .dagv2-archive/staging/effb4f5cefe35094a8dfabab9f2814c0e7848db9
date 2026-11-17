# R18 第 13 题：冻结观测重述的独立审查

**结论：event 175 的直接失败属于模型对本次 repair 授权的明确违约；未发现必须重述与禁止重述同时成立的协议死锁。** 通用摘要幂等复核文案可更明确地区分“历史已整合路线”与“本批已验证并冻结的草稿”，但现有证据不能把这次拒绝归为校验器错误。

- 冻结源码：`800c51763ea3a2bfcad459b4413d41c6432db52e`；题目 `0d2259ae-1432-46a9-81e7-e3b3e3be5cc9`。
- 只读本题 attempt 的三次请求/响应与对应源码；未读 labels/scores、未调用模型或测试、未改源码/运行、未停止任务。报告不含原文、摘要内容或答案值。

| 调用 | 实际授权与返回 | 结论 |
| --- | --- | --- |
| joint_read/4 | 1 条 support；2 条 unresolved；同时声明解除 1 个义务。 | 槽级解除条件不成立，形成 `id="*"` repair；support 本身已验证冻结。 |
| joint_read_repair/5 | failed entry 是 `id="*"`、`observation=null`，反馈要求有来源且无 unresolved；没有 frozen reference offer/schema 字段。模型仍原样重述已冻结 support，并保留 2 条 unresolved，声明解除 2 个义务。 | 重述产生冻结错误；这一步并未授权使用 reviewed IDs。 |
| joint_read_repair/6 | failed entry 仍为 wildcard；明确提供 1 个 `slot_observation_ids`，schema 允许该 `reviewed_observation_ids`。模型既填写该引用，又在 observations 中原样重交同 ID。 | 引用和重述并存，被明确禁止；event 175 保留 `valid_rows=1`，`complete=false`。 |

三次 observation 经规范 JSON 比较完全相同；repair 6 引用指向的完整 slot 行也与第 4 次已验证行完全相同。三次均 `finish_reason=stop`，不是输出截断；真实输入分别 9,984 / 10,854 / 11,232 tokens，各请求预算检查通过。

## 授权和实现是否一致

- 通用 repair 规则明确：wildcard 可以修槽，但不解冻行；只有 named failed ID 才必须重交。两次 failed ID 都是 `*`，所以 `failed.slot` 中附带原行是诊断上下文，不是 named-draft 重述要求。
- repair 6 实际系统提示明确要求用 `reviewed_observation_ids`，并明确 “Do not restate or edit a frozen observation”。schema 的允许引用枚举包含该唯一 ID；没有要求 observations 必须非空。
- 生产同时在槽级发现冻结 ID 重述（joint_reading.py:2474），并在 `_reviewed_frozen_rows` 中拒绝引用 ID 同时出现在 observations（:1892）。这与实际提示一致；schema 只规定结构和引用枚举，未编码全部跨字段冻结语义，不能据此视为重述授权。
- 第 5 次没有引用 offer 的原因也与代码一致：第 4 次包含 unresolved，属于非纯 coverage 失败，`_update_evidence_obligations` 不生成 coverage-only 复核 offer（:1967、:1988）。保留未解问题、撤回不成立的 resolved 声明、令 observations 为空是一条协议允许的保守路径；它不等于题目成功。
- 通用 summary 指令（:210）允许在“待修原草稿被明确要求”时做幂等重查，但没有 named draft 要求覆盖本例冻结边界。repair 6 的专门 offer 已消除具体引用方式的不确定性。不能从该段通用文案推导允许同一冻结 ID 同时引用并重述。

## 不能从这一处修复推导的结果

- 即便删除重述，只保留正确引用，模型仍保留 2 条 unresolved 却请求解除义务，解除条件仍不成立。已有 support 引用 7 个 source；这两项已提供义务分别要求复核 49 和 75 个 source。单独这条引用不足以证明覆盖，更不能自动放行。
- 本报告仅归因调用 4→5/6 与 event 175，不归因本题全部后续行为，不判定最终答案正确性或 R18 成败；14 题继续自然完成，不改变 guard。

## 精确证据身份

| 请求 | response_ref / 文件名主体 | 文件 SHA256 |
| --- | --- | --- |
| joint_read/4 | `1cede76c87440eb66c0045963801f9e8fae51fb5da7eb1ccc97edac5bcc79f50` | `2252765dddaf78124d92934a9bd49e1c678adcf080099b6998d2e81c6d54b0b1` |
| joint_read_repair/5 | `3ef82086d52e445e7984f55d85d88fc7025c9d18644a04d909df5032db46e8e8` | `1e9f8207a0e643228f7389114ec183c4ad9f3dc243f0dedb3af159cd0b419f8a` |
| joint_read_repair/6 | `5b06d6bcdf8b4ac45faccdc958c9bbc1f4410381ea452abd94654bf167ebd3ae` | `65d1f7ad3291bb5e5365a721d5bfcdd8aa5831b67b42083644af1120d4069764` |

冻结源码 SHA256：
- `dagbt/joint_reading.py`：`f5568ea4ad837dc32f8ebfb94afae4516efb5bb20f83dccdb2e0904eb94710eb`
- `dagbt/residual_control.py`：`b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211`
- `dagbt/reasoning.py`：`52e1d03bc8848f66be4fb3d20928765e0df34e5317f695d1d8b3bec18b4895da`
- `dagbt/personal_task.py`：`7af9cc43b08364ea824c23c4aa2072395720ff945fb1499f62956bd4d889a9a3`
- `dagbt/transport.py`：`9c974dd54e6f68243d29039b8e6c86567b9bc6c0ec91dec0e47659877e7189ee`

所有请求身份、事件原始行 hash、来源计数和结构比较见同目录 `r18_case13_frozen_restatement_review.json`。
