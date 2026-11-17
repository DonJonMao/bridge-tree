# R15 固定 14 题结构验证汇总

冻结源码：`50d1ba0b2edb623384e51ac42ea12b36e5b69229`。自然结束：`complete_with_failures`。报告生成时 release tracked files clean。

本报告未读取标签、未导出题目/选项/答案文本、未评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。

| 方法 | 已发布题数 | 状态 |
| --- | ---: | --- |
| original | 14 | {"ok": 14} |
| dagbt_residual_memory_v2 | 14 | {"unresolved_or_exhausted": 9, "audit_incomplete": 1, "ok": 3, "execution_failed": 1} |

DAGBT 逐题记录（编号从 1 开始）：

| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ok | 11 | 2 | 6 | 1 | 1 | 无 |
| 2 | unresolved_or_exhausted | 13 | 5 | 7 | 0 | 0 | obligation_resolution_conditions; InputOverflow |
| 3 | unresolved_or_exhausted | 11 | 2 | 7 | 1 | 0 | InputOverflow |
| 4 | unresolved_or_exhausted | 15 | 4 | 9 | 1 | 0 | InputOverflow |
| 5 | unresolved_or_exhausted | 20 | 6 | 8 | 3 | 2 | Required failed observation still unavailable; mandatory_downstream_context_capacity; InputOverflow |
| 6 | unresolved_or_exhausted | 17 | 2 | 11 | 2 | 1 | Audit must return an explicit verdict; mandatory_downstream_context_capacity; InputOverflow |
| 7 | ok | 7 | 0 | 4 | 1 | 1 | 无 |
| 8 | ok | 14 | 3 | 8 | 1 | 1 | 无 |
| 9 | audit_incomplete | 24 | 2 | 7 | 12 | 2 | llm_call_reservation; BudgetExceeded |
| 10 | unresolved_or_exhausted | 14 | 4 | 9 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 11 | unresolved_or_exhausted | 19 | 6 | 11 | 1 | 0 | Required failed observation still unavailable; mandatory_downstream_context_capacity; InputOverflow |
| 12 | unresolved_or_exhausted | 22 | 6 | 14 | 1 | 0 | mandatory_downstream_context_capacity; Summary revision cannot supersede revoked, retired or stale routes; InputOverflow |
| 13 | unresolved_or_exhausted | 15 | 6 | 8 | 0 | 0 | mandatory_downstream_context_capacity; InputOverflow |
| 14 | execution_failed | 3 | 2 | 0 | 0 | 0 | PersonaMem requires semantic/text response selection, not symbolic fact certification; Compose requires parents; execution must be retrieval/compose; PersonaMem terminal must compose personal-history evidence into a response selection; ProtocolError |

类别可以重叠，不能将不同类别的题数相加。终端和审计调用可能是同一 identity 的连续窗口，并非独立 controller 重跑。

出现容量相关事件的题号：[2, 3, 4, 5, 6, 10, 11, 12, 13]。

专项证据：第 9 题 12 个 terminal 窗口同一 identity，随后 2 个 audit 窗口完成，第 3 个因预算拒绝；第 12 题修订引用了输入中已经 superseded、且不在 eligible offer 内的旧 route。

第 14 题在 planner 阶段失败，result 无 diagnostics；LLM 3 / JSON 修复 2 从已存 fusion events 恢复，history/terminal/audit 均未开始。三次请求都收到 history→compose 约束，后两次收到准确的前次错误反馈，模型仍连续返回无 history inputs 的单步计划。未据此发现新的校验实现缺陷。
