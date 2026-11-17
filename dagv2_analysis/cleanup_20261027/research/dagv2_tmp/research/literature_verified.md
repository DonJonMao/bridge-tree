# 2024—2026 RAG 顶会文献核验及与 DAG v2 的重叠

核验日期：2026-10-01。采用三个自然年窗口（2024、2025、2026，截至核验日），不是以 arXiv 上传年份作为发表年份。核心 20 篇的稳定编号、全部作者、官方摘要、正式 venue 和直接链接在 `literature_core.json`。窗口内主会长文/正式主会文章计入核心；2023 IRCoT 仅作为背景；未核实的 CRAG/GraphRetriever 不计入正式顶会清单。论文数量是代表性选择，不是穷尽性系统综述。

## 1. 先给结论：可提出研究假设，不能把组合组件当成已证明新颖

“问题分解成树/DAG”“多候选答案”“候选填槽后再次检索”“多链保留”“局部/全局回滚”“最小充分上下文”“信息价值分配检索预算”均已存在直接或接近先例。尤其：

- **BeamAggR [L05] 已保留每个问题节点的 top-k 答案与概率，对候选组合填入 #i 占位符，再进行包含外部检索的 multi-source reasoning**；因此多值 parent-slot 及下游按候选重新检索本身不是新机制。
- **ReAgent [L13] 已在验证到矛盾时执行局部/全局回退，且只重查被失效证据对应的子问题**；“局部重放”本身不能独立声称新颖。
- **CIRAG [L17] 明确保留多条 plausible evidence chains，并按证据充分性在三元组→句子→整段文档之间级联**；多链或最小充分证据也不能独立声称新颖。
- **ETS [L10] 对证据句集合的相互依赖和 reader 实际答题效用建模**；“用证据效用替代节点数”需要进一步限定实际目标和无 gold 的估计方式。

建议把研究点写成：**在原有问题 DAG 中，用可追溯原文约束歧义实体候选，并通过下游原文的差异支持/显式反证识别上游分支，随后使依赖该分支的支持证书失效并在固定预算内重放。** 这目前是待验证的具体研究设计，不是已经证明首创的结论。最有价值的证据是：在相同模型、相同调用/token 预算下，超越 BeamAggR 式候选投票/边际聚合、ReAgent 式冲突回滚和 CIRAG 式多链整合；并用错误父实体注入、证据互换/移除等实验表明收益来自原文辨识机制，而非额外检索和额外采样。

“下游没有找到支持”不等价于“父候选错误”：候选可能正确但检索失败。显式 refutes、无支持 unknown 和 supports 必须分开。候选若均无证据，应保持不确定或退回原有路径，不能制造语义反证。

## 2. 最接近的工作：具体方法与可能差异

| 文献 | 官方方法证据 | 与建议方案的直接重叠 | 可检验的差异及限度 |
|---|---|---|---|
| BeamAggR [L05] | §3.1 节点包含 question、candidate answers、probabilities；Algorithm 1 的 CartProd/MaskFill；§3.2 四知识源推理及频率投票；§3.3 beam组合后再次multi-source reasoning和边际概率聚合 | 多候选子答案、占位符替换、候选条件检索/推理、限制beam防爆炸 | 可以研究仅原文锚定候选、候选独立证据支持/反证判别、共享DAG祖先一致性及支持失效；但“top2”“DAG取代树”只是实现选择，不足以证明贡献 |
| ReAgent [L13] | §4.1 无效证据只重查其关联 qi；§4.2 supervisor定位最小不一致集合；§4.4 local/global backtracking；persistent log | 矛盾触发纠错、局部重查、状态恢复 | 可对比“已接受断言出现矛盾后回退”与“提交前保留实体歧义，候选间原文差异判别”；确定性后代失效规则与固定预算有望形成可复现实验协议；回退本身已有先例 |
| CIRAG [L17] | §3.3 history-conditioned integration筛选core triples，保存triples→句子/文档provenance，累计多轮证据；§3.4通过是否refusal决定triple/sentence/document充分性；§3.5轨迹蒸馏 | 多链保留、跨轮证据历史、出处映射、充分性控制 | CIRAG方法定义以core triple集合和下一查询为状态，未在正文方法中定义每个父slot的竞争实体赋值、分支间反证及DAG支持失效；必须将后者作为具体接口和实验机制，而非泛称多链创新 |
| ETS [L10] | §3.2训练MCTS节点reward为reader给gold answer的条件似然；训练policy/value；§3.3推理early-terminating beam，句子前缀定位原文 | 证据集合整体效用、证据句协同、搜索预算 | 推理不能使用测试gold；如改用终端充分性proxy，需验证proxy校准及与ETS/相同预算搜索的差异，不能宣称“首次考虑协同证据” |
| D²Plan [L16] | §2.1 ordered sub-question及#A_j占位符；Reasoner/Purifier；已解子问题后refine下一问；最多K次检索仍无解才revise剩余计划；§2.2-2.3 SFT+RL | 分解、依赖答案填槽、检索反馈改计划、证据去噪 | 方法正文没有定义同一已解slot多候选的平行保留/原文对照；它也具有最大重试控制。因此只能强调明确多值slot和分支证据判别协议，不能把动态计划/有界重试说成新颖 |
| COSMOS [L18] | §3.2边集大小K+连通+查询根实体约束；语义相关性/冗余边际效用；§4 seed-guided greedy + topology-aware组件聚合；结构对比训练 | 预算下证据子图选择、连通性、整体效用 | 它针对显式KG边集的检索，不是自然语言问题DAG的slot假设；可研究语义支持证书充分性，但约束优化/图连通本身已有工作。本文理论结论不能直接移植到新的充分性目标 |
| CheckRLM [L19] | §3.2 段落级rt中抽取claim，查询{原问+claims}独立检索；修正模型以原文作最小token修正，随后继续生成；DPO训练recognition/correction | 推理中事实定位、独立证据检索、局部修正接续 | {rt, rt′}只是当前段落修正/不修正状态，不是父实体竞争赋值。需对比当前段落claim纠错与跨DAG依赖的歧义分支辨识，不能泛称“原文验证纠错”新颖 |
| Weakest Link [L20] | §3 MFAI attention instruction + 18文档/3bucket受控位置实验；识别与综合失败分解 | 证据可见性、终端链弱点、上下文顺序和误导提示评估 | 属诊断而非parent-slot检索策略；为评测链注入/提示先验提供依据，不是对所有reader或所有上下文位置的定律 |

上述“未定义”仅限已读取的官方摘要、正文方法及相关附录文本范围。没有穷尽这些工作的全部源码、历史版本或所有相邻文献；报告不应据此写“首次”。

## 3. 核心20篇的主题、适用范围和 DAG v2 启示

### 2024：自反、候选探索及检索效率

**[L01] Self-RAG — ICLR 2024 oral。** 官方 OpenReview `venueid=ICLR.cc/2024/Conference`。训练reflection token以判断是否检索、相关性、支持性和答案效用，推理可调整检索频率与偏好。它说明“自评+检索控制”已成熟；若 DAG v2 继续冻结LLM，不应宣称实现了训练式Self-RAG。启示是分离支持判断与最终答案，而不直接采信自报confidence。

**[L02] RAPTOR — ICLR 2024 poster。** 递归聚类并生成摘要，形成多层树状索引，检索可跨抽象层。树索引表示资料层次，与DAG任务依赖层次不同；对DAG可提供长材料多粒度archive pool，但摘要不可替代原文出处和原文充分性验证。

**[L03] RECOMP — ICLR 2024 poster。** 官方摘要描述训练抽取/生成式compressor，将检索材料变为短摘要，并在没有有用信息时输出空摘要做selective augmentation。启示是保留“无益证据不加入”的状态；直接压缩并塞入链仍需测reader噪声敏感性。

**[L04] Adaptive-RAG — NAACL 2024 long。** 通过小分类器按问题复杂度选择无检索、单次或迭代RAG，标签来自模型预测结果及数据集归纳偏置。它控制整题策略，不是针对特定有歧义DAG节点的反证获取。需要比较统一成本下局部策略收益，而非笼统称自适应检索创新。

**[L05] BeamAggR — ACL 2024 long。** 此文是multi-valued parent-slot设计的关键强基线，详见上一表；正文证明候选填槽后下游外部检索已有先例。它使用四知识源及投票/边际概率，而原文证据判别须用等预算对照证明价值。

**[L06] EfficientRAG — EMNLP 2024 main。** labeler和filter经过训练，依据检索内容标出有助于下一轮的token并迭代产生query，不需每轮调用大型LLM。支持把query refinement与节点answer resolve分离，并测量真正节约的LLM调用；冻结推理法与训练模块不是同一预算。

**[L07] HippoRAG — NeurIPS 2024 main。** 开放知识图谱、实体检索与Personalized PageRank结合，执行关联多跳检索。它的图是资料关联图，不等同于DAG v2的问题依赖图。可作为graph retrieval baseline，不宜将建图/PPR直接作为新增论文主贡献。

### 2025：reader效用、多路径与可逆推理

**[L08] From RAG to Memory（HippoRAG 2）— ICML 2025，PMLR 267。** 官方题名不包含“HippoRAG 2”。它在PPR基础上加强passage integration和在线LLM使用，追求事实/关联/sense-making记忆共同改进。启示是图检索应保留段落原文，防止仅三元组的语境损失。

**[L09] RAGGED — ICML 2025，PMLR 267。** 在不同retriever-reader组合与检索深度中测稳定性，结论是reader噪声鲁棒性决定是否从更深检索获益。DAG“closure覆盖更多节点”不能自动推出答案更好；应测证据数、token、排序、链注入与reader错误的关系。

**[L10] Evidence Tree Search — ACL 2025 long。** 将证据句集合表示为路径，训练MCTS使用reader正确答案似然，policy/value推理使用早停beam。与DAG的证据选集目标直接相关，但主要基于LongBench长上下文证据提取，不能将其论文数字当作本项目开放域端到端比较。

**[L11] GRAT — ACL 2025 long。** 过程奖励MCTS进行多路径探索、逐步评估、全局选取和自训练，减少仅单链贪心限制。增加搜索节点/过程奖励自身已有先例；DAG研究应给出确定的成本和证据接口优势。

**[L12] PropRAG — EMNLP 2025 main。** 用上下文较丰富的proposition取代孤立三元组，在线无需LLM的beam搜索命题路径。在HotpotQA/2Wiki/MuSiQue同类场景很适合作为检索对照；不能把“图路径多跳”单独作为创新。

**[L13] ReAgent — EMNLP 2025 main。** 非单调多agent知识集、局部/全局回退、被失效证据对应子问题重查。必须把“局部回退”标注已有先例；建议方法需在候选提交与DAG依赖证书层面给出清晰区别。

### 2026：最新的多链整合、计划、证据目标与诊断

**[L14] Query Decomposition for RAG: Balancing Exploration-Exploitation — EACL 2026 long。** 每个子query为bandit臂，逐文档观察奖励并更新相关性信念，研究层次分解。正文§3.3主要离线监督实验可获得relevance labels；在线LLM judge/click/retrieval scores是备选信号，不能把其离线结果直接承诺为DAG在线收益。VOI/预算路由应作为配套而非独立新颖核心。

**[L15] Classifying and Addressing the Diversity of Errors in RAG Systems — EACL 2026 long。** 16类错误覆盖chunking/retrieval/reranking/generation；RAGEC先判答案、再标首错阶段与类型，配套人工标注数据。可以借鉴首错分层，但其通用taxonomy不能自动定位DAG某个父slot错误；需要自己的节点与依赖日志。

**[L16] D²Plan — ACL 2026 long。** 动态顺序规划、Reasoner/Purifier、SFT+plan-oriented RL，失去关键证据或被外围证据误导是主要动机。说明“更精细planner+purification”已有强先例；DAG方案应克制组件扩张，聚焦可审计的分支状态。

**[L17] CIRAG — ACL 2026 long。** 最接近的多链/多粒度RAG之一，正文§3.3-3.5包括triple→source mapping、多轮core sets及轨迹蒸馏。注意它充分性indicator是refusal模板匹配、所有层均不充分时仍默认document-level answer；这不是语义充分性的证明。DAG可研究独立支持证书，但需与这种行为indicator清楚区分。

**[L18] COSMOS — ACL 2026 long。** 显式KG检索的连通/大小约束和整体utility优化、greedy组件聚合、结构对比调优。新充分性目标应检查是否真的满足submodularity等假设，不能仅借名词或宣称保证。

**[L19] CheckRLM — ACL 2026 long。** 及时抽取并修正推理段落中错误claim，DPO训练修正器。用于比较“逐段纠错”和“父slot歧义辨识导致后代局部失效”两种控制；文献效果不能代替本项目原文反证实测。

**[L20] Failure Modes in Multi-Hop QA: Weakest Link/Recognition Bottleneck — ACL 2026 long。** 受控attention提示和位置实验将recognition与synthesis拆开，并分析误导提示/不同任务拓扑。对DAG final prompt最有用的启示是：selected_docs即便包含关键原文，也不保证reader识别/采用了它；“有链”不应被当作“有证据”。

## 4. 推荐给报告的实验对照

1. **强基线**：原版DAG；同模型同预算的BeamAggR式candidate beam/概率投票；CIRAG式多链/多粒度；ReAgent式矛盾后局部回退；新增机制的完整版本。模型/语料/提示/输出token总预算应可比。训练式与冻结式方法分别说明是否重现、直接用发布模型或仅做思想对照。
2. **机制消融**：候选保留；候选保留+下游检索；增加独立原文supports/refutes/unknown判别；再加依赖失效/局部重放；再加terminal-sufficiency与chain-exposure校准。不能只与弱单链baseline相比。
3. **定向扰动**：错误父实体注入、同名实体候选、错误但流畅链、删除关键下游原文、用不相关文档替换原文、仅改变原文顺序；记录恢复正确父slot的比例与不必要修改正确父slot的比例。删掉支持只支持因果依赖评估，不代表为另一个候选创造了反证。
4. **评测报告**：QA EM/F1、支持文档/句召回、原文支持判别准确性、父slot纠错精度/覆盖、正确→错误损伤率、首错节点、分支数/重放范围、失败/拒答、物理HTTP与逻辑LLM调用、reader token和总成本。采用paired bootstrap/随机化检验与置信区间，不杜撰效应量。
5. **reader控制**：相同selected_docs下比较raw-docs-only、仅validated chain、错误chain注入、masked parent-slot；解释reader受中间答案先验影响还是受原文不足影响。将链注入作为实验变量，不能把chain_confidence当事实验证。

## 5. 核验来源与正式状态注意

- ACL/NAACL/EMNLP/EACL：`https://aclanthology.org/<paper-id>/` 的citation metadata、官方正文PDF；会议整卷XML来自官方 `acl-org/acl-anthology` GitHub，存在本地 `sources/*.xml`。2026 ACL论文页publication date为2026/7，EACL为2026/3，均早于截止日。
- ICLR 2024：OpenReview官方搜索API返回的submission note的venue和venueid；核心Self-RAG正式ID是 **hSyW5go0v8**，而不是常被误写的另一个ID。完整API响应存为 `sources/openreview_*.json`。RAPTOR=GN921JHCRw，RECOMP=mlJLVigNHp。
- ICML 2025：PMLR卷267的官方页面明确International Conference on Machine Learning；网页上的proceedings online publication date为2025/10/06，不改变ICML2025会议归属。
- NeurIPS 2024：官方proceedings的Conference正文条目；HippoRAG不是GraphRAG一般综述。
- **CRAG（Corrective Retrieval Augmented Generation）**：核验的OpenReview记录是2024 CoRR、ICLR2025 withdrawn、ACL ARR2026 May submission。未核实AAAI2025正式发表；不写“CRAG AAAI25”。这些状态不足以断言永远未发表，只能说明本次未找到正式顶会来源。CRAG还可指NeurIPS2024的 **Comprehensive RAG Benchmark**，二者不是同文。
- **GraphRetriever**：此次搜索没有取得正式ICLR2025 submission-title/venue证据，未计入。不可把名字类似的G-Retriever NeurIPS2024、GRAT ACL2025或图检索工作相互替换。
- **IRCoT**：Trivedi, Balasubramanian, Khot, Sabharwal，ACL2023 long，`https://aclanthology.org/2023.acl-long.557/`，仅背景。
- **可选补充**：Entity-Event KG/EACL2026 `https://aclanthology.org/2026.eacl-long.90/` 已核验正式long，但未挤入20篇主清单；主要研究时序因果一致性。RAGChecker/NeurIPS2024 Datasets and Benchmarks正式页面已保存，可作为评测补充，须注明track。


## 6. 完整核心参考文献（官方URL）

[L01] Akari Asai, Zeqiu Wu, Yizhong Wang, Avirup Sil, Hannaneh Hajishirzi. Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. ICLR 2024 oral. https://openreview.net/forum?id=hSyW5go0v8

[L02] Parth Sarthi, Salman Abdullah, Aditi Tuli, Shubh Khanna, Anna Goldie, Christopher D Manning. RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval. ICLR 2024 poster. https://openreview.net/forum?id=GN921JHCRw

[L03] Fangyuan Xu, Weijia Shi, Eunsol Choi. RECOMP: Improving Retrieval-Augmented LMs with Context Compression and Selective Augmentation. ICLR 2024 poster. https://openreview.net/forum?id=mlJLVigNHp

[L04] Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang, Jong Park. Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity. NAACL 2024 (long). https://aclanthology.org/2024.naacl-long.389/

[L05] Zheng Chu, Jingchang Chen, Qianglong Chen, Haotian Wang, Kun Zhu, Xiyuan Du, Weijiang Yu, Ming Liu, Bing Qin. BeamAggR: Beam Aggregation Reasoning over Multi-source Knowledge for Multi-hop Question Answering. ACL 2024 (long). https://aclanthology.org/2024.acl-long.67/

[L06] Ziyuan Zhuang, Zhiyang Zhang, Sitao Cheng, Fangkai Yang, Jia Liu, Shujian Huang, Qingwei Lin, Saravan Rajmohan, Dongmei Zhang, Qi Zhang. EfficientRAG: Efficient Retriever for Multi-Hop Question Answering. EMNLP 2024 (main). https://aclanthology.org/2024.emnlp-main.199/

[L07] Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, Yu Su. HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. NeurIPS 2024 (main conference). https://proceedings.neurips.cc/paper_files/paper/2024/hash/6ddc001d07ca4f319af96a3024f6dbd1-Abstract-Conference.html

[L08] Bernal Jiménez Gutiérrez, Yiheng Shu, Weijian Qi, Sizhe Zhou, Yu Su. From RAG to Memory: Non-Parametric Continual Learning for Large Language Models. ICML 2025 (PMLR 267). https://proceedings.mlr.press/v267/gutierrez25a.html

[L09] Jennifer Hsia, Afreen Shaikh, Zora Zhiruo Wang, Graham Neubig. RAGGED: Towards Informed Design of Scalable and Stable RAG Systems. ICML 2025 (PMLR 267). https://proceedings.mlr.press/v267/hsia25a.html

[L10] Hao Sun, Hengyi Cai, Yuchen Li, Xuanbo Fan, Xiaochi Wei, Shuaiqiang Wang, Yan Zhang, Dawei Yin. Enhancing Retrieval-Augmented Generation via Evidence Tree Search. ACL 2025 (long). https://aclanthology.org/2025.acl-long.1175/

[L11] Xianshu Peng, Wei Wei. GRAT: Guiding Retrieval-Augmented Reasoning through Process Rewards Tree Search. ACL 2025 (long). https://aclanthology.org/2025.acl-long.1352/

[L12] Jingjin Wang, Jiawei Han. PropRAG: Guiding Retrieval with Beam Search over Proposition Paths. EMNLP 2025 (main). https://aclanthology.org/2025.emnlp-main.317/

[L13] Zhao Xinjie, Fan Gao, Xingyu Song, Yingjian Chen, Rui Yang, Yanran Fu, Yuyang Wang, Yusuke Iwasawa, Yutaka Matsuo, Irene Li. ReAgent: Reversible Multi-Agent Reasoning for Knowledge-Enhanced Multi-Hop QA. EMNLP 2025 (main). https://aclanthology.org/2025.emnlp-main.202/

[L14] Roxana Petcu, Kenton Murray, Daniel Khashabi, Evangelos Kanoulas, Maarten de Rijke, Dawn Lawrie, Kevin Duh. Query Decomposition for RAG: Balancing Exploration-Exploitation. EACL 2026 (long). https://aclanthology.org/2026.eacl-long.322/

[L15] Kin Kwan Leung, Mouloud Belbahri, Yi Sui, Alex Labach, Xueying Zhang, Stephen Anthony Rose, Jesse C. Cresswell. Classifying and Addressing the Diversity of Errors in Retrieval-Augmented Generation Systems. EACL 2026 (long). https://aclanthology.org/2026.eacl-long.147/

[L16] Kangcheng Luo, Tinglang Wu, Yansong Feng. D^2Plan: Dual-Agent Dynamic Global Planning for Complex Retrieval-Augmented Reasoning. ACL 2026 (long). https://aclanthology.org/2026.acl-long.216/

[L17] Zili Wei, Yilin Wang, Xiaocui Yang, Shi Feng, Weidong Bao, Daling Wang, Zihan Wang, Yifei Zhang. CIRAG: Construction–Integration Retrieval and Adaptive Generation for Multi-hop Question Answering. ACL 2026 (long). https://aclanthology.org/2026.acl-long.1203/

[L18] Boci Peng, Xiao Liu, Boren Hu, Yun Zhu, Xuanbo Fan, Yanwei Yue, Chunyu Yang, Yan Zhang. COSMOS: Connectivity-Oriented Submodular Maximization for Optimal Subgraph Retrieval. ACL 2026 (long). https://aclanthology.org/2026.acl-long.1662/

[L19] Dingling Xu, Ruobing Wang, Qingfei Zhao, Yukun Yan, Zhichun Wang, Daren Zha, Shi Yu, Zhenghao Liu, Shuo Wang, Xu Han, Maosong Sun. CheckRLM: Effective Knowledge–Thought Coherence Checking in Retrieval-Augmented Reasoning. ACL 2026 (long). https://aclanthology.org/2026.acl-long.1780/

[L20] Meiru Zhang, Zaiqiao Meng, Nigel Collier. Failure Modes in Multi-Hop QA: The Weakest Link Effect and the Recognition Bottleneck. ACL 2026 (long). https://aclanthology.org/2026.acl-long.1937/

