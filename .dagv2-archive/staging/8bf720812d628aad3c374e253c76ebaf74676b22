# R11 首题结构诊断（只读取证）

运行已由主代理停止，`live_writer=false`。这是发现具体容量阻断后的人工停止，**不是算法自然终态**。未读取标签，没有新生成或 tokenizer 网络请求。

- 发布 row / attempt result / fusion snapshot：均不存在；不能报告最终作答状态或准确率。
- 最后预算：LLM 22/24（已记录 reasoning response 21），ANN 3，JSON repair 0。
- 历史读取：20 个已完成 batch，全部 complete=true。
- Terminal：semantic_compose/22 已发、尚无 response，停止时在途。Audit：尚未发起。
- 最后 active_demands：past_events、response（event 679）；无最终 FactState，pending_variables 不可确定。

## 已确定的阻断

Event 465：past_events 出现 InputOverflow，错误为 Local sources/parents/counters exceed real wire capacity。上一个成功批次是 event 419。此后 45 条 tokenization 记录构成 15 个前缀的 base / ordinary repair / whole-review forecast 三次精确计数。

所有 ordinary 检查通过，所有 fresh whole-review forecast 被拒。最小 forecast 输入 8478，加 4096 输出、4096 未知草稿空间、256 输入 margin 和 8 固定 margin 得 16934，比 16384 超出 550。最大总量 17818。没有 actual-repair-input-unavailable 事件。

| 事件序列 | Base | Ordinary repair | Whole forecast | Ordinary total | Forecast total |
|---|---:|---:|---:|---:|---:|
| 420,421,422 | 8741 | 8830 | 9362 | 13190 | 17818 |
| 423,424,425 | 8195 | 8284 | 8792 | 12644 | 17248 |
| 426,427,428 | 7982 | 8071 | 8570 | 12431 | 17026 |
| 429,430,431 | 7896 | 7985 | 8478 | 12345 | 16934 |
| 432,433,434 | 7920 | 8009 | 8505 | 12369 | 16961 |
| 435,436,437 | 8052 | 8141 | 8643 | 12501 | 17099 |
| 438,439,440 | 8129 | 8218 | 8723 | 12578 | 17179 |
| 441,442,443 | 8195 | 8284 | 8792 | 12644 | 17248 |
| 444,445,446 | 8343 | 8432 | 8946 | 12792 | 17402 |
| 447,448,449 | 8410 | 8499 | 9016 | 12859 | 17472 |
| 450,451,452 | 8482 | 8571 | 9091 | 12931 | 17547 |
| 453,454,455 | 8504 | 8593 | 9116 | 12953 | 17572 |
| 456,457,458 | 8569 | 8658 | 9184 | 13018 | 17640 |
| 459,460,461 | 8651 | 8740 | 9269 | 13100 | 17725 |
| 462,463,464 | 8741 | 8830 | 9362 | 13190 | 17818 |

全部原 wire SHA256 见同名 JSON。R10 最小前缀恢复准入只对其保存状态成立，不能据此认定 R11 不同规划及累积状态也能通过。当前证据支持进一步审查资源分配，不能将人工中断写成模型作答失败。
