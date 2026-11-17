# R6 首题 interests 容量诊断

只读分析，未读取标签、调用生成、修改运行源码或原实验输出。精确计数使用生产
`DeploymentTokenCounter`，共 14 次 `/tokenize`。数据文件：`r6_wire_redundancy.json`。

## 已确认的实际容量

16,384 context 减 4,096 输出、256 input margin、8 safety 后，输入上限为 **12,024**。
以下是 `joint_support_capacity_rejected` 前紧邻的两条实际 tokenizer 记录，分别是
mandatory response compose 与其结构化修复预留请求：

| 拒绝序号 | 必需原文 span | base / repair 输入 token | 超出输入上限 |
| --- | ---: | ---: | ---: |
| 349 | 67 | 15300 / 15526 | 3502 |
| 363 | 67 | 15239 / 15465 | 3441 |
| 377 | 67 | 15239 / 15465 | 3441 |
| 405 | 105 | 17665 / 17891 | 5867 |

这不是当前 interests 阅读请求本身超限，而是新 support 的必需下游容量检查失败。

最重要的来源结构：已存在 music_prefs/event_history 的 source 集合并集为 20；
event_history 未解 evidence_obligations 的来源并集为 64，failed_batch_reviews 也为 64；
三者并集恰为 **67**，已覆盖前三次 mandatory 请求中的全部 67 个 span。
interests 的引用从 20 降到 9 后，span 数仍为 67，输入仅下降 61 token。

因此主瓶颈是继承的 event_history 未解决整窗口义务。继续要求 interests 压缩自己的
引用并不能消除这些必需来源。需要 reader/contracts 正确处理 event_history 的显式
修订与失败记录恢复；不得为通过容量检查删去旧原文、反证、作用域或来源路径。

## 重复结构的精确测量

`personal_task_instruction` 的完整历史阶段指令在 user 与 system 中严格重复。
在 5 个实际请求中，仅省略 user 的完全相同副本，保留 system 全文，均精确节省
**474 token**。所有 baseline 再计数均与原运行记录一致。

| 实际调用 | 节点 | 原输入 | 仅去指令副本 | 限定 observation 共享表 | 两项同时 |
| --- | --- | ---: | ---: | ---: | ---: |
| 11 | event_history 修复 | 9109 | 8635 | 8056 | 7582 |
| 12 | event_history 失败恢复 | 11736 | 11262 | 10683 | 10209 |
| 13 | interests 阅读 | 7332 | 6858 | 无可共享重复 | 6858 |
| 14 | interests 修复 | 7666 | 7192 | 无可共享重复 | 7192 |
| 16 | interests 失败恢复 | 11850 | 11376 | 无可共享重复 | 11376 |

event_history 中同一个 draft 出现在 failed.observation、failed.slot.observations、
whole_value_reviews.draft_observations 三处；一个相同 known observation 出现两处。
分析 helper `lossless_wire_probe.py` 只在明确 observation 位置放引用，保留完整 JSON
对象一次，不遍历 typed value，额外计入引用解码指令；精确省 1053 token。
解码与原 payload 完全相等，嵌套 typed literal 中 reference 形状不被解码，候选位置
发生保留引用形状冲突时拒绝压缩。该共享表只是分析原型，**root 已明确暂停集成**。

mandatory 请求还会把已有父值同时放入 grounded_subquestion、supported_parents 和
known_observations；这是 `_payload` 与 grounded() 的静态路径。该计划没有
task_expressions，不能把 supported_task_outputs 算成一个额外的重复大表。
本次没有重构未持久化的 mandatory 完整请求，也没有把阅读请求的节省值直接减到
mandatory 容量上，因此不声称上述编码已经解决 3441–5867 token 的缺口。

## 允许的最小实现方向

root 已授权在 reconcile 中新增独立纯 helper，仅去掉 user 中与 `_system` 实际选择
的 phase/audit 常量严格相同的 personal_task_instruction。必须镜像真实分支：
history_evidence 优先；其余按 audit_instruction 字段是否存在选择 audit 或 selection。
非 personal、自定义不同文本、相同 phase 但实际 system 分支不同均保留字段。
system 指令、内部 canonical payload、原文、反证、route、typed value 都保持不变。

该改动能稳定减轻请求体，但 event_history 未解决闭包仍是本轮主要修复事项。
