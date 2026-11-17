# 当前批次 frozen IDs：独立回归与边界复核

仅新增 RECONCILE 的 `tests/test_v4_frozen_ids_schema_review.py`。未改生产或旧测试，未运行整套，未 commit。全部使用 synthetic 原文、observation、local fake response 和 fake actual counter；网络被禁止，未调用模型/tokenizer，也未读取标签或评分。

## 基线与修复后

- 基线 `e02c8cc5349aca3222319927f05cf573a765c58c`，`joint_reading.py` hash `f7a01fd53130d1782766c1fbdb09cc43d7ead1ca864e77c5597272b896cb7490`：最小真实 Reader 回归 **2 failed / 0.23s**。unknown 与 partial 都在第二次 repair 的实际 schema 仍接受本批已冻结行处失败；不是仅检查新增字段缺失。
- 已保存基线最小测试副本及 `r20_frozen_ids_schema_baseline_failure_receipt.json`，SHA-256 `ab2988c8d43aae37aabc8f302ba9a7612359efc5486e2015535484df67157334`。通知 control 基线封存后，control 才修改生产源码。
- 修复后，独立扩展 **21 passed / 0.18s**。被测源码 hash `263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`；测试 hash `b1513b200cadd51ebfba159e5406fcb6c09eb10907152aef0bcfb24b2089514a`。

## 已验证的边界

真实 Reader 的未知/部分行先合法规范化并冻结，下一次实际 repair schema 禁止普通重述，而且不提供 reviewed ID 权限。fake model 刻意继续重述时，原 runtime 仍拒绝，保留问题、原行与 pending，不会因 schema 补全自动完成。

真实 whole-value 回归包括两个互不一致的 support 草稿与一条合法 counter：后续 repair 的 F 只保留 counter，两个 support 以原 ID 可编辑；修复后 counter 原样生效，完整值正常绑定。另实际验证新批 known route ID 可重用、durable 原草稿 ID 仍可按现有授权修复，不会从历史 validated 字段继承当前冻结。

独立 schema 检查确认 F 按变量隔离，相同裸 ID 不串扰；无 R 也禁止 F；旧 R-only fixtures 的禁止/引用行为保留；F 不授予引用或模型输出字段权限。真实 named repair 还确认 F 排序稳定，包含不能引用的 unknown 和无来源 irrelevant 行。

summary/handoff 两项使用合成 guard 失败信号，验证真实循环在构建下一 schema 前已经移除退回 support 的冻结 ID；这两项测试的是状态处理时序，不声称额外验证这两个 helper 的语义判断。

完整 repair payload 在 admission 阶段与最终发送阶段一致，新增 metadata 和完整 schema 均参与计数。专门的容量用例让包含新 F 的真实 repair 输入超出边界 1 token，确认不发送该 repair、不消耗 repair 预算，原未决责任保留。这里的 token 数是明确的离线 fake actual 测量，不是部署端测试。

## 只读源码审查

当前 diff 仅在所有既有解冻处理之后生成按变量 F、让 schema 禁止 F 与旧 R 的并集，并在存在 F 时加入解释。reviewed IDs 仍由原 settled offer 独立授权；原 runtime guard、offer、义务解除、预算规则未改变。未发现超出已批准设计的权限变化。

离线通过不证明模型一定遵守提示/schema，不解除 R20 case04 的 18/16-source 原义务，也不证明该题完成或答案质量。

完整 receipt：`r20_frozen_ids_schema_independent_receipt.json`，SHA-256 `32346246573a0dd6c49e39f16455f83f37b826256bd44df0942a42d893c81282`。
