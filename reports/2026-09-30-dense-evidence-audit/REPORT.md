# Dense 与 Evidence Bridge：效果、信息与成本审计

> 此文保留导入 v2 日志之前的初步审计。当前实测结论、病例与修法优先级见 [真实日志综合报告](ACTUAL_REPORT.md)。

日期：2026-09-30。审计源码：`16809bd64b6b1edc93e719489cec45ebd19db6f9`。

## 结论及证据边界

当前结果没有证明 Evidence Bridge 优于 dense。用户提供的同题、成功且 `normal` 的 72 对中，dense 为 55/72（76.39%），Evidence Bridge 为 52/72（72.22%），后者净少 3 题（−4.17 个百分点）。两者都对 50 题、都错 15 题，仅 Evidence Bridge 对 2 题、仅 dense 对 5 题。只有 7 题正误不同，且样本尚未跑完、同一 persona 内相关、normal 是按 Evidence Bridge 运行结果事后筛出的子集；不能据此宣称 dense 在总体上稳定优越。

代码可以排除“dense 拥有更大的配置上下文预算”这一解释。两者使用同一最终 reader、同一 8192 估算 token 的完整输入上限。Evidence Bridge 的候选池从相同的 dense 召回开始，额外付出搜索、集合评分与证据推理的开销。现有证据不支持“dense 因花更多总计算而更准”。

最值得优先验证的机制问题是：Evidence Bridge 在最终 reader 前增加需求规划、证据映射和集合筛选，可能丢掉 dense 已经召回的有用历史。`normal` 不能排除这种语义信息损失。候选池更大、原文引用合法、需求覆盖完整，都不等于最终答题效用更高。

本次检查了当前代码、配置、7 道差异题的本地数据、历史诊断报告和用户贴出的 v2 汇总。**本地没有当前 v2 的逐题原始日志**，所以不能确认实际平均上下文长度、真实调用费用，或把当前 5 个 dense 独对案例逐一归因。旧 activation 的日志只能提供历史参照，不能充当 v2 失败链的直接证据。本次未调用模型、未修改运行代码或配置。

## 同一 reader 预算下，两种方法做了什么

| 维度 | dense | Evidence Bridge |
|---|---|---|
| 最终 reader | `deepseek-v4-flash`，temperature=0，输出上限 512 | 相同 |
| 完整 reader 输入上限 | 8192 估算 tokens，包含提示、问题、选项和原文 | 相同 |
| 初始候选 | 原 query 检索最多 12 条 | 先包含同一初始 dense 结果，再扩展 |
| 最终上下文 | 按检索排名逐条尝试加入完整原文，预算可容纳则保留 | 依据需求与证据表选取原始记忆，可删除或替换任意候选 |
| 最终条数 | 最多 12 条，可能因预算减少 | 可多于或少于 12 条，受同一 reader 上限限制 |
| 检索与集合评分 | 1 次检索，无集合 reranker | 总检索预算最多 36 次，最多 512 个逻辑评分集合 |
| 额外证据 LLM | 无 | 最多 24 次逻辑调用，含规划、映射、选择与修复 |
| 最终回答 | 1 次 reader | 1 次 reader |

上表中的 36、512、24 都是配置上限，不是每题实际用量；逻辑评分集合数也不是 HTTP 请求数。Evidence 内部的 16384 输入预算不是 reader 上限。默认配置中的旧 `retrieval.context_size: 5` 不是这里 dense 的实际选集规则。

代码依据：

- [reader 配置](../../configs/default.yaml)：`models.generator`。
- [检索预算](../../configs/chain_full.yaml)与[证据配置](../../configs/evidence_bridge.yaml)。
- [dependency_experiment.py](../../src/bridgetree/dependency_experiment.py)：`_generation_plan_for_ids`、`_baseline_context`、dense/evidence_bridge 执行分支及共同最终 reader 路径。
- [dependency_retrieval.py](../../src/bridgetree/dependency_retrieval.py)：`retrieve_dense` 与 `build_initial_pool`，后者首先 `admit(dense.ids)`。

必须区分“候选池的信息量”和“最终 reader 看到的信息量”。Evidence Bridge 有更大的候选池，但 dense 最后可能保留更多相关原文；是否确实如此，必须用同题 `selected_ids` 和 `costs.generator_input_tokens_estimate` 验证。原文更多也不自动等于有效信息更多。

## 为什么 normal 仍然可能损失关键历史

源码中存在以下合法路径：

1. 某条 dense 候选进入 Evidence Bridge 的候选池。
2. mapper 对这条记忆的所有原文单元返回空 `assessments`，同时给出非空 `irrelevance_reason`。
3. 校验器接受这些判断，并将单元记为已完成映射。
4. selector 的 `candidate_ids` 只从映射产生的 facts 提取；没有任何 fact 的记忆不进入可选范围。
5. 最终 reader 无法看到这条记忆，但任务仍可被标记为 `normal`。

这说明“完整映射”的精确含义是所有单元都得到了合规处理，包括被判断为无关；不是每段有用信息都被正确保留。`normal` 只检查未映射单元和选择输入截断，不验证需求是否完整、无关判断是否正确、覆盖判断是否真实。

依据：[evidence_selection.py](../../src/bridgetree/evidence_selection.py) 的 `_map_rows`（约 670 行）、`payload_for`（约 1008 行）及 `diagnostics`（约 271 行）。

另外，mapper 依赖分段原文与批次，selector 看到的是映射后的 claim 和引用片段。最终 reader 虽然拿到被选中记忆的完整原文，前面被误删的记忆仍无法恢复。

## 最可能影响效用的三处机制

### 1. 提前猜需求，然后冻结需求

planner 只看 query，需求确定后不会随着候选历史被发现而修订；mapper 只能映射到这些需求。若规划漏掉判分需要的历史理由，后续正确执行也可能围绕一个不完整目标工作。

两方法检索都只看 query，选项都只在最终 reader 阶段出现。因此不存在 dense 额外读取选项的优势。区别在于 dense 将相关原文保留下来，reader 看选项后还有机会找出区分信息；Evidence Bridge 在选项出现前就要判断哪些历史足够。

本地差异题支持研究这一风险，但还不能证明实际发生了误删：

| 当前独对方法 | 题目简写 | 判分所需的细节 |
|---|---|---|
| dense | `dbbd6663`，flashcards | 当前在说团体游戏，选项区分过去“不利于深度学习”和“重复无聊”等具体理由 |
| dense | `17273334`，绘画课 | 当前喜欢课堂，同题正确项要求保留过去觉得结构化环境太限制创造力的理由 |
| dense | `2c7661cc`，爱情小说 | 要区分最初就喜欢和后来才喜欢，不能只保留“现在喜欢” |
| dense | `40d94e80`，周末读书推荐 | 推荐依据来自较远的关系、自助类阅读偏好 |
| dense | `aa2c7800` | 本地 query 问烹饪视频脚本，四个选项却讨论写书评与即兴聊书，存在明显题干与选项错位现象，值得另审 |
| Evidence Bridge | `56fb1ba3`，meditation | 长篇暑期辅导叙述中带到 meditation，选项要求历史偏好变化 |
| Evidence Bridge | `8f6defba`，烹饪课 | 是否曾提过喜欢烹饪课的历史回忆 |

来源：[queries.jsonl](../../data/processed/personamem-v1/32k/queries.jsonl)，对应行 86、62、174、125、42、92、68。这里只用 gold 进行离线诊断，不应将其输入在线检索。题干与选项错位尚未追溯到原始数据或转换环节，不将其直接定性为数据处理 bug。Evidence Bridge 也赢了一道含隐含历史目标的题，因此这个风险不是所有案例的统一解释。

### 2. 把“需求覆盖”当作“对 reader 有用”的代理

代码能验证引用原文确实存在，能阻止跨需求引用或把推断伪装成明确事实，却不能验证 claim 是否准确概括原文，或者选中的内容是否足以区分答案。

一个合法但错误的 `covered` 判断还会抑制缺口检索。整个链条可以语法正确、引用合法、没有截断，最终仍然选错信息。原先相关性代理的偏差，并不会仅因换成 LLM 覆盖判断就自动消失。

### 3. 额外搜索与最终选择的联系有限

搜索保存了已经评分的组合以及条件关系，但交给 mapper/selector 的主要是合并后的候选 ID。已测组合的结构与评分不直接约束最终集合。因此，改进搜索调度可以让候选更丰富，却不能保证最终共同保留搜索中发现的有益组合。

这是一种方法设计取舍，不能直接称为当前实现又漏交了某个候选；也不能把更高的旧相关性评分等同于更高答题效用。

## 为什么修了多次仍未超过 dense

前几轮改动解决了不同层面的问题：完整归档、服务与输出兼容、原文引用合法性、预算超限、搜索调度、历史证据选择。它们不是对最终准确率的同一个直接优化过程。

用户提供的 v1/v2 中途快照中，Evidence Bridge 执行成功率从 53/283（18.73%）到 142/173（82.08%），说明可运行性明显改善。但两次不是同一完整样本，不能把这个变化当作受控版本效应；更不能推出“成功运行后的答案一定更准”。

当前 v2 方法没有参数训练，需求、映射、覆盖都还是模型预测。测试通过可以证明实现满足指定契约，不能证明这个契约比 top-12 原文直接交给 reader 更有用。

之前把多个设计改动合到一次完整实验，没有先分别验证扩展检索、映射筛选各自的净收益，导致当前无法从汇总准确率直接定位收益和损害。这是评估证据的缺口；继续叠加机制会让归因更难。

## 成本日志发现的问题

发现并用无网络本地 probe 复现了一处计数漏项：executor 的 `_CountingServiceProxy` 只将旧 `complete_messages` 计入 `evidence_adapter_invocations`，而当前 selector 优先调用 `complete_evidence_messages`。未注册的方法直接透传，导致顶层 `costs.evidence_calls` 可能为 0，尽管实际已经调用证据模型。

当前统计应改读 selector 自身维护的 **`costs.evidence_reasoning.evidence_llm_calls`**，并配合该对象内的输入/输出 token 估计、分操作调用数，以及底层请求 usage/transport 记录。这个缺陷影响成本统计，不改变选集或答案。

另一个成本归因问题是共享 embedding 缓存：任务通常按 dense、activation、Evidence Bridge 的顺序执行，dense 可能先承担整个可见历史的编码，后续方法复用缓存。应将共同预处理单列或摊销，不能简单按方法 elapsed 或 embedding 样本量判断 dense 更昂贵。

最后一次 reader 的输入 token 数也不是整套方法的总 token 数。即使 dense 的最终 reader 原文更长，也不能据此推断 dense 的整体费用更高。当前没有足够日志和计价信息给出真实金额或成本倍数。

依据：[dependency_experiment.py](../../src/bridgetree/dependency_experiment.py) 约 1674、1713、1847 行；[evidence_selection.py](../../src/bridgetree/evidence_selection.py) 约 255、420、443 行。

## 下一步最小诊断与判断标准

先分析已有产物，不改变正在运行的方法：

1. 对同题比较最终原文条数、reader 输入 token、dense 选集在 Evidence Bridge 中的保留比例、新增条目和预算拒绝。
2. 对 5 个 dense 独对和 2 个 Evidence Bridge 独对案例，追踪“dense 选中 → EB 候选 → 规划需求 → 映射事实 → 可选 ID → 最终选集 → reader”。区分未召回、误判无关、selector 删除、预算淘汰与 reader 自身答错。
3. 先核对实际 reader request/context hash；相同请求的答案差异不能归因于选集。历史报告曾记录相同请求仍产生不同答案，temperature=0 也不能当作服务端完全确定的证明。
4. 有明确遗漏证据时，以同一 reader 预算进行加回/替换干预，并复跑原请求作为生成波动对照。单次救回仍不是充分因果证据。

再做最小消融，保持同样 reader、同样预算上限与输入边界：

| 检索候选 | 上下文选择 | 目的 |
|---|---|---|
| dense 候选 | 原文按 query 检索排名入预算 | 现有 baseline |
| dense 候选 | 当前 mapper + evidence selector | 检查语义筛选本身的净收益；固定候选时关闭缺口扩展 |
| EB 扩展候选 | 用同一 query 排名规则后原文入预算 | 检查扩大候选池的价值 |
| EB 扩展候选 | 当前 mapper + evidence selector | 完整方法；拆分组件时固定同一候选池并关闭额外反馈，再单独看在线反馈 |

在已有差异题上开发和定位后，应在尚未用于调试的题目上验证改动。主要结果应报告所有计划任务的正确率和失败率，再补充共同成功、normal 等诊断分组，避免只展示成功筛选后的有利子集。

如果筛选消融退步，优先减少误删而不是加大搜索预算；如果扩大候选池也没有收益，则需要重新评估这批任务是否需要当前复杂搜索。只有找到稳定的收益来源，才值得进一步增加机制复杂度。
