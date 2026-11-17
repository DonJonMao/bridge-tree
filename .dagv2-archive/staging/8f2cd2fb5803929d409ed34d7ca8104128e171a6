# R10 首题独立控制流复核

复核源码：`b160f3ad449796a714c3d45df232b29032262dce`（release tree）。

运行：`/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r10`。
方法：`dagbt_residual_memory_v2`；首题哈希：
`7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0`。
证据为该题 `attempt-001/result.json`、`fusion_events.jsonl`、发布行及对应冻结源码。
本报告保存已经完成的复核结果，没有重新运行实验。

## 结论

这是容量拒绝后无可执行动作的退出，不是控制器把必需的 pending 依赖误当成可以消除。
最终状态为 `unresolved_or_exhausted`，LLM 19/24、ANN 3/36、JSON repairs 1/6。
`recent_changes` 有有效的 version 3 绑定，但该任务仍有 37 条未读窗口义务；
failed slots、failed-batch reviews、evidence obligations 和非空 slot unresolved 均为空。
有效绑定存在不等于其全部必需来源审查已经完成。

## 实际控制链

| 事件序号 | 观察与控制行为 |
| --- | --- |
| 621 | `recent_changes` 抛出 `InputOverflow: Local sources/parents/counters exceed real wire capacity`。`ResidualControl.run` 的异常分支将该动作 identity 加入 `exhausted`。 |
| 651 | 第一个 `semantic_compose` 来源窗口完成，4 个 valid rows、无 failed slots，input 11761 tokens。 |
| 665 | 第二个 `semantic_compose` 来源窗口完成，4 个 valid rows、无 failed slots，input 11298 tokens。 |
| 666 | `active_demands` 仅剩 `recent_changes`；该 identity 已 exhausted，没有可执行动作。 |
| 667 | 发布失败状态 `unresolved_or_exhausted`，没有运行 audit 或发布成功答案。 |

651、665 属于**同一次 Reader.read 的两个来源窗口**，identity 都是
`3555be80035ca5856c84405adc342db2a8df63db08851fc02dc26ebf5ccfa02a`。
它们不是控制器重复调度形成的 retry loop。

重算 `recent_changes` 控制 identity 得到：
`5b8943dbe96afa4f51577aada0b075efeb3f935c716544a291e07c33d18d3ac5`，
与全部 37 条 unread obligations 的 identity 完全相同。
该 identity 包含任务/query/program/父绑定版本，不包含自身 Reader 材料状态。

## 独立离线状态复核

使用真实 `FactState.restore` 和 `ResidualControl` 方法恢复并检查保存状态，未调用模型：

- `possible_outputs.status = determined`，但 `active = [recent_changes]`。
- `task_projection(recent_changes) = None`，没有符号短路消除该义务。
- 终端依赖为 `attended_events`、`music_preferences`、`recent_changes`、`response`。
- 四个依赖都有 valid 值；当前版本及值摘要与终端 `binding_dependencies` 完全匹配。
- `pending_used_dependencies = [recent_changes]`。
- `semantic_inputs_current() = false`。因此未进入 audit 是依赖完整性门槛的正确行为。

相关冻结源码：`residual_control.py:211` 检查语义输入当前性，`:315` 保留 pending 的
active demand，`:662` 跳过 exhausted identity，`:714` 记录异常动作耗尽，`:715`
处理无动作退出。

## 37 条未读义务不能直接清除

未读 alias 为 `s106..s142`。两个终端窗口实际仅覆盖其中 `s106..s111`，即 **6/37**；
其余 31 段未出现在终端请求中。全部 37 段虽曾在其他历史任务的窗口出现，但不同变量的
历史审查不能自动替代 `recent_changes` 的任务审查。不能依据已有有效摘要、其他任务读过
原文或终端格式合法，直接清空这些义务。

本次不建议修改控制器。当前修复方向由 root/reader 另行处理：在保留真实输入限制、
双份输出预留及全部来源要求的前提下，检查 whole-review forecast/实际修复请求中的
无损重复表示。若将来允许容量恢复，应绑定实际材料或容量条件变化，并防止无变化重试；
不能通过无条件取消 exhausted、丢弃未读原文或绕过 pending 获得成功状态。

## 复核边界

- `network_requests: 0`；离线方法复核设置了网络访问拒绝钩子。
- `labels_read: false`；没有打开评价标签，离线方法复核拒绝标签文件访问。
- 未生成新答案、未评分、未修改源码或运行结果。本次仅写入本报告。
- 本报告不证明容量修复后能够完成，也不证明准确率提升或发布验收通过。
