# R19：旧 history 集成断言与独立 review 表示层

状态：**只读静态复核完成；这 5 个旧断言的失败可由合法新增表示层解释，不构成 history 碰撞保护降级。仅建议调整物理表示比较的边界，不删除碰撞、权限或无副作用检查。** 本文未修改或执行旧测试。

## 精确范围与冻结证据

control 的 `r19_review_wire_implementation_receipt.md` 报告旧定向组 5 failed / 41 passed / 6 deselected。本人阅读并逐项定位：

- `tests/test_v4_history_wire_review.py:test_prepare_collision_keeps_old_wire_and_never_adds_reference_instruction` 的四个参数：shared_history_texts、grounded_subquestion_parts、parent_value_ref、known_value_ref。
- 同文件 `test_prepare_has_no_stale_applied_status_between_requests`。

本人新增的独立测试文件最终已为 **121 passed in 0.89s**（不是较早的 117）；最后新增四例直接覆盖上述四种 history 碰撞，由手写 review inverse 证明恢复原数据，并确认不添加 history 解码说明。测试 hash：`b40e2dc60ffae6f786d6b2f322a958437e5628a216b64b29c0a63904bfb2a73b`。详细回执保持原文件不变。

生产冻结：
- review_wire.py：`d7d9174ea9f0b319f6fc994adce866d2ad494f83b5316382511d52dcfd8e75fb`
- joint_reading.py：`47290d56d15a7e2b5998254ccb89f08e0eca53f784ae1c0a5b6d65e11c5c07a4`

## 为什么是比较边界问题

旧测试的 old_wire 是 `reader._wire_data(original)`。以前 _prepare_wire 只有 history 一层，所以 history 因保留字段碰撞退回时，最终 wire 恰好等于 old_wire，system 也恰好只有 _system(old_wire)。

现在 _prepare_wire 明确按以下顺序执行：
1. history.pack_with_status(old_wire)；碰撞时返回 old_wire、False。
2. review.pack_with_status(上一步结果)；只处理自身显式 value/reason 字段，可能返回新的共享表示、True。
3. 根据两个独立可信 applied 标志分别加说明。

旧 history 字段（包括恶意/字面 shared_history_texts、grounded_subquestion_parts、value_ref）没有被 history 解码，也未给它们加 history 说明。review 表示层用不同 ref namespace，只把自己的字符串引用取回一次；其 inverse 后恰好得到 old_wire，含原来所有 history 字面字段。它不借这些原字段推导权限或事实。

因此旧的 `canonical(wire) == canonical(old_wire)` 在这一集成层不再是必要条件；必要条件是“撤销确实应用的新 review 表示后原输入完全不变”。这不改变 history 单独 codec 的碰撞回退契约。

## 最小可接受调整建议

仅限上述两个集成测试函数，不批量替换全库 assertions。

### 四参数碰撞集成测试

保留 before、old_wire、原对象不变、无请求/无费用及 history.INSTRUCTION 不存在的断言。建议把最终物理 wire 比较改为：

```python
# decode_review 是独立手写 inverse，例如新独立测试提供的 inverse；
# 它只撤销 review 引用，绝不能继续调用 history decoder。
assert canonical(decode_review(wire)) == canonical(old_wire)
assert history.INSTRUCTION not in system
```

system 的旧“只有基础说明”检查可以改成精确的分层期望：
- 此 fixture 输入须明确没有新 shared_review_texts 字段；因此新表若出现，只能是当前新表示的产物。
- 若新 review 表实际存在，system 精确等于 _system(wire) + review.INSTRUCTION；否则精确等于 _system(wire)。
- 不建议仅检查“system 大致包含一些说明”，也不能不分 codec 地允许任意新增说明。

还应直接核对对应碰撞字面字段未变（四种情况分别查看 top history 表、query parts、parent.value_ref、known.value_ref），并保留来源、state/schema 和预算不被准备过程修改。原测试已有 canonical 输入和零调用/收费检查；新增独立测试已补更完整 state/schema 检查，root 可决定是否把它们同时放到旧 fixture。

**不要使用 history.oracle_decode 来恢复碰撞输入**：那些字段是调用者原字面内容，history 此时未获 applied 授权。生产 unpack 可以作为补充，但不能是唯一 oracle。

### 无陈旧 applied 状态的序列测试

保持原序列：正常输入 A → history 碰撞输入 B → 正常输入 A。

只把 B 的最终物理比较改成：

```python
assert canonical(decode_review(fallback_wire)) == canonical(reader._wire_data(collision))
assert history.INSTRUCTION not in fallback_system
```

并保持第二次 A 的完整 wire/system 与第一次 A 一致，不能删除这个确定性断言。B 可以只有 review 说明；不能继承 A 的 history applied 状态。可按上一节精确核对 B 的 review 说明是否存在。review 自身碰撞不能继承上一次 review applied，已由新层纯函数和独立碰撞测试另行覆盖。

## 必须继续保持的边界

1. **所有纯 history.pack_with_status 的碰撞原样返回/False 测试不改。** 新层不影响该函数契约。
2. 新 review codec 的碰撞仍要求该层完整回退、applied=False；不能因另一个字段有收益而部分覆盖自带 ref。
3. 调用者字面 reserved dict 永远不因形状存在而启用说明或递归解码；池字符串是 literal，不产生 citation/权限。
4. raw invalid_response、草稿差异、source/scope/counter/parent/version、failed/known/validated 角色及所有未解义务不变。
5. canonical/schema/state/预算参数和发布/容量 guard 不变；输入共享 refs 不能作为合法输出。
6. estimate 与实际生成的完整 wire/system/schema 一致；没有真实 token 计数前不声称容量改善。

这是一份最小断言调整建议，最终修改仍由 root 决定。本次没有改旧 tests、生产或已有 receipts，没有重新运行旧组或 full suite，也没有把已报告的 5 failures 当成通过结果。

