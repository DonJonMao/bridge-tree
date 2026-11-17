# R20 第 1 题 Reader 独立结构诊断

冻结源码：`6c046374008ce2e45f817d6bc9876b3ab927ab18`。仅读取已自然结束的 canonical 结果和实际请求/事件；未读取 gold、评分文件或导出题目、选项、答案文本，未调用服务。

最终状态为 `unresolved_or_exhausted`，audit_complete=false。LLM 11/24、JSON 修复 6/6、ANN 3/36；剩余全局 LLM 预算 13，不能将整题解释为全局 LLM 预算耗尽。实际 semantic_compose 和 audit_joint 请求均为 0，事件 terminal_published 只是失败终态发布，不证明做过模型 terminal/audit。

计划包含 3 个独立 history 子问题（attended_events、music_preferences、cultural_interests）及一个依赖三者的 response。最后 attended_events 与 cultural_interests 仍 pending，music_preferences 已有有效绑定。

## 按实际请求确认的早期协议/覆盖失败

- Call 2：50 个可见来源，返回 1 条 support（引用 3 个来源）和 1 个 unresolved，留下针对原 50 个来源的证据义务。
- Call 3：78 个可见来源，声称解决该义务，但 support 仍只覆盖 3/50 个原来源，缺 47 个。普通 schema 通过；这不代表运行期覆盖条件通过。
- Calls 4、5：实际 repair prompt 明确冻结约束，schema 的 observation.id.not.enum 禁止冻结 ID，同时 reviewed_observation_ids.enum 提供该 ID。两次模型同时引用该 ID 又在 observations 重述同一行，离线校验均在 slots[0].oneOf 失败。修复指令、实际 schema 和冻结 restatement 拒绝一致；本检查未发现这一 repair 契约自相矛盾。
- Calls 3–6 返回 observation 的完整 row hash 一致（slots 的引用/解决字段有差异）。即使去掉普通 restatement，3/50 的原来源覆盖仍不足，因此不能把整题失败单独归因于 frozen ID。
- Call 6：80 个可见来源、已保留的失败批次，模型仍声称解决义务/失败批次但只覆盖 3/50。最终该义务保留 50 个来源，失败批次与 hard unread 都保留 80 个来源；43 是 capacity_unavailable 的前缀组数，不是 unread 来源数。
- 所有 10 个已发送 Reader 请求 finish_reason 均为 stop；10 个请求的部署 token count 与返回 usage 均 matched；均未发生 tokenizer 服务失败。Call 3 fresh cap 为 553，但不能据此宣称发生了截断。

## 后续恢复与最后阻塞

- Call 7（music_preferences）完成。sequence 337 发现未来 response 尚缺 cultural_interests，handoff 标记 executable=false/provisional=true/capacity_fits=false，并 deferred；该早期未来交接没有直接拒绝这一历史支持。
- Calls 8–11（cultural_interests）输出 schema 均通过，支撑来源数依次为 17、7、6、6，值 hash 相同。但分别遇到 response 下游容量拒绝，共 4 次；最后留下来源范围 104 的失败批次。
- sequence 192 的 repair 输入不可装入：input=13039，output reserve=4096，margin=256，加固定 8 后为 17399 > 16384。随后 sequence 280 另记录 attended_events 的真实 wire InputOverflow。这些是容量失败，区别于 HTTP/连接故障。
- 本报告保留实际拒绝与计数证据；下游拒绝来源闭包的独立因果复核由 control agent 负责，未在这里把容量拒绝等同于算法理论缺陷。

## 请求表

| Call | 操作 | Task | 来源数 | Input tokens | Output cap | Schema |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 2 | joint_read | attended_events | 50 | 7342 | 4096 | pass |
| 3 | joint_read | attended_events | 78 | 10078 | 553 | pass |
| 4 | joint_read_repair | attended_events | 78 | 11174 | 4096 | fail |
| 5 | joint_read_repair | attended_events | 78 | 10844 | 4096 | fail |
| 6 | joint_read_repair | attended_events | 80 | 11906 | 4096 | pass |
| 7 | joint_read | music_preferences | 50 | 7367 | 4096 | pass |
| 8 | joint_read | cultural_interests | 50 | 7337 | 4096 | pass |
| 9 | joint_read_repair | cultural_interests | 50 | 7684 | 4096 | pass |
| 10 | joint_read_repair | cultural_interests | 50 | 7689 | 4096 | pass |
| 11 | joint_read_repair | cultural_interests | 104 | 11904 | 4096 | pass |

本题没有实际 shared_review_texts 或 shared_history_texts 请求，因此不能把空集的 codec 检查当成本题在线验证通过。来源身份/请求曝光独立检查已重建 156 个 source identities、追踪 10 次曝光，未发现这些结构检查的异常；不证明语义证据充分或答案正确。

JSON 证据 SHA-256：`3d018bfd92579436c90c0f7c8382a14c83b6db965533237434a471f2e2a3b1a9`。
