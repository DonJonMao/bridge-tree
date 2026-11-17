# BeamAggR 及相近先例：2026-10-02 深读核验

## 结论与建议收敛点

建议继续以老版 DAG v2 为底座，但把主问题收敛为：**原问题明确限定的中间实体绑定漏掉/违反了某个条件时，从当前首次检索的原文中发现尚未得到证实的 binding predicate，用“候选实体 + 该关系 + 原问条件”发起至多两次全语料 dense 补查，以一次联合 raw 判读核验绑定，承诺后再执行子节点。MVP 不需要先扩展下游、深链 beam 或回滚；局部依赖重算留作后续。** 例如原问要求“1998 年影片 X 的导演的出生地”，不应把新增预算继续投入“候选 A 的出生地/候选 B 的出生地”；应先补查 `(directed_by, X, 1998, candidate)` 与实体身份，再决定何种出生地证据有资格支持原问。

多候选、每候选检索、反证淘汰、局部回滚、三值判断、条件化改写都已有先例，不能再作为新颖性的充分理由。**本次未证明上述收敛设计首创。** 可检验增量是：在唯一性约束明确的原问下，把“重复原子问”“延伸候选答案分支”“通用证据核验”与“补查仍未证实的绑定谓词”作为不同动作，并用局部约束状态控制提交，证明最后一种动作以相同候选、同样调用/检索成本更有效地修复错误绑定。

必须把原问本身真有多种合法解读与模型中间步骤错绑分开：DIVA/CondAmbigQA 处理的真歧义不应被强行压成唯一答案；在原问没有足够约束时，下游资料不能凭空恢复用户意图。

## 1. BeamAggR 的正式身份与源码边界

**Zheng Chu, Jingchang Chen, Qianglong Chen, Haotian Wang, Kun Zhu, Xiyuan Du, Weijiang Yu, Ming Liu, Bing Qin. BeamAggR: Beam Aggregation Reasoning over Multi-source Knowledge for Multi-hop Question Answering. ACL 2024, Volume 1: Long Papers, pp.1229–1248.**

- 正式论文页：https://aclanthology.org/2024.acl-long.67/
- 正式 PDF：https://aclanthology.org/2024.acl-long.67.pdf
- DOI：10.18653/v1/2024.acl-long.67。
- 已逐项读正文 §3.1–3.3、Algorithm 1、§5.3、§6.3、Limitations 和附录 A.2/A.4/A.5/A.6，重点检查 Figure 8 与 Table 4/7，以及外部知识推理 prompts。

**未取得作者 BeamAggR 官方代码仓库。** Anthology 页无作者 Software/code 链接；正式 PDF 的文本没有作者 repo；进一步提取并审查了全部 104 个 URI 注释，只有 HotpotQA 等数据资源和 IRCoT、ProbTree 等基线 repo，没有 BeamAggR 自身 repo。该结果不能证明作者代码不存在，只证明本次从指定权威来源未取得地址。因此以下算法结论是正式正文/附录层面核验，不能冒充公开实现逐行审计。没有猜 GitHub 地址或把名字相似的其他项目认作作者实现。

## 2. BeamAggR 具体做了什么

| 问题 | 正式证据 | 核实结果 |
|---|---|---|
| 每个节点是否保留多个答案？ | §3.1；Algorithm 1；Table 7(b) | 是。节点为 `N(i)={q(i),a(i),p(i)}`，答案/概率各为长度 k；叶子投票后 top-k，中间节点聚合后 top-k，root 最终输出 top-1 |
| 是否已有 top2？ | 附录 A.2 Table 4 | 是。默认 beam size=2；因此 top2 不构成新颖性 |
| 父/子候选怎么组合？ | Algorithm 1 行8；§3.3 Eq.(3)；Table 7(d) | 对被依赖子问题候选做 Cartesian product，组合先验为各候选概率的乘积 |
| 是否按候选接地问题？ | Algorithm 1 行9；Table 7(d) MaskFill | 是。将 `#i` 替换为对应候选答案，生成每个组合对应的具体问题 |
| 接地后是否再外部检索？ | Algorithm 1 行10；§3.2/3.3 | 是。每个替换问句再做 multi-source reasoning，含 Wikipedia BM25 和 Google SERP，不能误描述为只在固定文档上换答案 |
| 概率来自哪里？ | §3.2 Eq.(2)；Table 7 Vote/Aggr；§3.3 Eq.(4) | 四种知识源的采样答案按频次去重/归一；中间候选按组合先验与条件答案分布做边际概率聚合。是频率/投票式权重，不是独立原文蕴涵概率 |
| 是否只局部高风险节点开 beam？ | Algorithm 1；§5.3 | 主算法对树中各节点执行相应 top-k/组合步骤，没有定义风险触发的局部稀疏开关；但已有 k=1 greedy aggregation 成本变体，局部化本身仍需作为效率增量检验 |
| 是否主动寻找反证或补查遗漏的原問限定条件？ | §3.2/3.3；附录 prompts/Figure 8 | 没在已核验算法定义中找到该独立动作。外部检索直接服务于接地后子问题；prompt要求依据证据回答，不等价于“识别 missing binding predicate 后针对它另发查询” |
| 下游结果是否回写上游实体假设状态？ | Algorithm 1；§3.3；Figure 8 | 正式算法是 bottom-up 聚合输出，未定义下游检索证据触发上游 binding predicate 状态变更、父答案版本修改及仅相关支持路线失效 |

### 不要抹掉已有能力

BeamAggR §5.3 直接分析“广一些的候选可纠正错误推理”，并提供 greedy aggregation 对照；Figure 8 先保留 Cologne/Darmstadt，再检索两者旧名并聚合最终答案。因而“后续信息帮助纠正早期错误”也是已有动机和结果，不能泛称首次反向约束上游。

可区别的是明确的**状态和动作**：当前哪个原问绑定条件仍 unknown；哪个检索动作只补查这个条件；何种原文把父绑定标为 supports/refutes/unknown；何种依赖记录因版本变化失效。概率传播对最终答案有帮助与程序明确维护这些条件不是同一接口，但接口差异仍不是效果差异的证明。

### 实验协议注意

附录 A.2 使用 October 2017 Wikipedia dumps、Elasticsearch BM25、Google SERP（Serper）、Wikipedia/fuzzywuzzy 获取文本片段，四知识源包括 implicit internal/explicit internal/Wikipedia/web。Table 4 有 self-consistency、few-shot 与 beam 参数；其 Table 6 说明 Azure content-filter拒答样本从指标计算中省略。这些都与本仓库冻结模型/固定语料/全任务失败计零不同。

因此可以做“同模型、同语料、同预算的 BeamAggR 算法适配”，但在官方源码未获得时，必须标明算法适配，不能声称精确官方复现。对比应至少包含默认 k=2、k=1 greedy、只局部开候选以及等成本新增普通检索，不能只选弱的全单值路径。

## 3. DIVA：条件化查询已有，失败后的 predicate repair 未见于其算法定义

**Yeonjun In, Sungchul Kim, Ryan A. Rossi, Mehrab Tanjim, Tong Yu, Ritwik Sinha, Chanyoung Park. Diversify-verify-adapt: Efficient and Robust Retrieval-Augmented Ambiguous Question Answering. NAACL 2025, Volume 1: Long Papers, pp.1211–1238.** 方法简称是 **DIVA**，不是 DVA。

官方页：https://aclanthology.org/2025.naacl-long.56/；PDF：https://aclanthology.org/2025.naacl-long.56.pdf。

正文 §3.1 的目标是回答原问的**所有 plausible interpretations**，并组织综合响应。§3.2/Table 7–8 先推断 AmbSub/AmbObj/AmbPred/AmbTime/AmbLoc 与具体 disambiguated pseudo-questions：例如分别改写成 men's/world-cup 和 women's/world-cup。这已经覆盖“补入时间/地点/主体限定条件形成候选查询”，不能笼统当作空白。

| 流程 | 证据 | 是否已有 |
|---|---|---|
| 获得初始候选语料 | §3.2、A.4.1 | 依据原问使用 ColBERT 与 Bing 收集候选 `Ci` |
| 按各 pseudo-interpretation 条件化检索 | Eq.(4) `R(Ci,q̂ij;K)` | 有，但明确针对已有 Ci 的检索/排序，而非 verifier 失败后动态扩展全语料 |
| 去噪与固定最终 Pi | Eq.(5)、Algorithm 1 行3–8 | 对 pseudo-questions 平均相关性，选 top-K |
| 验证 | §3.3 Eq.(7)、Table 9 | 每个 q̂ 与同一 Pi，判断“passages contain the answer? Yes/No” |
| 质量分类 | §3.3 | Useful/PartialUseful/Useless，是解释覆盖程度，不是每条 binding 的 supports/refutes/unknown |
| 验证后主动补查新条件/新检索？ | Algorithm 1 行14–18；A.4.2 | 没有。Useful/PartialUseful 时用 Pi 生成；Useless 时走 closed-book LLM |
| 槽位修复与 DAG 版本/后代重放？ | 正文 §3.1–3.4、Algorithm 1、附录 | 未定义这种状态/控制流程 |

**最准确差异**：DIVA 的条件化多解查询在验证前生成，用于多解释覆盖；本研究候选动作在局部绑定失败或缺证时生成，目标是补足原问已存在而尚未证实的条件。二者可共享查询技术，不能把泛化“主动消歧”叫作新颖。

本次已读 DIVA 正文、Algorithm 1、Appendix A.3/A.4、B.1/B.2、C、D 全部 relevant prompts；没有取得或审查 DIVA 官方代码仓库，因此上述否定范围只限论文方法定义。

## 4. 最接近的五项先例

| 文献/正式来源 | 真正重叠 | 目前仍可检验的局部约束 repair 差异 |
|---|---|---|
| **BeamAggR / ACL24**：https://aclanthology.org/2024.acl-long.67/ | 答案候选、Cartesian product、填槽后多源检索、概率聚合；已有beam=2和greedy变体 | 补查的是原问 binding predicate，而非继续延伸候选分支；明确的 binding/支持版本失效状态 |
| **ReAgent / EMNLP25**：https://aclanthology.org/2025.emnlp-main.202/ | 不仅矛盾后回滚：附录 C 已有四竞争假设、checker并行一致性测试、反证淘汰；正文还有关联 qi 局部重查 | 不能再以“我们先保留多个候选、它只事后回滚”区别。需要证明 missing predicate 的选择与局部绑定修复动作更有效；源码未核验 |
| **CIRAG / ACL26**：https://aclanthology.org/2026.acl-long.1203/ | 多候选 triples、历史条件整合、多链和出处映射、证据充分性级联 | triple集合整合与 parent binding constraint 执行接口不同，但原问约束本身也在其整合器中保留；不能只说更关注原问，需给明确动作消融；源码未核验 |
| **DIVA / NAACL25**：https://aclanthology.org/2025.naacl-long.56/ | 时间/地点/主体等候选解释、条件化查询、验证和适应生成 | 方法定义没有“验证失败→针对尚缺绑定谓词再次检索→修复局部断言”的闭环；真歧义全覆盖与唯一问句错绑修复是不同任务 |
| **End-to-End Beam Retrieval / NAACL24**：https://aclanthology.org/2024.naacl-long.96/ | 每hop保留多条 passage hypotheses；学到的全程相关性评分和多跳拓展 | passage序列与实体绑定状态不同；它主要在固定候选set选择上下文。官方代码没有missing-predicate查询生成动作；不应把它说成单步文档检索 |

### Beam Retrieval 官方代码审查

PDF第一页明确给出 **https://github.com/canghongjian/beam_retriever**，本次成功从这个地址取得公开实现，固定 commit **902980bfb5bd47a963569ab9c3621fd5ae81204a**。没有凭名字猜地址。

已读 README、`retrieval/retriever_model.py` 的模型/forward及beam扩展部分。`current_preds`保存的是 passage index序列；第一hop选top beam，后续对各partial sequence拼接剩余候选paragraph，再分类并选top beam。编码器+两个分类头经过监督训练；不是一个冻结LLM为候选实体补查原问条件的执行器。README的fullwiki路径也描述使用MDR候选数据再进行reranking，不能将其主要候选阅读理解实验数字与本仓库全语料在线检索直接比较。

未运行其训练、权重、reader实验；未把源码全文、所有脚本与结果文件逐行审查。读到的范围只能支持 passage-hypothesis scorer/beam控制的结论。

## 5. 其他正式候选与搜索结果边界

- **Eliciting Critical Reasoning in Retrieval-Augmented Generation via Contrastive Explanations（C-RAG）**，Leonardo Ranaldi, Marco Valentino, André Freitas，NAACL2025 long：https://aclanthology.org/2025.naacl-long.557/。已读正式PDF §2、§3.1–3.5：先按query检索文档，再从固定文档抽取/比较相关与不相关要点，构造对比解释并输出答案；同时支持GPT-4 prompting及合成解释指令训练。所核验流程没有基于missing binding predicate生成新query并再检索的动作。它证明对比原文判读/对比解释早已有，差异不能落在“让模型比较A/B”本身；源码未核验。
- **CondAmbigQA: A Benchmark and Dataset for Conditional Ambiguous Question Answering**，Zongxi Li, Yang Li, Haoran Xie, S. Joe Qin，EMNLP2025 main：https://aclanthology.org/2025.emnlp-main.115/。强调 conditions 作为明确上下文约束以消解不同解读；可用于区分“真歧义”与“错绑定”，条件概念本身不是新颖点。已取正式正文/附录，核心结论与摘要一致。
- **HyKGE**，Xinke Jiang 等，ACL2025 long：https://aclanthology.org/2025.acl-long.580/。用 Hypothesis Outputs 扩展KG探索方向与片段粒度rerank，医学语境；正式摘要给出 https://github.com/Artessay/HyKGE。本次未审查代码，不据摘要断言它有/没有本方案完整修复机制。
- **SeaKR**，Zijun Yao 等，ACL2025 long：https://aclanthology.org/2025.acl-long.1312/。以内部状态不确定性触发检索、重排并选择推理策略；说明“风险触发局部检索”已有，不能把不用全面beam本身当作新颖。
- **Speculative RAG: Enhancing Retrieval Augmented Generation through Drafting**，Zilong Wang 等，ICLR2025 Poster：https://openreview.net/forum?id=xgQfWbV6Ey。正式 venueid=ICLR.cc/2025/Conference；并行小模型从不同检索子集产生draft，大模型单轮verify。此次核验官方submission/abstract，未深读PDF/代码；因此不能据其概要排除某种完整candidate-binding能力。
- **Chain-of-Retrieval Augmented Generation**，Liang Wang 等，NeurIPS2025 poster：https://openreview.net/forum?id=gUPGGCM4WH。动态query reformulation、rejection-sampling训练retrieval chains，测试时可改变链长/采样数。正式接收状态已核验，但此次只读摘要，不用它作精确源码差异结论。
- **TeleRAG**，Chien-Yu Lin 等，MLSys2026：https://openreview.net/forum?id=YsOyCpMUYD。其lookahead retrieval是CPU→GPU数据prefetch，与缺失语义binding的检索动作不是同类；不能仅因lookahead一词纳入语义创新查重。
- **Tree of Clarifications**，Gangwoo Kim 等，EMNLP2023 Main：https://openreview.net/forum?id=vDvFT7IX4O。正式身份可核验，但窗口外；DIVA以它为iterative ambiguity baseline，所以“迭代澄清树”有更早先例。此次不将其计为2024–2026新文献。

搜索通过已保存的官方 ACL/NAACL/EMNLP/EACL XML全文title/abstract及OpenReview官方搜索API，关键词含 ambiguity/disambiguation/contrastive/hypothesis/lookahead/candidate。主会/正式长文与被拒/withdrawn/ARR/Workshop状态区分；没有把API搜到的预印本或相似标题当正式会议文章。搜索是定向而非穷尽；尚未逐一阅读所有候选、Findings、学科消歧论文、历史源码，因此不能得出“没有任何先例”。

## 6. 必须能分离的实验

同一初始错误绑定、候选集、模型、语料和硬预算下，至少比较：

1. **继续分支**：`child_question(candidate)` 普通检索/回答，BeamAggR式概率或频次聚合。
2. **一般重新检索**：对父问题或原问题普通top-k检索，确保收益不只是第二次检索。
3. **通用冲突checker**：同候选/证据，ReAgent式一致性与反证测试，明确标算法适配。
4. **定向 binding predicate repair**：从原问抽出尚未得到原文支持的绑定条件，查询这个条件，而非派生目标属性；按 supports/refutes/unknown更新局部绑定；承诺后才进入子节点。对已执行节点的实际依赖重放不纳入MVP，避免把已有回滚机制误当新增主线。
5. **成本匹配**：相同总LLM、HTTP尝试、retrieval/rerank、输入/输出tokens；同时画实际成本前沿，报告失败与正确→错误损伤。

中间评测直接衡量：wrong-binding检出率；missing predicate选择正确率；针对查询的原文命中率；修复正确率与误修正确绑定率；原問条件完整率；最终EM/F1；unresolved/真歧义错误压单率。原文未命中只能是unknown，不能当反证。

若动作4只胜出动作1、却不能超过等成本动作2/3，则主价值可能只是更有效的query rewriting或协议可靠性，应该按该真实结果定位。若原问条件提取/绑定核验本身不稳，应先止于诊断，不扩大beam、图模块或训练代理。
