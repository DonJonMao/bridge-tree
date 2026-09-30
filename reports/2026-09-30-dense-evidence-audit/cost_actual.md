# Dense / Evidence Bridge：真实同题成本与上下文审计

本报告读取 2026-09-30 v2 导出包的 `run/outcomes/*.json` 权威当前结果，并关联 `candidate_pool` 和 `visible_memories`。不累计 modules 中的 live 与 snapshot 事件，不把早期失败重试与当前 outcome 混算。没有调用模型、修改实验代码或远程运行。对应明细与复现脚本分别为 `cost_actual.json` 和 `cost_actual.py`。

快照包含 dense 178 个成功结果；Evidence Bridge 146 成功、31 失败。本报告的主要比较只取两边都成功的同题集合：146 对；其中 Evidence Bridge 为 `normal` 的 73 对。该快照比用户此前粘贴的 72 道 normal 题多 1 道，两方法均未答对新增题，故答对数仍是 dense 55、Evidence Bridge 52。

## 主要结论

1. **dense 确实把更多原始记忆交给最终 reader，但成本并不更大。** normal 同题每题平均 dense 为 12 条 / 4603.6 估算输入 tokens，Evidence Bridge 为 3.03 条 / 1506.3 tokens。两者 reader 输入预算同为 8192。Evidence Bridge 删去原文不是预算迫使：这 73 题中，把两者选集取并集后，完整 reader 输入全部仍能容纳，最多 5832 tokens。
2. **最大的过滤发生在 mapping 到 eligible 的关口。** normal 组 dense 的 876 条记忆全部被 Evidence Bridge 召回、全部完成映射流程；其中只有 208 条获得有效 assessment 并进入 eligible，最终保留 194 条。总共被丢弃的 682 条中，668 条在 mapping→eligible 阶段失去资格，14 条是 eligible 后未选。即 97.95% 的 dense 原选集丢弃发生在映射阶段。这个数字不意味着 668 条全部有用或被误删，但明确指出应优先检查语义过滤门槛。
3. **Evidence Bridge 的端到端工作量高很多。** normal 同题平均执行约 775.6 秒，dense 24.9 秒，约 31.2 倍；其中还没有向 Evidence Bridge 收取该题公共记忆库首次 embedding 成本。每题 Evidence Bridge 额外平均 20.60 次证据 LLM 调用、34.86 次检索、346.68 个逻辑评分集合、186.30 次 reranker 传输尝试。其证据 LLM 服务返回的 usage 平均为 99,736 输入 / 15,121 输出 tokens，尚未计最终 reader。
4. **normal 是执行协议完整，不是语义正确或信息完整。** 73 个 normal 成功任务中 10 个给 reader 的记忆集合为空，reader 仍看到问题与选项；这 10 题 dense 答对 7，Evidence Bridge 答对 6。不能把空记忆答对解释为新增检索有收益。

## 同题准确率与信息量

| 指标 | 全部共同成功：146 对 | normal：73 对 |
|---|---:|---:|
| dense 答对 | 100/146，68.49% | 55/73，75.34% |
| Evidence Bridge 答对 | 93/146，63.70% | 52/73，71.23% |
| dense 平均选中记忆数 | 12.00 | 12.00 |
| Evidence Bridge 平均选中记忆数 | 4.28 | 3.03 |
| dense 平均 reader 估算输入 tokens | 4643.4 | 4603.6 |
| Evidence Bridge 平均 reader 估算输入 tokens | 2000.8 | 1506.3 |
| Evidence Bridge 平均保留 dense 记忆数 | 3.28 | 2.66 |
| dense 原选集保留比例 | 479/1752，27.34% | 194/876，22.15% |
| Evidence Bridge 平均新增 dense 之外的记忆数 | 1.00 | 0.37 |
| Evidence Bridge 最终记忆中新增来源的合并比例 | 146/625，23.36% | 27/221，12.22% |
| 两方法选集并集能放入 reader | 144/146，98.63% | 73/73，100% |
| 并集可容纳但仍丢弃 dense 记忆 | 143/146 | 73/73 |
| 并集 reader 平均估算 tokens | 5035.9 | 4741.4 |
| 并集 reader 最大估算 tokens | 9274 | 5832 |

“新增比例”使用合并计数分母，不与每题比例均值混用。normal 最终选集 0–10 条，全体共同成功为 0–19 条。dense 在这些同题集合均为完整 top12，没有触发 reader 容量排除。

并集预算并非把两个输入 token 数相加：使用导出包原始 `Memory.text`、时间顺序、source metadata，配合本地 `questions_32k.csv` 的问题与选项，调用现有 `build_context_plan` 重建一次完整消息。CSV SHA256 与导出 run manifest 完全一致；逐题重建 dense 和 Evidence Bridge 原选集后，估算 tokens 均与 outcome 记录完全一致，再按同一过程计算并集。该统计证明并集可输入，**未运行 reader，也不证明并集一定更准确**。

## 按最终记忆数量分组

| 集合 | Evidence Bridge 记忆数量 | 同题数 | dense 答对 | Evidence Bridge 答对 |
|---|---|---:|---:|---:|
| normal | 0 | 10 | 7，70.00% | 6，60.00% |
| normal | 1–3 | 37 | 28，75.68% | 27，72.97% |
| normal | 4+ | 26 | 20，76.92% | 19，73.08% |
| 全部共同成功 | 0 | 14 | 9，64.29% | 8，57.14% |
| 全部共同成功 | 1–3 | 61 | 44，72.13% | 40，65.57% |
| 全部共同成功 | 4+ | 71 | 47，66.20% | 45，63.38% |

这些组是方法输出后的分组，不能用组间准确率直接估计“增加一条记忆”的因果作用。

## 真实增量成本

| 每题平均指标 | dense：normal 73 对 | Evidence Bridge：normal 73 对 | Evidence Bridge：全部共同成功 146 对 |
|---|---:|---:|---:|
| reader 调用 | 1 | 1 | 1 |
| 额外证据 LLM 调用 | 0 | 20.60 | 21.12 |
| 检索次数 | 1 | 34.86 | 34.90 |
| 逻辑 scored sets | 0 | 346.68 | 357.09 |
| reranker 实际样本尝试 | 0 | 245.08 | 255.05 |
| reranker 传输尝试 | 0 | 186.30 | 193.97 |
| reranker 逻辑输入 tokens 估算 | 0 | 477821 | 489511 |
| 额外证据 LLM 输入 tokens 估算 | 0 | 115253 | 122569 |
| 额外证据 LLM 输出 tokens 估算 | 0 | 19558 | 21488 |
| 额外证据 LLM 服务报告输入 usage | 0 | 99736 | 105730 |
| 额外证据 LLM 服务报告输出 usage | 0 | 15121 | 16615 |
| 额外证据 LLM 耗时，秒 | 0 | 443.0 | 484.2 |
| reranker 耗时，秒 | 0 | 298.8 | 312.1 |
| 总任务执行耗时，秒 | 24.9 | 775.6 | 830.9 |

全部共同成功的 dense 平均总执行耗时为 25.0 秒。以上是当前 outcome 的执行成本，不包含其他方法、不包含历史失败尝试，也不是完整实验完成时的总成本。物理 reranker transport 统计来自每个 scorer 的起止差值；这些成功配对中 failed batch 和 split events 都为 0，故传输次数与 batch request 次数相同。逻辑 scored sets 包含 cache 命中，不能当成 HTTP 次数或真实付费 token。

证据 LLM usage 来源为 `candidate_pool/<task_id>.json → evidence_selection.requests[].response_metadata.usage`：全部共同成功的 3084 次逻辑调用均有服务 usage；normal 的 1504 次均有。服务报告总 usage 分别为 17,862,407 和 8,384,528 tokens，只统计证据规划/映射/选择，未计最终 reader。不同模型价格、缓存计价、机器资源费未知，因此不换算货币成本。服务 usage 与本地估算口径不同，也不将其相除声称精确“token 成本倍数”。

## 成本记录缺陷与缓存归因

**顶层调用漏计在真实日志中已确认。** 全部 177 个 Evidence Bridge 权威 outcome 的 `costs.evidence_calls` 都是 0，而 `costs.evidence_reasoning.evidence_llm_calls` 均大于 0。原因是 `_CountingServiceProxy` 只登记旧 `complete_messages`，没有登记 v2 使用的 `complete_evidence_messages`。本报告使用 selector 自己维护的后者计数，并核对 requests 与 usage。后续分析不能使用顶层 0 当真实调用数。这个问题影响计费观测，不直接影响选集或答案。

公共记忆库 embedding 也有方法顺序归因：146 对中 dense 的缓存命中为 0/146，Evidence Bridge 为 146/146。normal 中 dense 每题首次编码平均 85.04 条全库记忆，Evidence Bridge 为 0；完整共同成功中 dense 平均 85.18 条。任务顺序固定 dense→activation→Evidence Bridge，缓存键不含 method。因此 dense 的 24.9 秒已经包括公共首次 embedding，Evidence Bridge 的 775.6 秒不含这份成本。Evidence Bridge 还从前一方法的评分持久缓存受益：normal 平均约 101.6 个 persistent-cache 命中。以上观测非独立冷启动公平计费，但这两种归因都不支持“dense 因成本更大才更好”。

## 结论边界

真实日志足以确认 **dense 最终读取的信息量更大，Evidence Bridge 实际计算量更大，差距主要发生在完整映射中的语义资格筛选，且 normal 的原文删除并非 reader 容量所迫**。它还不能单独证明哪条被删信息具有因果贡献，或扩大选集会净提高多少准确率。下一步应对差异题查看被判无关的原始信息，再冻结同题集合，以 original reader 对 dense 集合、Evidence 集合、两者并集进行对照；不能根据 gold 临时改选集再将结果当正常方法收益。
