# 实测 token 选择：独立离线复核

独立新文件 `tests/test_v4_review_wire_selection_review.py` 在 RECONCILE 通过 **69 tests / 0.17s**。本 reviewer 仅新增该测试文件；未修改生产源码、既有测试、RELEASE 或在线运行。使用 synthetic 数据和独立 fake actual counter，网络接口被禁止，未调用模型/tokenizer，也未读标签或评分。

计数 oracle 来自预先声明的完整 payload 测量值，刻意不与字节长度绑定；没有调用生产 selector 来生成预期答案。测试保留真实 Reasoner 序列化、preflight、request 和原文 exposure 逻辑。

已覆盖：

- 六种 Reader/compose/audit 与 repair 操作：只有两个候选均标记 actual 且 review 严格少于 baseline 才选择 review；相等、更多或非 actual 保留 baseline。
- 三种响应模式下完整 schema、system 解码指令与 output cap 参与计数；选中 payload、最终 Reasoner preflight payload 和送入 transport 的 payload 精确一致。
- baseline 恰好装入上下文而 review 超限时仍可发送 baseline；两者超限仍由原 preflight 阻断，不绕过预算或容量。
- counter 抛出 `ValueError` / `ConnectionError` 时异常原样传播；全原文 exposure 已先记录，hard unread 保留，无模型发送和 LLM 预算消耗。transport 失败保持原来的 logical call、计费与 exposure 语义。
- `_wire_candidates` / `_prepare_wire` 仍是纯准备；实际 codec 的字节候选经过独立计数才确定。原有 history sharing 在任意 review 选择下保留；存在非法 review 引用时不新增解码授权。
- 真实 `_read` 和 `_repair_terminal` 两个调用点均向 exposure wrapper 传递完整候选；在 wrapper 内选择后发送。此两项用独立 synthetic 候选生成器隔离路由行为，codec 正确性另由真实候选测试检查。

没有发现本次限定选择实现违反以上契约。此结论不代表线上 tokenizer 调用成本/缓存已经实测，也不证明任务语义或答案质量。**R20 第 1 题没有实际使用 history/review codec；本修正不能据此宣称解决该题未决、覆盖或容量失败。**

测试文件 SHA-256：`e0d7e7d090d591be7a0a126445994b5d2078da184c1b7117b80682d422ada547`。

被测 `dagbt/joint_reading.py` SHA-256：`f7a01fd53130d1782766c1fbdb09cc43d7ead1ca864e77c5597272b896cb7490`。

完整 receipt：`r20_review_wire_selection_independent_receipt.json`，SHA-256 `874bd55b0074d48d13a8500fd8a394f4de64a4f2679199b366d5160aea9727b2`。
