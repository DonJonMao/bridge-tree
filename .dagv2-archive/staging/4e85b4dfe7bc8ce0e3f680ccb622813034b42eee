# R19 未接地未来 handoff：独立边界审查

**结论：支持按实际可执行性区分 handoff 容量检查。对冻结候选运行独立 11 例全部通过；未发现未来容量 advisory 绕过当前执行、同批反证、父版本或发布守卫。**

设计依据是理论 6.2 要求整批合法观测先整合，6.3 按实际请求预检。`grounded=None` 时 Controller 本来也不会执行该目标，因此假想未来 payload 不应否决已经校验的局部事实。这个判据比“新事实来源恰好属于另一 owner 闭包”更一般；无需通过来源重合或无父节点特判。

保存事实不承诺以后一定容得下。当前 self conflict recheck、真正 grounded 的下游、实际终端/审计及符号格式化仍须严格预检；后来所需 closure 若超容量，应原样保留来源/未知状态并诚实失败。没有新增自动 owner 恢复机制、免费重试或终端成功保证。

## 基线与最终测试

在 control_v4 尚未修改 `_handoff_failures` 时，构造了合成三任务 `a`、`b`、`terminal`：`a` 当前实际 wire 可读，`b` 有保留义务且未绑定，未来 terminal 的冻结任务输入过长。旧方法错误地把未来未接地目标的容量不足作为拒绝 `a` 的原因。首例结果为 **1 expected failure in 1.18s**，记录在 `r19_handoff_executability_independent_baseline.json`。

最终只执行自有文件：

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_handoff_executability_review.py
11 passed in 1.62s
```

没有运行全库测试、服务、远端 tokenizer 或实验；没有读取真实题目、标签或评分。唯一修改的代码是新增 `tests/test_v4_handoff_executability_review.py`，未改生产源码或旧测试、未 commit、未动 RELEASE。

## 关键独立边界

- **真实容量反例**：当前局部 read 使用真实 `_payload/_fits` 可通过，未来未接地大输入只产生 advisory；预检本身不改变 FactState、material signature 或 ledger。
- **真实 Reader 入库**：`a` 保存后 `b` 的 pending 和原义务完全保留，来源表不变，没有为 `a` 创建错误 failed batch，也不能发布结果。
- **两种顺序恢复 strict**：分别先读 `a` 再读 `b`、先读 `b` 再读 `a`。第二条支持使未来目标真正 grounded，立即恢复实际容量拒绝；只保留第一条已准入路线，第二条保留失败义务，不再记 advisory。每个局部输入只支付一次读，修复预算为零。
- **以后实际调用仍失败关闭**：先保存合法独立事实，再使目标可执行；真实 terminal read 超限时在模型调用前失败，既有路线/来源不丢失，不能产生成功 prediction。
- **同批反证顺序**：同一真实响应先给新 support、后给撤销旧路线的 counter。两者整批整合，旧路线确实 revoked，新值生效，另一独立 pending 不丢失；不会因先看到有利 support 或未来容量 advisory 跳过末尾反证。
- **self conflict 不钻 None 缺口**：四任务图中，新支持携带真实父版本；同批父 counter 令父与该支持在 prospective state 中均不可绑定，目标 query=None。自身 recheck 仍 strict，不发该目标的 deferred 事件。此例仅对 self recheck 容量返回设置显式失败桩，以隔离分支判断；prospective state、父版本、counter、payload 与 Controller 判断均走实际代码。
- **真实 checkpoint 恢复**：走 `Engine.resume` 与 `Controller.restore`，在进入新 run 的边界停止。pending、义务、路线来源、版本、material signature、forced/exhausted 与 replay guards 完整恢复，零新 planner/模型/检索调用。
- **advisory 不是进展**：重复容量 advisory 不改变语义签名、义务或预算，不清除 forced/exhausted；真实局部进展后重复同一 read 不能产生额外付费请求。
- **不是无父/来源重合特判**：已有真实父版本的新 support、以及没有任何 foreign-owner 来源豁免的新独立 OR 路线，也遵循同一个未接地未来目标规则。

中间 checkpoint fixture 曾先付费规划后调用 restore，被现有 fresh-ledger 守卫正确拒绝；改为真正空白 Engine.resume 流程后通过。未改预算守卫或生产代码。

## 冻结身份与适用范围

- `dagbt/joint_reading.py`：`e27b1f321995c0e933fbdfbf069671c1edf1f52ec1505ebf7a79093967a8e077`
- `dagbt/residual_control.py`：`b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211`
- `dagbt/fact_state.py`：`e55b9535d2c55ea87be3de59f4c5e1123e0eac06dc7e672827ba466e9c94c91e`
- `tests/test_v4_handoff_executability_review.py`：`6b349c4e6aba48bbbd2027a7597233a58514ae74677e8d0a01a7c3794b22ed42`

这些测试验证执行边界与状态保存，不证明模型语义判断正确，也不证明现有失败案例会恢复成功。根代理可据此运行一次完整 suite；本报告不扩大部署/运行授权。
