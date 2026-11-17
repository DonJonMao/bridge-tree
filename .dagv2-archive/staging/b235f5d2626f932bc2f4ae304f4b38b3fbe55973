# 迭代/自适应 RAG 对照：与 DAG + BT 剩余求解方法的机制边界

日期：2026-10-12。阅读对象：`tmp/pdfs/dag_bt_innovation/method.txt`（用户 PDF 的文本）。本笔记只研究机制，不使用实验答案标签，不修改代码。按严格滚动两年看，2024-10-12 至今为主窗口；NAACL/ICLR 2024 只能补充历史背景。以下会场均通过会议正式论文页核验；不把 arXiv 年份当作录用年份。

## 最值得在论文中直接比较的三篇

### 1. CoRAG — NeurIPS 2025 Main Conference

**Chain-of-Retrieval Augmented Generation**，Liang Wang 等。

- 正式会场：[NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/566aad4fac1acf17fd1ae8c3aef75326-Abstract-Conference.html)。
- 正文：[作者终稿 arXiv 2501.14342v3](https://arxiv.org/pdf/2501.14342v3)，首页明确 NeurIPS 2025；本地 `iterative_sources/corag_paper.txt`。
- §3：根据不断变化的检索链状态生成子查询/子答案；通过 rejection sampling 生成检索链训练数据；推理时有 greedy、best-of-N、tree search 等计算量伸缩方式。
- **§5.4 Learning to Stop at Test Time（PDF 第 9 页）直接比较停止机制**：每次检索后，模型额外预测已经获取的信息是否足够，输出空间限制为 Yes/No；Yes 则停止生成子查询。训练标签来自使最终答案似然最大的检索链前缀；用 Yes token 的 logit bias 控制早停。
- 原文短引：`If the decoded output is “Yes”, no further sub-queries are generated.`
- 对本方法的约束：**子问题分解、动态查询改写、树搜索、节省检索以及早停本身都不能作为新增贡献。** 可比较的是：CoRAG 学习预测充分性；当前方案在明确的类型化关系/输出契约内，用已验证绑定化简关系，检查未绑定项是否仍可能改变所要求输出。两者的停止依据不同。
- 边界：不能由此声称本方法实际效果优于 CoRAG，也不能把符号关系内部的正确性扩张成自然语言规划/事实判断正确性。

### 2. SeaKR — ACL 2025，Long Papers

**SeaKR: Self-aware Knowledge Retrieval for Adaptive Retrieval Augmented Generation**，Zijun Yao 等。

- 正式页：[ACL 2025 long.1312](https://aclanthology.org/2025.acl-long.1312/)。正文：[PDF](https://aclanthology.org/2025.acl-long.1312.pdf)；本地 `seakr_paper.txt`。
- §3.1–3.2，pp.27024–27025：对同一上下文多次采样，使用 EOS 隐状态的正则化 Gram 矩阵行列式估计不确定性；超过经验阈值触发检索。查询由伪生成的 rationale 去除低概率、不确定 token 得到。
- §3.3：对多个检索片段构造上下文，选择最能降低模型不确定性的片段，属于**基于不确定性的重排**。
- §3.4，pp.27025–27026：停止条件为模型生成 `So the final answer is`，或达到检索次数上限；最终在基于 rationale 与基于知识片段的两种推理中按不确定性选择。
- 对本方法的约束：不能笼统声称“现有方法都固定检索”“首次根据状态决定检索”。可强调本方案的控制状态是**剩余求解关系及活跃事实需求**，而不是生成置信度；原文条件化桥接无须以候选单篇的降不确定性/相关性评分作为必要前提。
- “零 reranker”是架构和成本选择，不是独立的新颖性证明；应验证移除评分后是否仍可找回联合支持、减少误剪枝，以及成本是否真的下降。

### 3. RAG-Star — NAACL 2025，Long Papers

**RAG-Star: Enhancing Deliberative Reasoning with Retrieval Augmented Verification and Refinement**，Jinhao Jiang 等。

- 正式页：[NAACL 2025 long.361](https://aclanthology.org/2025.naacl-long.361/)。正文：[PDF](https://aclanthology.org/2025.naacl-long.361.pdf)；本地 `ragstar_paper.txt`。
- §4.2–4.3，p.7067：MCTS/UCT 选择、扩展推理节点；路径历史是原问题与已生成子问/子答案对。Policy model 基于内部知识生成下一个子问和候选答案。
- §4.4，p.7068：检索外部证据，用 answer-aware reward 检查/修正答案，用 query-aware reward 检查子问逻辑，反向传播奖励引导后续树搜索。
- 对本方法的约束：**树结构、多步规划、检索支持的中间答案校验都已有成熟先例。** 需要明确区分：RAG-Star 的树是候选推理轨迹的搜索结构；当前初始 DAG 表达任务依赖，而 BT 是当前事实需求内的原文线索导航；剩余关系决定哪些需求仍影响输出。仅“DAG 比 chain 多分支”很弱。

## 另外三篇补充对照

| 论文、已核验会场 | 已有机制 | 对本方法的边界 |
|---|---|---|
| [Search-o1，EMNLP 2025 main.276](https://aclanthology.org/2025.emnlp-main.276/) | §3.3–3.5：模型在推理中输出搜索边界 token，检索得到文档后，Reason-in-Documents 将历史推理、当前查询和文档共同处理，提炼内容再注入推理链。 | 已有“检索结果联合阅读并反馈推理”的机制。当前原文桥接若要有辨识度，必须与残余需求、保留原始来源及真实绑定依赖相联，不能只叫阅读反馈。 |
| [ReasonRAG / Process vs. Outcome Reward，NeurIPS 2025 Main](https://proceedings.neurips.cc/paper_files/paper/2025/hash/54e1381d0c0598127b90af4c940fd3d9-Abstract-Conference.html) | 官方摘要核验：RAG-ProGUIDE 为 query generation、evidence extraction、answer generation 提供过程级奖励，训练 agentic RAG；非仅结果奖励。 | 查询—证据—答案的分阶段过程优化已有研究。本文若不训练奖励模型，应把控制与证据约束讲清楚，避免称“首次联合优化三阶段”。这里只核验正式摘要，未据此推断其所有停止细节。 |
| [EfficientRAG，EMNLP 2024 main.199](https://aclanthology.org/2024.emnlp-main.199/) | 官方摘要：迭代生成新查询并过滤不相关信息，每次迭代无需额外 LLM 调用。 | “迭代检索更省调用”不能单独作为创新；要有对照消融和总成本报告。发布时间 2024 年 11 月，处于严格近两年窗口。 |

2024 年历史补充：[Adaptive-RAG，NAACL 2024 long.389](https://aclanthology.org/2024.naacl-long.389/) 用小 LM 复杂度分类器在 no retrieval / single-step / iterative 三种策略间选择。它是问题级策略路由，不能等同于每次证据更新后的关系化简。Self-RAG/IRCoT/FLARE 可作更早背景；本次不将未成功获取正式页的 Search-R1 会场当作已核验事实，也不为了补 2026 年份而把预印本列为已录用论文。

## 三个递进贡献应怎样落点

1. **表示与控制：显式剩余求解状态。** 在检索前固定任务 DAG 和类型化输出契约，保留未知条件/实体；将新事实绑定代入，得到当前仍影响输出的需求。区别不在“会分解”，而在自然语言任务历史之外有可执行的剩余关系。必须承认 partial evaluation/短路求值本身是经典方法。
2. **证据获取：由剩余需求驱动、由原文线索条件化的桥接与联合绑定。** 当前子任务从 dense 出发，利用已读原文寻找跨记忆补充，联合阅读后产出带来源及实际父依赖的绑定。候选导航连接不等于证据支持关系；无 reranker 不等于没有检索排序，也不自动意味着低成本。这一点应通过组合证据/跨记忆测试证明，并消融“独立子问 dense”与“残余需求 + 原文桥接”。
3. **输出与停止：对输出契约敏感的不变性证书。** 在可执行关系的适用子集，只有剩余未绑定项不能改变要求的输出时才停止/剪去无关分支。`If(true,p,b)` 对只要主包名称的请求可以不查 b；若用户要求两种方案都给出或完整失败原因，则输出契约改变，不能沿用同一停止判断。比较 CoRAG 的 Yes/No 充分性预测和 SeaKR 的生成终止/上限停，实验报告成本—正确率及错误停止率。

**不能跨越的边界：** PDF 的 if 示例本身是标准短路，不能只凭示例宣称新理论。所谓“证书”只在规划关系、值域/约束、输入事实解释及来源审计均正确的条件下成立；开放式偏好建议的语义答案不应宣称获得同等形式保证。证据支持/冲突撤销、时间与主体范围、真实参数依赖是让控制结果可追溯的机制，但它们目前支持一个有希望的组合方法，不证明文献中从未出现过任何相似组件。

## 源材料

`iterative_sources/` 保存正式论文页、下载的正文及 pdftotext 文本。CoRAG venue 由 NeurIPS 正式页核验，§5.4 来自 2025-10-10 arXiv v3 接收终稿；SeaKR、RAG-Star、Search-o1 正文来自 ACL Anthology。`reasonrag_official` 仅用于正式会场与摘要机制核验。Google/部分 OpenReview 请求返回验证页，未用这些失败结果作为证据。
