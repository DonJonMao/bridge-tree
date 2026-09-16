# 2025–2026 正式顶会论文：机制证据与 BridgeTree 问题映射

核验日期：2026-09-15。范围：2025–2026 年已正式发表的机制相关顶会论文；本次筛出的四篇均为 2025 年正式论文。会议身份以 ICLR/NeurIPS 官方节目页、PMLR、ACL Anthology 为准；方法细节交叉阅读作者论文正文与作者代码说明。没有把 arXiv 年份、作者自称或代码 README 单独当成正式录用证据。

本备忘对应报告的“相关研究与改进依据”，**不是同数据集排行榜**。四篇原论文实验均不是当前 PersonaMem-v1 的 `questions_32k.csv` / `shared_contexts_32k.jsonl`、589 题协议。其 LoCoMo、DialSim、GVD 或开放域 QA 分数不可与我们的 PersonaMem 准确率直接相减。RF-Mem 等同数据集核验另见 `research_baselines.md`。

## 结论先行

当前最有针对性的外部依据是 Sufficient Context：把“相关性分数高”与“证据足够回答目标任务”分开。HippoRAG 2 则说明结构化检索应保留原始 passage 与 dense 信息通路，而不应以结构扩展本身作为收益证据。A-Mem、MemoryOS 提供免参数训练的记忆表示、关联和分层维护方案，但不能据其原论文结果宣称在当前 PersonaMem split 已优于 dense。

| 当前审计问题 | 文献提供的具体机制 | 推荐的小范围检验 | 不能据此断言 |
|---|---|---|---|
| 音乐案：软件制作事实已在候选库，却因负集合边际被排除 | Sufficient Context 区分证据充分性与生成正确性 | 离线标注初始池/最终集合的事实充分性；冻结上下文做补证据消融 | reranker 高分等于答案正确概率；加一条事实必然纠错 |
| 搜索耗尽 ANN，新增独立记忆少；扩展后仍选择很短上下文 | HippoRAG 2 保留 passage 节点、dense 种子并融合关联检索 | 固定候选池，对比纯 bundle 选择与 dense 锚点保留 | PPR 或更大的图必然改善 PersonaMem |
| 当前话语重复项或只有主题相似的项挤掉历史事实 | Sufficient Context 的“足以回答”视角；HippoRAG 2 的原文上下文保留 | 严格区分当前 query 与历史证据，记录重复项与有效新增事实覆盖 | 上述论文专门研究/已经解决了我们这类 query 重复 bug |
| 原始长对话中的个人事实不够显式、关联难找 | A-Mem 的原文＋时间戳＋关键词/标签/上下文说明＋链接 | 只改记忆表示，保留原文与来源；同预算、同生成器验证 | LLM 生成的链接就是因果依赖或真实证据 |
| 历史习惯、当前偏好、近期变化容易混淆 | MemoryOS 分层存储、用户事实/traits、动态更新 | 顺序处理历史、保留来源时间与有效性，分开稳定画像和事件事实 | 访问热度/recency 就等于事实有效期或偏好更新规则 |

所有上表的 BridgeTree 改动均是本报告提出的待测假设，不是这些论文已经在本项目上验证的结论。

## 1. Sufficient Context：先诊断证据够不够，再诊断模型会不会用

**正式论文**：Hailey Joren et al., *Sufficient Context: A New Lens on Retrieval Augmented Generation Systems*, ICLR 2025，主会 Poster。

### 官方身份与可复查材料

- 官方会议页：https://iclr.cc/virtual/2025/poster/30092
- 官方会议页链接的 OpenReview：https://openreview.net/forum?id=Jjr2Odj8DJ
- 作者论文全文（本次阅读 v3，2025-04-23）：https://arxiv.org/html/2411.06037v3
- 作者代码与提示：https://github.com/hljoren/sufficientcontext
- 作者机构页面：https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems/

注意：预印本首次上传是 2024-11-09，但正式会议年份是 2025，因此满足本次时间范围。OpenReview ID 采用官方会议页直接链接，避免把正文参考文献中的另一篇文章 ID 误当本篇。

### 正文证据

论文 §3 将问题区分为：给出的上下文是否包含足以回答 query 的信息，而不是是否“提到了同一主题/实体”，也不是生成器这一次是否答对。作者构造了含高度相关但不充分证据的困难样本，用 1-shot Gemini 1.5 Pro 提示进行 sufficiency 分类；在 115 个人工标注实例上的报告准确率为 93%。这项数字仅是该 autorater 在该样本上的验证，不是 PersonaMem 正确率，也不代表我们换用 DeepSeek 后会有相同判别质量。

论文 §4 按 context sufficiency 分层分析生成结果：充分证据仍可能被模型误用；不充分证据也可能依靠模型已有知识得到正确回答。因此，检索充分性与最终正确性必须分别观测。

原论文主要分析 HotpotQA、MuSiQue-Ans、FreshQA；autorater 标注集还从 PopQA、Natural Questions、EntityQuestions 等取样。**不是 PersonaMem。**

### 无需训练的边界

- 可直接借鉴、无需新参数训练：§3 的提示式 sufficiency autorater，以及离线错误分层分析。仍需推理调用和人工抽检。
- 不应称为严格免训练：§5.1 的 selective generation 将 sufficiency label 与模型自评置信度输入 logistic regression；正文明确进行 100 次随机超参数搜索。
- §5.2/附录还研究 Mistral 的 LoRA 微调。因此不能把整篇论文标成“全流程无需训练”。

### 对当前日志的意义

音乐案中，加入 m00027 的集合分数从 0.99287857 降到 0.97404264，选择器据此拒绝明确的“使用软件制作音乐”事实。这已经证明“事实被集合目标排除”的执行机制，但尚未证明 reranker 为何这样打分。Sufficient Context 支持增加独立的证据充分性审计，而不是直接把 relevance marginal 重命名成 sufficiency。

PersonaMem 的 query 经常是陈述式用户发言，而非普通问答题。移植 autorater 时要依据实际个性化任务说明定义“需要什么历史信息”；不能把作者的开放域 QA 提示不加验证直接照搬。可以离线人工标注“事实是否存在、是否属于当前用户、是否仍有效、最终集合是否覆盖”，并保留原文索引。若在线实验协议不允许看到选项/金标准，则 sufficiency 检查也不能借机把答案选项或正确标签泄漏给检索与选择。

**最小实验**：冻结 query、记忆库、生成器与排序，对原最终集合、补入独立个人事实后的集合分别做配对生成；同时离线标注充分性。多次生成或复用相同上下文的生成结果，避免把生成波动归因为模块增益。对强制多选的 PersonaMem，不能通过增加拒答偷偷改变评测任务，再把 selective accuracy 与原准确率混报。

## 2. HippoRAG 2：结构关联不能牺牲原始上下文和基础事实能力

**正式论文**：Bernal Jiménez Gutiérrez et al., *From RAG to Memory: Non-Parametric Continual Learning for Large Language Models*, ICML 2025，PMLR 267:21497–21515。HippoRAG 2 是方法名，不能把它误作正式论文标题。

### 官方身份与可复查材料

- 官方论文页：https://proceedings.mlr.press/v267/gutierrez25a.html
- 官方 PDF：https://raw.githubusercontent.com/mlresearch/v267/main/assets/gutierrez25a/gutierrez25a.pdf
- 作者正文（本次阅读 v2，2025-06-19）：https://arxiv.org/html/2502.14802v2
- 官方论文页链接的代码：https://github.com/OSU-NLP-Group/HippoRAG
- 作者数据：https://huggingface.co/datasets/osunlp/HippoRAG_2

### 正文证据

论文摘要明确指出，一些结构增强 RAG 虽改善关联/理解任务，却在基本事实任务上跌到普通 RAG 以下；HippoRAG 2 的目标是同时保住这些能力，而不是只增加图结构。

- §3.2 Dense-Sparse Integration：在概念 phrase 节点之外加入 passage 节点，以 `contains` 边连接原始 passage 与其抽取概念，缓解只保留概念造成的信息损失。
- §3.3：默认以完整 query 的 embedding 匹配 triple，而不只依赖从 query 抽取实体。
- §3.4 Recognition Memory：先向量召回 top-k triples，再用 LLM 过滤。
- §3.5：过滤后无 triple 时，直接退回 embedding passage retrieval；有 triple 时同时使用 phrase 种子和 passage 种子，按分数/权重分配 reset probability，运行 Personalized PageRank 并返回 passage。

原实验覆盖 Natural Questions、PopQA、MuSiQue、2Wiki、HotpotQA、LV-Eval、NarrativeQA；正文 Table 2 的主要生成器为 Llama-3.3-70B-Instruct，retriever 为 NV-Embed-v2。**没有当前 PersonaMem-v1 32k 的直接成绩。**

### 无需训练与复现条件

核心方法是预训练 LLM 的离线信息抽取、既有 embedding、在线 LLM 过滤与 PPR，未要求为目标数据集训练新模型参数。无训练不等于无成本：图构建、抽取与过滤的调用、缓存和索引都必须计费。当前官方 README 提供外部模型端点配置，但真正复现应固定代码 commit、抽取模型/提示、embedding、建图参数和索引身份；将这些模型改成当前 DeepSeek 属于模型对齐重测，不能直接继承论文数字。

### 对当前系统的意义与限制

它支持“基础检索通路与结构通路并存”的设计依据。对本项目可先做小消融：同一候选库、同一 token 上限，将纯正边际 bundle 选择与“预设 dense 锚点＋bundle 补充”比较。这里的 dense 锚点方案是我们的机制检验，不是 HippoRAG 2 原算法。

音乐案的关键事实已被召回，直接替换为更大的图检索并不是最小修复；应先隔离最终选择的损失。PPR、LLM triple filtering 也仍可能遗漏事实，不能把结构化输出视为真实性证明。它不直接解决当前 query 被错误当成历史记忆或偏好时序冲突。

## 3. A-Mem：保留原文的结构化笔记与动态关联

**正式论文**：Wujiang Xu et al., *A-Mem: Agentic Memory for LLM Agents*, NeurIPS 2025，主会 Poster。

### 官方身份与可复查材料

- 官方会议页：https://neurips.cc/virtual/2025/poster/119020
- 官方会议页链接的 OpenReview：https://openreview.net/forum?id=FiM0M8gcct
- 作者论文（本次阅读 v11，2025-10-08）：https://arxiv.org/html/2502.12110v11
- 作者明确标记“复现论文结果”的代码：https://github.com/WujiangXu/AgenticMemory
- 作者系统实现：https://github.com/agiresearch/A-mem

两个仓库不能混为一谈：系统仓库 README 明确引导论文复现使用 `WujiangXu/AgenticMemory`；复现仓库也说明其用途是 paper evaluation。

### 正文证据

- §3.1：每条笔记保存原始交互内容、时间戳、LLM 生成的关键词/标签/上下文描述、embedding 和链接集合，而非只存一句抽象主题。
- §3.2：先用 embedding 取近邻候选，再由 LLM 分析共同属性建立链接。
- §3.3：新记忆可触发更新既有记忆的 context、keywords、tags，实现记忆演化。
- §3.4：使用 query embedding 检索 top-k 记忆，为生成器提供历史上下文。这里应描述为结构化记忆和检索，不宜夸大成对所有依赖路径的完备搜索。

原论文实验为 **LoCoMo、DialSim**，不是当前 PersonaMem split。正文/附录报告多种基础模型，不能借“支持多模型”推断我们的量化 DeepSeek 结果。论文 reproducibility checklist 对是否报告统计显著性回答 No，说明多次 API 调用成本高；因此不能把其单次数值理解为已验证的稳定优势。

### 无需训练与复现条件

核心记忆构造、链接和演化是 LLM 提示推理，检索使用既有编码器，无需针对 PersonaMem 更新模型参数。需统计记忆写入/重写的离线 LLM 成本，而不仅是问答时一次生成成本。复现仓库 README 提供 LoCoMo evaluation 和 k-sweep，并提醒 k 影响论文最优结果；迁移时必须在独立开发集预设 k，不能在当前 589 道评测题上扫描取最好成绩。

### 对当前系统的意义与限制

可借鉴“将个人事实显式写成可检索结构，同时保留原文及 source IDs”，减少长篇对话主题词掩盖身份事实的机会。但目前音乐案的事实并非不可检索，因此它是表示层对照方法，不是已有选择故障的直接证据。

动态 LLM 重写可能产生错误关联或把后来的信息写回早期状态；迁移 PersonaMem 必须按每题 cutoff 顺序构建/截取记忆，禁止用完整用户未来历史建一次库后供早期问题检索。每个生成属性都应可追溯到允许看到的原文。A-Mem 的链接不是因果证明，也不能自动保证“旧偏好已失效”。

## 4. MemoryOS：分开近期交互、主题记忆与长期用户画像

**正式论文**：Jiazheng Kang et al., *Memory OS of AI Agent*, EMNLP 2025 主会，25961–25970，DOI `10.18653/v1/2025.emnlp-main.1318`。

### 官方身份与可复查材料

- 官方论文页：https://aclanthology.org/2025.emnlp-main.1318/
- 正式 PDF：https://aclanthology.org/2025.emnlp-main.1318.pdf
- 作者方法全文（本次阅读预印本 v1）：https://arxiv.org/html/2506.06326v1
- 作者代码：https://github.com/BAI-LAB/MemoryOS

### 正文证据

§3 给出 Storage、Updating、Retrieval、Generation 四个模块，以及 STM/MTM/LPM 三层：

- STM：带 query、response、timestamp 的 dialogue pages，构成对话链；容量满时 FIFO 迁移。
- MTM：将同主题页面放入 segment；使用语义相似与关键词 Jaccard，分 segment/page 两级检索。
- LPM：分别保存用户资料、User KB 和动态 User Traits 等，用于长期个人信息。
- Heat 综合访问次数、segment 页面数量和最近访问衰减，用于迁移/淘汰；生成时整合近期对话、相关页面和画像信息。

原文实验数据集为 **GVD、LoCoMo**。ACL 正式摘要的 LoCoMo F1 相对提升写作 **48.36%**；arXiv v1/README 写作 **49.11%**，BLEU-1 均为 46.18%。这说明必须区分版本，不能混抄或把相对提升当百分点，更不能当 PersonaMem 准确率。正式报告若非必要，建议不列这组不可直接横比的数字。

### 无需训练与复现条件

核心流程采用 LLM 抽取/总结、embedding、规则阈值和队列管理，没有针对目标数据集的新参数训练步骤。代码 README 有可更换模型与 LoCoMo 复现入口；迁移需要计入记忆生成和更新成本，并固定容量、阈值、访问时间来源、执行顺序。

### 对当前系统的意义与限制

可用作“独立用户事实/画像通道”的训练免费对照：历史话题相关性不足时，仍有明确的人物事实或偏好供生成参考。可同时启发时序日志字段：`observed_at`、`source_ids`、`supersedes`/有效性说明，以及为什么某条事实保留或失效。

不过，论文的 recency 是**距上次访问的时间**，不自动等于事件发生时间、用户偏好生效时间或事实可信度。高频老事实可能很热，低频但重要的新变化也可能很冷。故不能说采用 MemoryOS 热度公式就解决 PersonaMem 偏好更新；这需要专门的冲突、否定、更新子集检验。

## 5. 报告中的推荐顺序与证据标准

1. **先做可解释性/协议修正，不先换完整算法。** 当前 query 与历史证据分离；按任务截止时间过滤；区分搜索候选出现、进入归档、进入最终上下文和真正支持答案。当前 query 的重复不是未来信息泄漏本身，但可能造成自匹配和把“重述问题”误当作有用证据，需要单独记录与消融。
2. **先隔离选择器。** 固定候选池、生成器和 token 上限，对比原正边际选择、dense 锚点保留、离线诊断性补事实。选择器单改实验先验证音乐案这类“召回到但没有用上”的失败。
3. **再用 Sufficient Context 的思想补审计层。** 人工小样本验证后再扩展提示式充分性标注；不将该标注器未经验证替代原 scorer，不把已看到正确标签的人工注解送回在线搜索。
4. **最后按模块引入外部免训练基线。** HippoRAG 2 对照检索/结构融合，A-Mem 对照记忆表示/关联，MemoryOS 对照分层事实/时序维护。三者都需在完全相同 PersonaMem 文件、cutoff、问题集、生成模型版本和量化配置上重跑。

每次对比至少共同报告：同题配对正确率、任务成功覆盖率、失败原因、有效证据覆盖/最终保留率、最终 token、离线写入成本、在线成本、重复上下文与生成波动。日志中的正 interaction、ANN 用满、bundle 数或 reranker 分数只能作为过程证据，不能单独作为模块有效性的判据。

本次工作只读取公开文献、作者代码说明和现有审计证据，未改实验代码，未运行任何模型推理或训练。上述改进是报告建议，尚未实施或验证。
