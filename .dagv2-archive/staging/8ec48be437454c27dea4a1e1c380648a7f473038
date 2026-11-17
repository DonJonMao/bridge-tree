# R19 control_v4 最小 handoff 修改记录

范围：root 明确授权后的 RECONCILE 工作树修改。生产拥有范围只有 `dagbt/joint_reading.py::_handoff_failures`，新增测试只有 `tests/test_v4_handoff_executability.py`。未修改 RELEASE、residual_control 生产代码、已有测试或 root 的 schema 区域；没有 commit、真实模型/网络调用、full suite、评分、标签读取或 R18 输出变更。

## 变更

- 未接地的未来目标继续沿原 `_payload` / `_fits` 检查 provisional footprint；容量不适配只发 `joint_support_handoff_deferred`。
- 不把这个 advisory 返回为局部 citation failure，因此不阻止本地已验证的证据与同批反证整合，不为它支付同 draft 修复。
- 自身 conflict recheck 例外保持 strict；grounded 非空目标、真实 audit 与 symbolic format 保持原 gate。
- 函数返回类型不变；没有新队列、pending/forced demands、exhaustion 重置、材料签名变更或自动 owner 重修。
- 事件记录缺失父项、实际 parent versions、program identity/revision、source 数及稳定集合 hash 和上下文限额；没有伪造 `_fits` 未返回的精确 token 数。

## 可复查的测试结果

先新增反例，在原 handoff 生产逻辑上运行：

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_handoff_executability.py
2 failed, 2 passed in 0.19s
```

失败分别是：合法独占新来源的 fresh proof 被未来未接地目标以 citation_capacity 拒绝；相同情形的实际 read 额外支付一次局部 repair。新测试用 scripted transport 和可控 `_fits` 返回值隔离 handoff 决策，本身不宣称测量真实服务 token 边界。

实现后同命令：`4 passed in 0.17s`。

相关既有回归与新测试：

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_joint_reading.py tests/test_v4_audit_dependency_projection.py tests/test_v4_handoff_executability.py
53 passed in 0.73s
```

既有测试包含实际 wire 容量构型下宽引用→充分窄引用修复、同批 counter、冲突与 audit 投影边界。`git diff --check` 通过。contracts agent 的独立真实 wire 反例及其他新增验证由 root 另行汇总，本文不提前声称其结果。

## 文件身份

- 外部设计 `/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r19_handoff_separation_design.md`：`f0bdebbb7f6ad6587d4c0b94b559a2195111843575956228361955deba887dc5`
- RECONCILE `dagbt/joint_reading.py`：`e27b1f321995c0e933fbdfbf069671c1edf1f52ec1505ebf7a79093967a8e077`。这是整个文件 hash，包含 root 此前独立 schema 修改，不能将整个文件 diff 都归本 agent。
- RECONCILE `tests/test_v4_handoff_executability.py`：`b0fca5ab99ad55a2fc3c13b79673964bc081e2194cf958ece37edb3a7792ee04`

## 局限

先保存的合法 proof 后来仍可能在真实闭包中超容量。此补丁不新增对已解决 owner 的容量复核、summary 改写或预算；没有合法新动作时允许如实失败。case13 的原 75-source 硬义务与全部失败事实保留；此测试结果不证明 case13 已通过或正确率改善。
