# 实验日志证据备忘

本文件由 build_experiment_evidence.py 读取两个下载包生成。未调用模型服务、未修改实验代码；完整精确值及逐题配对清单见同目录 JSON。

## 口径

权威 outcomes 493 条；summary/current 490/490 条，滞后 3 条成功。predictions 377 + failures 348 = 725 次去重 executor 调用。

| 方法 | 已处理 | 成功 | 答对 | 答错（成功输出） | 执行失败 | 成功样本正确率 |
|---|---:|---:|---:|---:|---:|---:|
| dense | 99 | 99 | 65 | 34 | 0 | 65.66% |
| dense_rerank | 99 | 99 | 66 | 33 | 0 | 66.67% |
| activation | 99 | 61 | 36 | 25 | 38 | 59.02% |
| context_marginal | 98 | 57 | 31 | 26 | 41 | 54.39% |
| activation_fixed_pool | 98 | 61 | 34 | 27 | 37 | 55.74% |

## 与 dense 的同题共同成功配对

rescue＝dense 错/方法对；harm＝dense 对/方法错。分母各不相同，不是全部任务正确率。

| 方法 | 共同成功 | dense 对 | 方法对 | rescue | harm | 净变化（百分点） |
|---|---:|---:|---:|---:|---:|---:|
| dense_rerank | 99 | 65 | 66 | 2 | 1 | +1.01 |
| activation | 61 | 41 | 36 | 5 | 10 | -8.20 |
| context_marginal | 57 | 35 | 31 | 3 | 7 | -7.02 |
| activation_fixed_pool | 61 | 40 | 34 | 7 | 13 | -9.84 |

五方法全都成功的共同题数：44；五方法都有结果的共同题数：98。

## 失败与重试

最终失败类型：{'HTTP_500': 112, 'TimeoutError': 4}；阶段：{'dependency_search': 83, 'selection': 33}。所有失败都未调用生成器。

116 个任务的三次尝试停在相同 ANN/scored_sets 计数；232 次重试都只剩一次 reranker 逻辑调用。重试恢复 0 个任务。

HTTP500 已拆到单个集合文档仍失败，不意味着单条 memory 失败；日志不足以确认超长/OOM。

| attempt | 失败数 | HTTP500 | Timeout | executor 小时 |
|---|---:|---:|---:|---:|
| 1 | 116 | 112 | 4 | 5.711 |
| 2 | 116 | 112 | 4 | 0.949 |
| 3 | 116 | 112 | 4 | 0.948 |

## 成本与缓存

全 attempts 执行 18.207 小时，其中失败 7.608 小时（41.79%）。仅累加 outcomes 会得到 11.547 小时，遗漏前期失败尝试。

后续重试执行 1.897 小时；按配置推算任务退避 2.417 小时（非等待事件直接计时）。

| 方法 | 全尝试小时 | 成功任务中位秒 | 首次尝试 persistent hits | 首次尝试 memory embedding 调用 |
|---|---:|---:|---:|---:|
| dense | 0.694 | 25.11 | 0 | 99 |
| dense_rerank | 0.257 | 9.61 | 24 | 0 |
| activation | 9.765 | 369.40 | 1985 | 0 |
| context_marginal | 4.531 | 140.52 | 17784 | 0 |
| activation_fixed_pool | 2.960 | 73.32 | 27534 | 0 |

后执行方法大量复用缓存，dense 独自承担 memory embedding，以上原始时延不是算法固有速度排序。阶段成本不得再次加到 task totals。

## 版本与模型

数据：PersonaMem-v1 / 32k / 589 题，revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`。本地原始问题文件 SHA256 与运行 manifest 完全一致。

运行 source package hash：`3a55adcae46c4bd7a1231b55736c8d381f2eac0a8ef57e5470a94c4dd6757b0c`。

审计本地 HEAD：`39efab3dd547c522c22e3739d03e9b1904661567`，dirty=True；本地 source package hash：`3a55adcae46c4bd7a1231b55736c8d381f2eac0a8ef57e5470a94c4dd6757b0c`；与运行一致=True。

源码身份是指定目录内路径与文件字节的聚合 SHA256（包括未跟踪源文件），不是 Git commit。不能把当前本地 HEAD 单独当作服务器运行版本。本次实际聚合哈希匹配，支持用本地源码解释运行机制；该匹配不证明远端模型权重身份。

模型安全字段：`{"embedding": {"model": "qwen3-embedding-8b", "backend": "remote", "query_instruction": "Instruct: Retrieve past personal interactions that help answer the current request\nQuery: "}, "generator": {"model": "deepseek-v4-flash", "max_tokens": 512, "temperature": 0.0, "context_token_budget": 8192}, "reranker": {"model": "", "score_space": "unit_interval", "score_contract": "pointwise"}}`。

Configured generator is deepseek-v4-flash; INT8/284B/checkpoint/thinking-mode not established by archive. Reranker model field is empty; its actual server model is not pinned by this field. No endpoint URLs or credentials exported.

## 三个详细 case 的复算

| task 前缀 | activation 条数 | selection 比较 | 不可行/不完整 | 最终分 | 末轮最大边际 |
|---|---:|---:|---:|---:|---:|
| 3b1003e23012 | 192 | 117 | 0/0 | 0.9997326174 | -0.0008573748 |
| dd67463ac537 | 250 | 83 | 0/0 | 0.9928785717 | -0.0080676207 |
| 55de70ff2877 | 160 | 111 | 0/0 | 0.9992445943 | -0.0005090161 |

公式误差为浮点重算精度范围内的零，同集合评分一致；末轮均严格负边际。证据支持代理评分偏好问题，不支持把这些 case 归因于预算过滤或简单改成 logit 即可解决。

## 解释边界

- Snapshot is non-atomic; summary/current lag authoritative outcomes by three success tasks.
- Only four personas are covered. Method-by-question units within a question are correlated; unequal failure missingness prevents unqualified successful-accuracy comparisons.
- Reported execution costs exclude task-level waits and service probes unless explicitly marked; outcome costs retain latest attempt only. Logical token estimates are not billed tokens or per-request input size.
- Paired tests are descriptive/exploratory, conditional on both succeeding, and unadjusted for multiple comparisons.
- Existing logs do not preserve exact failed request body, actual tokenization or server traceback; singleton 500 does not establish OOM or token-limit cause.
- Monotonic logit transform preserves selection marginal sign and argmax for a fixed archive. High scores do not imply correctness probabilities.
