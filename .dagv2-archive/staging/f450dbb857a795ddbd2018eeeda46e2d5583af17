# R19 review wire：独立对抗回归与代码审查

**结论：冻结候选上独立 121 例通过；显式字段共享的独立 inverse、权限与原始草稿保留、旧/新编码分层状态，以及实际 Reader/Reasoner 接线均符合本次设计。没有发现本轮修改通过共享池授予新权限、改动 guard/预算或合并失败与已验证对象。**

## 范围与归属

- 工作区：`/Users/mao/projects/dagv2-personamem-v4-reconcile`，基底 `0cc2cc78498bcd215252fb8e82d2168868a71b3f`。
- 本人唯一新增代码：`tests/test_v4_review_wire_independent.py`；生产 helper 与 _prepare_wire 接线由 control_v4 修改。未改 production、旧测试、RELEASE、预算配置或实际运行，没有 commit。
- 所有数据为合成 fixture。未读标签/评分，没有模型、网络、tokenizer 调用；实际 Reasoner 的 _count_payload 使用常数离线桩，回复来自本地 HTTP 形状模拟。它们验证传入内容/准入路径，不能作为真实 token 测量。
- 原设计报告 §1 已更正：LLM/repair/ANN 8/2/4 是 used；remaining 是 16/4/32。更正后报告 SHA256：`644db77d7f2a2352cee934b0fde24c6d498a51e1867fc48b0980a8ad70d54d96`。没有改其他旧 receipts。

## 最终定向执行

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_review_wire_independent.py
121 passed in 0.89s
```

只运行独占新增文件，没有运行 full suite、control 的测试组或旧测试组。最终 helper/hookup SHA256 与 control 确认冻结值一致。

## 独立证据

| 边界 | 独立验证 |
| --- | --- |
| 精确逆变换 | 手写路径 grammar 与 inverse，不借生产 _rows/normalizer。逐次比较不排序、类型敏感的完整 JSON；字段/列表顺序、额外键和 bool/number/string 类型保持。生产 unpack 只作为第二项交叉检查。 |
| 全部显式路径 | supported_parents（仅 value）、known、durable validated、failed 的 observation/slot/duplicate/replacement/required-counter、whole-value draft/known，以及 repair_scope 同形路径逐项覆盖。parents 为空也可共享。 |
| 全访问范围碰撞 | 每个路径上分别放两种 ref 键到短的非候选行，仍整层回退；顶层预存池同样不激活。未知/布尔/非字符串引用、value/ref 并存、缺池、非法池拒绝。parent 不允许 reason ref。 |
| 原始失败证据 | 语义相近但空白/换行不同的草稿不合并；重复 ID 不合并对象。raw invalid_response 含转义、重复键和畸形尾部仍完整保留，不 parse/dump。 |
| 不透明 literal | record/list/number/bool/null 值不转字符串；值内和任意非注册应用结构中的 ref/shared/review_allowed/source_ids 只是原字面对象。字符串池取回一次，不递归解析。 |
| 角色与约束 | source_ids、scope、实际父版本、撤销/反证、summary ancestry、额外字段、failed/known/validated 容器与 review_allowed 逐字段不变。源码只变表示，不动这些 guard。 |
| 原 producer 与旧表 | nullable failed observation/slot 支持；13 类不支持形状完整回退，decoder 明确拒绝。旧 known 列表格的列、行、cells 和 shared-shaped literal 原结构保留，不展开。 |
| 确定性与所有权 | 同输入重复打包结果一致，返回对象独立；再次打包已编码对象整层回退；不改 canonical、原 pool/来源对象或 state。无收益、仅唯一字符串和非字符串重复值回退。 |
| 分层 applied | history→review 独立两层，逆序恢复；history 已用而 review 碰撞时只附 history 说明。另有 4 个 history 碰撞但 review 合法适用例，history 字段保持字面，只有 review 说明生效。 |
| 实际完整请求 | 6 个 operation × 3 个 plain/json_object/json_schema，共 18 例走实际 Reasoner._payload/estimate/request；所计与所发完整 messages、schema、输出预留相同，canonical/schema/state/settings 不变。 |
| 真正 durable recovery | 走实际 JointReader.read，由来源变化按既有条件授权；只支付 1 LLM 与 1 repair。模拟回复仍 unresolved 时，原失败/validated/raw/source_ids 保留，失败 marker 和 pending 未清空，无有效绑定。 |
| 严格容量与输出 | 常数桩令真实修复完整输入超上限 1 时，_repair_fits 与 Reasoner preflight 均拒绝，零请求/零预算收费。模型输出 ref 字段（有无原完整值两种）均被既有 _observation 校验拒绝。 |
| 权限不能提升 | review_allowed=False 的 record 不能因共享/恢复清除；实际 _failed_review_candidates 保留原失败 ID 并报既有授权错误。 |

两处中间失败均为新增 fixture 的错误使用，未导致生产代码或 guard 放宽：

1. 一次把 wire source alias 放入临时 canonical failed 记录后又调用 _payload，原来源守卫正确拒绝；改为提前取得真实 visible map。
2. 一次给 mandatory_closure 同时传 candidate doc_ids，原作用域守卫正确拒绝；改为正常 candidate window 的 durable recovery fixture。

之后扩展分层碰撞组合并完成最终 121 项通过。测试数量不与 control 或后续 root suite 相加作为独立样本数。

## 生产静态审查

- `review_wire._rows` 只走注册路径；不递归搜索 value/嵌套同名键。parent 限 value；旧 known table 只查容器形状，cells 不属于新引用空间。nullable observation/slot 对应真实 producer 的 None。
- pack 在替换前收集全体访问行并查 reserved 碰撞。只对精确字符串计数，按确定的一般字节收益规则生成候选，并计入新增说明；不使用题号、变量名、367-token 缺口或预设答案。
- _replace 原位更名，pool 表追加，inverse 移除表并原位恢复。canonical 原对象始终不变；反证、权限、source/parent/version 等不是共享候选。
- `_prepare_wire` 的 tracked source diff 仅为先 history 再 review，以及分别根据可信 applied 添加说明；_system 和 _schema 仍从相应原协议结构生成。reasoning/fact_state/residual_control 未改。
- 现有来源别名转换在此前 canonical→wire 边界发生；本层不再解释或改写来源。raw 字符串完整保存，不借模型的 reserved-shaped dict 启用解码。
- 字节门槛只选表示；既有完整真实计数、输入余量、输出预留、修复收费和失败关闭路径仍负责准入。共享池不是 progress/observation/citation，也不添加 owner retry。

control 提到旧 history 回退测试中有 5 条“整个最终 wire 必须不变”的既有断言冲突。本人没有运行或修改这些旧测试；新增 4 例独立证明：history 回退后，独立 review 层可以合法改变物理表示，但 inverse 恢复原数据，且不添加 history 解码说明。是否修改旧断言及完整回归由 root 审查；本报告不声称旧测试组或 full suite 已通过。

## 冻结身份

| 文件 | SHA256 |
| --- | --- |
| dagbt/review_wire.py | `d7d9174ea9f0b319f6fc994adce866d2ad494f83b5316382511d52dcfd8e75fb` |
| dagbt/joint_reading.py | `47290d56d15a7e2b5998254ccb89f08e0eca53f784ae1c0a5b6d65e11c5c07a4` |
| dagbt/history_wire.py | `1117bc614be0205fa1ef7a65dd0b1a111069ab65da60acf2ff35a9f1a0fe3cb9` |
| dagbt/reasoning.py | `52e1d03bc8848f66be4fb3d20928765e0df34e5317f695d1d8b3bec18b4895da` |
| dagbt/fact_state.py | `e55b9535d2c55ea87be3de59f4c5e1123e0eac06dc7e672827ba466e9c94c91e` |
| dagbt/residual_control.py | `b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211` |
| tests/test_v4_review_wire_independent.py | `b40e2dc60ffae6f786d6b2f322a958437e5628a216b64b29c0a63904bfb2a73b` |

回执：`r19_review_wire_independent_receipt.json`。

本结论只证明上述离线表示、权限和接线边界。没有测量真实 tokens，不声称节省 367、不保证 16K 准入或 R19 首题恢复成功，也不证明模型正确理解引用或准确率提高。当前原始失败轨迹、预算和发布 gate 仍保持原义；部署与新真实运行由 root 独立决定。

