# R20 第 4 题 Reader / terminal 独立结构诊断

冻结源码：`6c046374008ce2e45f817d6bc9876b3ab927ab18`。只读已结束的 canonical 结果、实际请求与事件。未读 gold、评分文件或进行准确率判断；本报告不导出题目、选项、答案文本。

最终 `unresolved_or_exhausted`，audit_complete=false。4 个 history batches 均 complete；实际 semantic_compose 2 次、audit_joint 0 次。LLM 11/24、JSON 修复 4/6、ANN 4/36，均还有预算。没有记录 InputOverflow、handoff capacity rejection 或 tokenizer 失败。

## 实际 terminal 链

- Calls 3–6：四个独立 history 变量完成，scope/hash/引用均有保存证据。
- Call 7：18 个可见来源；模型给 response 一条 support，值与一个合法公共选项精确相同，同时附 1 条 unresolved；顶层 semantic_answer 与 final_prediction 为 null。batch.complete=true 只说明批次评估执行完整，并不说明没有未解决义务。
- Call 8：执行 terminal-only repair，模型返回 slots=[]，semantic_answer 精确等于 expected_value，final_prediction 为合法且匹配该选项的标签。该格式/一致性修复实际成功，但没有权限删除 Call 7 留下的证据义务。
- Call 9：response 进入新的 semantic_compose 批次时，本批 runtime frozen 集初始为空。模型复用 Call 7 的旧 known route ID，输出 unknown/null，并声称解决原义务；复用旧 ID 本身不是从 Call 7 继承的同批冻结违规。该 unknown 行在 Call 9 本批规范化接受后才被加入本批 frozen，因此后续 Calls 10、11 受到冻结约束。返回源集合仅 16 个，原义务覆盖 18 个；新未知/失败材料又留下同描述 hash 的 16-source 义务。
- Calls 10、11：scoped repair 继续重述相同 unknown/null observation，声称解决两个义务；运行期拒绝普通冻结行重述。两次实际 schema 都允许此形状，离线 schema 校验均通过，故不能将本题解释为“模型违反 schema 的 not.enum”；该错误属于 schema 无法完整表达的运行期语义/冻结约束。
- 最终 response 仍 pending，保留 18-source 与 16-source 两个义务以及 18-source 失败批次；未执行真实 audit。

所有 9 个 Reader/terminal 请求 finish_reason 为 stop，部署 token count 与服务 usage matched。5 个 terminal/repair 请求包含实际 shared_history_texts；没有 shared_review_texts，因此不能把新 review codec 的 token 变大直接认定为本题原因。

原 unresolved 是否点名建立该个性化回答仍必要的具体缺失条件，需要单独语义复核。此报告仅把保存协议、模型输出结构与终态链接起来，不自动删除该义务、不放宽覆盖/冻结 guard，也不宣称理论已经被证伪。

## 请求表

| Call | 操作 | Task | 来源数 | Input tokens | Schema |
| ---: | --- | --- | ---: | ---: | --- |
| 3 | joint_read | past_interests | 48 | 7315 | pass |
| 4 | joint_read | emotional_needs | 48 | 7314 | pass |
| 5 | joint_read | constraints | 48 | 7330 | pass |
| 6 | joint_read | life_changes | 48 | 7321 | pass |
| 7 | semantic_compose | response | 18 | 8631 | pass |
| 8 | semantic_compose_repair | response | 18 | 7135 | pass |
| 9 | semantic_compose | response | 18 | 9552 | pass |
| 10 | semantic_compose_repair | response | 18 | 7934 | pass |
| 11 | semantic_compose_repair | response | 18 | 7962 | pass |

结构 JSON SHA-256：`48ba295106c73168bd0ebfcf370e34fb9e39c5dfbadfa68121dcc5fde727f8ad`。
公共选项/terminal 一致性 JSON SHA-256：`25436261100f9da476bafdf7ac1064a5f3bc9ba5698b3b5036fc1fdd0c047677`。

修订说明：本版纠正 Call 9 与 Calls 10/11 的冻结作用域边界。保留原版历史，不改变调用次序、coverage、终态或零服务/容量错误结论。原版 SHA-256：`4fe6918044fc88edf985be1e66897816f106221785a55b3af92997228ce0dcd6`。
