# ReAgent / CIRAG 最近机制核对与路线收敛

核对日期：2026-10-02。范围：两篇官方论文正文、附录及其公开仓库当前提交的静态代码。没有执行公开仓库、外部模型或读取凭据；代码观察不等于论文结果复现。本备忘录供主报告整合，不覆盖其他 agent 正在查阅的 RAFTS、Contrastive-RAG、KG-CRAFT、BeamAggR、Beam Retriever 等近作。

## 核心结论

此前的“原文三值判别 + 定向区分查询 + 共享祖先一致性”不能直接作为三个独立创新点。原文支持/反驳判断已有大量事实核验先例；多假设接地不能绕过 BeamAggR；ReAgent 既有冲突后回滚，也有 controller 请求额外证据，附录甚至提前枚举四个假设；CIRAG 已根据历史事实与原问题的信息缺口生成 targeted query。共享祖先的一致赋值与依赖失效更接近正确运行多分支 DAG 的状态条件。

较值得保留的是一个**检索动作选择问题**：当现存竞争候选可能改变必要终末答案时，有限预算应检索哪个原问题约束，才能区分这些候选？核心比较是“面向现存候选差异的检索动作”对“普通信息缺口查询”及“同预算增加搜索宽度”的增量，而不是多种状态工程的组合。

这个差异只是待验证的研究假说。ReAgent/CIRAG 中没有发现开放语料上明确优化现存竞争假设之间区分信息的机制，不足以证明所有近期工作都没有这种机制；主报告仍须整合图对比查询、反证检索等近作，必要时进一步收窄或否决路线。

## 来源与复核状态

| 工作 | 官方来源 | 本地材料与版本 | 本次确认 |
|---|---|---|---|
| ReAgent: Reversible Multi-Agent Reasoning for Knowledge-Enhanced Multi-Hop QA | EMNLP 2025 main，[官方页面](https://aclanthology.org/2025.emnlp-main.202/) | `tmp/research/sources/2025.emnlp-main.202.pdf`、同名 `.txt`；[官方仓库](https://github.com/astridesa/ReAgent)，提交 `31c3d9f4ad72846a6cb8c2cc1a4e34dba91cea84`，2025-10-01 | 正文 §4、Appendix A.6 / C；Algorithm 2 已渲染检查，PDF 第19页 / 印刷4085 |
| CIRAG: Construction-Integration Retrieval and Adaptive Generation for Multi-hop Question Answering | ACL 2026 long，[官方页面](https://aclanthology.org/2026.acl-long.1203/) | `tmp/research/sources/2026.acl-long.1203.pdf`、同名 `.txt`；[官方仓库](https://github.com/52566rz/CIRAG)，提交 `d78caa0d1e958814212fc59bfae777b1aac22718`，2026-01-29 | 正文 §3.3 / §3.4 / trajectory distillation、Appendix Fig.11 / 12；末页已渲染检查，PDF 第17页 / 印刷26197 |

视觉核对文件：`tmp/research/nearest_code/reagent_appendix-19.png`、`tmp/research/nearest_code/cirag_appendix-17.png`。正文 PDF 的章节/图号是主要引证；提取 txt 因版面和空字符而有行号变化，不作为稳定公开引用。

## ReAgent：不能压成“只有冲突后的被动回滚”

### 论文机制

正文 §4.1–4.4 的主机制是局部/全局非单调回滚。各 agent 保持知识集，Verifier 检查新证据与既有事实的相容性；Supervisor 对跨 agent 冲突回退，正文还提出 minimal conflict set 的 SAT 条件。§4.1 明确写：失效证据只使关联 subquestion 重新检索，而不重查其他子问。§4.2 的 controller 可以 challenge 关键断言，从其他 agent 视角重新检查。

附录 A.6 的 controller prompt（PDF 第17页 / 印刷4083）要求“Challenge or confirm critical assumptions by requesting additional evidence or verification”，示例进一步请求“additional sources or alternative cross-checks”。因此，“会要求额外证据”“只回查受影响局部”已高度重叠。

**更重要的是 Appendix C Algorithm 2（PDF 第19页 / 印刷4085）**：初始化枚举 `{H_A,H_B,H_C,H_D}`，每个 checker 负责一个假设，假定某人是 culprit 后检查 statements 的一致性；发现矛盾则弃掉对应假设，最后保留唯一一致者。它不是先固定一个答案、出错才想起另一个答案。不能声称“首次提前维护竞争假设并通过下游一致性排除”。

仍可精确区分的边界：这个附录例子是封闭 puzzle，假设集合与待查 statements 已给定；它没有定义开放语料中哪个新检索动作最能区分两个现存候选，也没有为这种动作选择建立预算受限目标。其公开 multi-hop QA 主算法以冲突信号与 controller challenge 为主，未见明确定义候选间区分收益的查询策略。应表述为本次核对的机制边界，不能扩大成“ReAgent 没有主动验证”。

### 当前公开代码的复现边界

| 静态观察 | 代码位置 | 能支持的结论 |
|---|---|---|
| `decompose_question` 明写 placeholder，返回三个模板子问 | `ReAgent/Agent/agent.py:126–135` | 当前文件中该方法不是论文的模型分解实现 |
| `retrieve_evidence` 明写 placeholder，返回 `Sample evidence for: ...` | `Agent/agent.py:168–173` | 当前文件中该方法没有实现论文的 sparse+dense+RRF 检索 |
| verifier 用 `len(set(combined)) < len(combined)` 检测重复字符串，返回“repeated or contradictory” | `Agent/agent.py:216–224` | 该方法不能代表论文语义一致性核验能力 |
| 六种执行/监督角色全部实例化 `BaseAgent`；它的 receive/run 方法是 `pass` | `main.py:52–58`；`Agent/agent.py:66–71,89–94` | 这一构建入口没有连接专门 agent 的执行逻辑 |
| environment 有状态 snapshot 与 revert | `Environment/environment.py:90–124` | 回退状态容器是真实实现，不能把全仓库称为空壳 |
| conflict resolver 自称 example，默认退至前一个存在 checkpoint | `Environment/environment.py:135–153` | 这里没有实现正文所述 SAT/minimal conflict set 求解 |
| `BlackSheep / Thinker / Human` 继承 `Agent`，文件类清单中未定义或导入 `Agent` | `Agent/agent.py:344,407,466` | 静态发现入口/命名不一致；未运行，不宣称具体运行报错 |
| 当前演示入口使用 Moderator2 的 CoT 与投票修订 | `main.py:135–163` | 不能确认该演示等于完整论文检索管线 |

由此，实验基线应命名 **ReAgent-paper 同模型适配**，保留验证、局部/全局回滚、controller challenge 等论文机制，并公开适配范围。不要把占位的官方文件当作弱基线，然后宣称超过了 ReAgent 论文。若以后完整运行官方代码，复现结果应单列。

## CIRAG：已经有 targeted gap query，但不是显式竞争候选控制

### 论文机制

§3.3 的 construction phase 检索与提取 triples；integration phase 使用 original question、当前候选 triples 与历史 reasoning/triples/queries，保留 core triples 并输出下一轮 query。正文明确说模型识别 information gaps，形成 targeted query。Appendix A.2 Fig.11（PDF 第17页 / 印刷26197）再次写：不能解原问题时，分析还需什么信息并提出新问题。故“定向补信息缺口”本身不是可保留的创新。

它还强调原问题锚定与多条 plausible chains，不能把它说成只盯一个实体、没有全局一致性。实际形式化状态是累积集合 `C ← C ∪ core triples`，及相应 sentence/document 的单调并集；未看到显式互斥的答案 slot assignment、版本化祖先赋值与分支依赖失效图。事实池中可以同时含多个实体，隐式多链不等于显式候选分支，但二者是否造成有用差异必须靠实验。

§3.4 的 adaptive cascade 是 triples → sentences → documents。其 sufficiency indicator 检测模型答案是否匹配预设拒答模板，未拒答就算 sufficient。它是模型的自评/拒答机制，不是语义充分性证明。§3.5/训练部分还有 trajectory distillation；同冻结模型适配与论文 distilled student 的训练条件不能混成一个结果。

### 当前公开代码

| 静态观察 | 代码位置 | 含义 |
|---|---|---|
| 单个 `query1` 串行运行至 `<no question>` 或迭代上限，每轮 dense top10、history-conditioned facts filter | `CIRAG/src/cirag/CIRAG_llm.py:734–772` | 已有历史驱动迭代与补缺口；未见显式答案假设 branch DAG |
| history 保留每轮候选与 thought/filter/next-query，core facts 去重追加 | 同上 `:758–771` | 不是无历史的逐跳贪心，且可隐式保存多个候选 facts |
| facts 映射回来源句子使用词重合启发式 | `CIRAG_llm.py:775–813` | 保留原文来源路径，但这里不等于精确 span 的支持/反驳验证 |
| 向量候选 top200 再受 dense passage 限制至10；过滤空时补新fact，thought三元组使用 cutoff=0 的近似匹配补fact | `CIRAG_llm.py:3004–3098` | 公开实现包含启发式保留与模糊归属，适配需披露，不可当精确引用核验 |
| filter system 明写 **“The information contained in the facts is absolutely correct.”** | `src/cirag/prompt/prompts/filter.json:45` | 这套公开 prompt 主要做相关性/缺口整合，未显式要求对源文本的支持、反驳、未观察三值检查；论文 Fig.11 没有此句 |
| `No answer` 触发从 triples 升至 sentences，仍不足再升至 passages，最后 reanswer | `CIRAG_llm.py:1647–1737`；`CIRAG.py:1652–1721` | 公开代码与论文拒答级联思路一致；“没有拒答”不能被当成证据真充分 |
| 模板加载仍引用 `src.hipporag.prompts.templates` / `hipporag` | `prompt/prompt_template_manager.py:59–69` | 复现时需核对命名与依赖；未运行，不宣称故障 |

源代码接口另有待复现核对点：`CIRAG.py:1110–1175` 的 passage fallback `zzzqa_copy` 优先 facts 对应原文、原问 dense top5 补满，返回 `(pred_ans, top_k_docs)`；其调用点把结果继续交 reanswer，需核对实际模板/类型约定。该点只标记复现风险，不能用它否定论文性能。

更有意义的比较是：相同候选与预算下，CIRAG 风格的“还缺哪一事实才能回答”查询，与“现存 A/B 哪个满足原问限定条件”查询各自找到什么证据。所谓判别查询不能只是改个 prompt 名字；需要证明它改变了检索的内容，并带来终末正确性增量。

## 对原方案的具体批判

1. **“未知”必须是观测边界。** 未检到反例不是支持，也不是反驳。三值应作用在 `(原文证据, 具体候选, 原问约束)` 上：原文支持、原文给出不相容事实、当前原文未决定。预算未看、映射失败、候选池没有正确实体，均不能被硬判为反驳。
2. **来源间矛盾不能强压成单一标签。** 每条原文可分别 support/refute/unknown；若两种证据都观察到，聚合状态应保持 conflict/待解，而不是看计数投票。来源语境、同名实体、时间、版本、国别等 scope 没核准时，表面矛盾也可能不矛盾。
3. **支持数与链长不是候选真实性。** 一个错误祖先可诱发一条更完整、更多来源的自洽链。联合优化若仍奖励“延长链/补足节点”，容易再次偏向可检索的错误实体；只能用原问题约束及对应原文决定分支是否适用。
4. **共享祖先一致性主要是必要条件。** 汇合路径不得把共享祖先从 A 悄悄换成 B；版本失效要阻止旧子结论进入新路径。这解决混支污染，却不能判断 A 是否真实。禁止混支的实现应作为所有显式多分支强基线的共同条件；“去掉一致性”只适合诊断消融，不能成为主要竞争者。
5. **多候选与回滚已有强重叠。** ReAgent puzzle 已枚举假设，BeamAggR 已多答案聚合；把单值节点改成 K=2 是支撑动作选择的状态表示，不宜独立包装成新机制。
6. **终末敏感度不能偷用 gold。** 在线 gate 可用冻结问题依赖、原问必要条件、候选替换后是否可能改变当前终末假设等可观测量；这是近似值，不是已知真实因果效用。终末仍未解时不能凭空断言“两个候选最终答案相同”。离线 gold/oracle 可估计上限，必须与在线策略隔离。
7. **两个候选都合法时不应制造区分约束。** 区分查询只能针对原问题要求，或原文明确的实体消歧条件。若候选都满足要求、原问本身有歧义，或没有可观察区分原文，保持未决/停止；不能添加用户未要求的年代、地点或唯一性假设来挑一个。
8. **正确候选缺席时该机制无解。** 排除两个错误候选并不自动找到真候选。候选覆盖率与正确答案可达率必须先测；显式分列“正确候选已出现”的条件收益和全任务收益，后者才是主结论。

## 推荐的单一路线

暂名“终末相关的候选区分检索”。保留老版 DAG 的全语料接地查询与 reader 作为起点，不全面迁入新版 mapping/audit/selector，也不同时把链校准写成另一项主贡献。

最小状态只保留少数歧义节点的 `K=2` 竞争赋值、各自出处与 scope，以及依赖它的路径。原来的同结论 OR 支持仍与答案候选 OR 区分。共享祖先版本一致是基础正确性要求。候选生成可并入现有节点 resolver，但若另用模型调用，必须计费。

最小动作是：选择一个原问中尚未判定、且候选可能不同的必要约束；生成指向该约束与相关候选的查询，检索后根据原文更新两候选的证据状态。例：问题指定某同名电影在某年上映，A/B 指向不同作品，查询它们的作品身份与上映时间；不能仅分别问两个候选“导演是谁”后选链更长的一边。一次动作若包含两个候选定向子查询，应算两次 ANN，不能因包在一个 Python 函数里当一次。

触发 gate 只考虑预计会影响必要终末答案/证据路径的候选；无影响或原文已经确定的节点不加动作。只有模型不确定性也不够：一个困惑但与终末无关的节点不应消耗主预算。在线策略以可观测的约束未决、分支差异、必要依赖和检索可达性作启发式；若不能给出可靠的差异或可检索约束，就停止或按已有路线处理，避免扩展成一般搜索 agent。

需要验证的主假说只有一个：**在同候选池、同模型与相同额外成本下，把下一条查询用于现存候选之间的原问约束差异，能比普通 gap query 更有效地修复终末答案。** 三值检查为这个动作提供可审计反馈，依赖图提供触发与失效边界，都不单列成主贡献。

## 强基线与最低因果实验

| 基线/控制 | 必须保留的能力 | 排除的混杂 |
|---|---|---|
| 老版同模型 DAG，单候选 | 全语料接地查询、原reader与原链协议 | 确认基本收益和改动成本 |
| 同候选的 best-of-K / BeamAggR 同模型适配 | 多答案、证据接地、聚合；显式 branch 时共享祖先一致 | 区分动作选择收益与“多保留一个答案”收益 |
| ReAgent-paper 同模型适配 | 局部/全局核验回滚、critical assertion challenge、additional evidence / cross-check | 不靠弱化成纯被动回滚赢基线；官方当前代码结果另列 |
| CIRAG 同模型冻结适配 | history-conditioned filter、original-question anchoring、gap query、triples/sentences/docs cascade | 与最近的缺口查询/多粒度机制正面对比；distilled论文配置另列 |
| 普通 gap-query，完全相同候选 | 使用同样history与原问题，指出回答还缺何信息 | 主对照：是否真需要显式候选区分目标 |
| 相同候选 + 等预算额外普通检索/更多宽度 | 相同额外模型token、ANN次数与文档额度 | 排除只是“多花一次查询”或“检得更宽” |
| 同判别动作，提前触发 vs 冲突后触发 | verifier相同、总预算相同、候选相同 | 区分触发时机与查询内容；不把ReAgent描写为完全没有提前challenge |
| uncertainty gate vs terminal-related gate | 相同动作产生器与总额度 | 验证终末相关门控的附加价值；不是另开大研究主题 |

优先做两阶段，而不是一次端到端全改：

- **冻结候选池的机制试验。** 每题先生成同一候选状态，所有 arms 共用；在有分歧的自然样本上比较普通 gap query、候选区分 query、等预算额外普通 query。候选构建成本应报告并计入端到端估算。冻结原问/必要条件，禁止使用gold决定触发、挑查询或删候选。
- **端到端试验。** 只有机制试验出现可信增益后，接回老版候选产生器；共同模型/向量、共同语料与 reader 预算，报告全题EM/F1、rescue/harm、每题成本。若候选池控制有收益但端到端消失，先检查候选覆盖、trigger precision与查询检索失败，不用选择器/reader新改动掩盖。

每条新动作记录：候选差异、原问约束、查询、返回文档、原文证据标签、状态更新、是否改变必要路径/答案、全部成本。离线诊断包含正确候选覆盖、支持/反驳判别错误、两候选均错误、两候选均合法、未发现区分证据、错误剪枝、增加查询但终末不变等类别。

成本按实际模型输入/输出token、ANN次数、reranker次数、文档读取与端到端时延共同报告。候选提取、query生成、原文判别、受影响节点重放、最终reader均计入；若约束“额外两次调用”，这些步骤必须共享或省去调用，不能把候选提取/重放免费藏到前处理。检索深度与模型调用不能互相充作相同成本。

oracle 只放离线附表：正确候选在池条件下的覆盖上限、可判别原文确实在已发现池时的上限、完美判别器上限应分开。不能让 oracle 选候选或查询再称在线可用。发现池没有统一排序时只报告集合coverage；不要称发现 R@k。Reader 消融必须使用共同可行的固定原文选集和真实模板token预算。

## 继续 / 否决标准

若显式候选区分检索在相同候选、预算和判别器下，仅比单候选强，未优于普通 gap query / 多搜索宽度，贡献仍主要来自保留候选或增加计算，不足以支撑这条路线。

若收益主要来自更严格的原文核验，而查询内容没有实际差异，应把论文问题改成稀疏验证，重新与事实核验/反证检索对比，不能继续沿用“判别查询”名称。

若候选覆盖上限低、自然分歧样本很少、主收益只存在于人工错误注入，先做失败机制分析，不把受控诊断当自然基准主结果。若图对比查询近作已覆盖“候选差异→有区分力检索”的核心，应将本路线降为强基线适配或停止，不再靠三值标签与祖先版本工程增厚新颖性声称。

