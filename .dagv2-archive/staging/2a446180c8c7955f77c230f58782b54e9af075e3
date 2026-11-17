# 老版 DAG v2 代码核读与创新起点

核读日期：2026-10-01。本文的“老版 DAG v2”特指 README 定义的 frozen non-thinking v6；`package/` 是它复用的 DAG v1 冻结核心，不能把 package 中未被 patch 的默认控制器当成老版 DAG v2 的实际行为。本文仅用于报告输入，未改产品代码。

## 1. 版本与证据边界

对 `original_manifest.json` 中下列 13 个关键文件逐字节计算 SHA256，全部 MATCH：README.md、dagv2/experiment.py、experiment_v6.py、frozen_flow_v6.py、两 pipeline、repair_planner.py、package/core.py、frozen_flow.py、reader.py、run.py、metrics.py、results/METHOD_CARD.md。关键哈希为：

| 文件 | SHA256 |
|---|---|
| dagv2/experiment.py | e3af184e3baa42bc57ae549c588b5344ab4b1cfde98fef2b3a21d318b8290a25 |
| dagv2/frozen_flow_v6.py | 957a6a964218a421f032387ceefe24162e7dc85da468d9b28a15b823c5cdebb0 |
| package/core.py | 4cad8b1b48400806470f64dfd958fef7a39e62573cd400034ddcfe16798a98bb |
| package/reader.py | ac637306b4b63e48571773f1a40a1e47ec6908e6801322031d903d20518d26cb |

因此本次老版分析没有混入新版 dagbt 的修改。仓库的 `results/RESULTS_*.md` 和 METHOD_CARD 是源服务器导出的汇总，不是本机重新运行结果；本机 outputs 的 summary 主要是 verification / scripted 测试输出。未发现支持本次重新复算老版全 1000 题消融的原始 full1000/rows，所以本文把成绩和消融明确标为方法卡发布值，不虚构新增实验。

实际入口是 `dagv2/pipeline_dagv2.py:21` / musique 入口 `:22`，先加载 experiment_v6；patch 在 `experiment_v6.py:21–24` 替换 controller、reader_input、chat_request、native.solve。`experiment.py` 的直跑 main 仍有旧 thinking 元数据、旧数据布局和 DAG v1 报告标题（:101–135、:227–255），分析实际运行须跟随 pipeline，不能仅看它的 main。

## 2. 实际数据流

1. **问题驱动一次规划**：`experiment.py:41–53,138–149` 用原问题规划 1–6 步 JSON，temperature=0；步骤包含 question/output_slot/answer_type/inputs，planner 无 thinking、最多 2048 tokens。validator 保证唯一 slot、前向依赖合法、引用已有 slot；把声明 inputs 和文本中占位符做稳定并集（:68–98）。它没有验证原问题所有约束得到覆盖、最后节点确实回答原问题，或每个非终端节点是否被最终节点使用。尾注修复只删除当前 output_slot 的尾部 `{slot: X}`（repair_planner.py:16–35），不改语义。
2. **预档案池**：`experiment.py:152–171` 对原问题及各步问题检索全语料 dense top50；占位符被替换为 `the unknown entity`，查询去重，然后按原问题优先、步骤顺序稳定并集。原问题 query 在填补剩余选文档时有稳定优先权。没有 BM25、cross encoder 或全局 relevance 聚合。
3. **逐节点 grounding**：`package/core.py:17–27` 对 resolved 父节点用 answer 替换占位符；未 resolved 父节点用括号包裹的父问题代替答案；若 inputs 没有出现在问题里，追加 `slot: value`。`ordered_steps` 用 TopologicalSorter（:11–14）；“最后已解析节点就是最终答案”没有显式 target_slot 约束。
4. **全语料检索与面板**：`frozen_flow_v6.py:22–54` 给接地问题算 embedding，用全语料矩阵 dense 排序，top50 并入池，top20 形成面板；**父节点继承的是 source_doc_ids 的直接引用，不是 closure_doc_ids 的全闭包**（core.py:30–34）。README “优先父引用闭包”不完全准确。若父直接来源多，20 篇上限会挤掉新的检索 hits；没有给 fresh evidence 保留最低份额。
5. **单次作答并勾选来源**：节点提示 core.py:37–58 要求父答案可错、只使用证据、勾选所有必需多篇；schema/decode 只校验 answer 字符串、长度等于面板的 bool 数组（:61–77）；v6 单调用 guided JSON，512 tokens、无 thinking（frozen_flow_v6.py:55–80）。answer_type 虽存在于 plan/state，却不加入节点 messages 或 schema；方法卡说明此前 answer_type 强约束两种路线已判负。
6. **“resolved”和证据闭包**：core.py:80–87 只判断 `bool(answer.strip() and sources)`；resolved 子节点闭包 = 自己勾选来源 ∪ 所有 resolved 父节点闭包。这是来源集合追踪，不是事实蕴含证明。没有检查引用确实支持答案、正确实体/关系、所有必需父节点 resolved，也没有记录实际使用了哪个父结论。因此会同时出现“错误父答案被无条件继承”与“未解父节点被跳过，子节点却 resolved”。
7. **预算选文档**：core.py:90–114 对 n≤6 个 resolved 节点闭包枚举所有子集，最多 64 种并集；对每个 k=5/10/20，保留文档并补足原始 pool 前列，目标最大化完整包含的节点闭包数量，平局按池中索引元组偏好。它没有区分终端和辅助节点、没有事实可信度权重、没有 token 成本，更不会反向利用预算不足引导重检索。k 三组独立优化，不保证嵌套。
8. **Reader 接收 20 篇文档和全部 resolved 链**：frozen_flow_v6.py:87–101 把每个 resolved 节点注入 lineage，source_doc_id **仅取其第一勾选来源**，source_span 为空；不检查节点完整闭包是否包含在实际 selected20。提示“final state answers question，start from it，只有原文清楚反驳才改答”。这增加链尾锚定倾向，而不是独立验证。Reader 原提示 core reader.py:45–82 要求最短短语，并说明 guide 不是新来源；最终非思考 1024 tokens（v6:104–107,110–124）。
9. **标签与评分**：pipeline_dagv2.py:83–118 要求保存全部 1000 行、ID 集合匹配后才读 evaluation_only；使用 token F1/EM 与 gold title-group recall（匹配组内任一文档即命中），all@k 要求所有组命中。MuSiQue 在 :102 归一化 `musique:` 前缀。selected k=5/10 仅用于检索指标，最终答案只读 selected20；不能把 F1 解释为 5 篇预算结果。

## 3. 已有成绩和可据此定位的问题

| 数据集（本地子集，各1000） | 旧v2 F1 | EM | R@20 | all@20 | DAGv1 F1 | 链尾直出F1 |
|---|---:|---:|---:|---:|---:|---:|
| HotpotQA | 79.83 | 67.00 | 99.25 | 98.80 | 82.91 | 71.82 |
| 2Wiki | 80.34 | 72.90 | 97.90 | 96.80 | 75.94 | 78.70 |
| MuSiQue | 64.66 | 54.50 | 89.76 | 75.00 | 66.86 | 57.97 |

证据来源：results/RESULTS 三表、METHOD_CARD:全量成绩/对照/消融（文件均通过 original_manifest 哈希）。这些是局部1000题，不是官方全 dev；模型是 Qwen3.8-27B-AWQ-INT4 + NV-Embed-v2，不可直接与论文不同模型/语料/全集的数字排名。

方法卡披露，终末已解析时 Reader 有87–99%逐字复制链尾（2Wiki 99.4%）；Reader 相比链尾直出增益分别 +8.01/+1.64/+6.69 F1。这说明终端节点错误传播和答案格式归一是首要入口。HotpotQA 的 all@20=98.8%而 F1=79.83%，**按已有支持组指标**，证据组缺失未必是主要瓶颈；不能据此断言所有读到的证据都充分/正确，title-group 命中并不验证关系事实。MuSiQue all@20=75%，则完整多跳证据缺失更可能值得单独排查。R@20 是按题宏平均 gold group recall，不能把它当作答案成功率，也不能从汇总直接求出“检索成功但回答失败”的确切题数。

## 4. 代码上明确存在、但尚未测量发生率的失败机制

| 机制 | 代码证据 | 可检验诊断 |
|---|---|---|
| 第一跳猜错后硬提交 | ground替换单一parent answer；state只有单值 | 人工标注桥实体错误，统计下游受影响率；以相同文档下替换正确桥实体作离线诊断，不能把该oracle输入当正式方法 |
| 引用存在被当作事实成立 | resolved只看非空+勾选 | 精确引文+独立实体/关系支持判读，对比citation precision与answer accuracy |
| 断开的父证明被误当完整链 | unresolved父被括号问题替代；closure只继承resolved父 | 统计resolved子节点含unresolved必要父的比例、完整依赖链通过率 |
| 面板遗漏祖先证据/新证据被挤出 | source_panel只取父direct sources且硬截20 | 比较direct-parent / full-closure /保障fresh quota的面板组成及F1 |
| 选文档偏好多个便宜节点而非目标 | select_sources等权计所有proof | 终端闭包可行但未入选率，terminal-conditioned选集的F1与all@k |
| 链证据对Reader不可见却仍被注入 | reader所有resolved，无selected过滤；第一source且空span | 全链/visible-chain/无链/原文反证 四臂，测错链服从率与正确链背叛率 |
| 最后状态不必是真正终端 | 无target_slot且TopologicalSorter排序，不做语义终端检查 | 计划中未被终端用的节点、末节点与问题关系不一致率 |
| 解析失败导致整题弃答 | v6:70–77任何node_finish或decode错误break，solve:120–123不跑Reader | 将格式错误与语义未解拆分；保留原题+已检索证据Reader兜底的净增益与代价 |
| 固定检索/生成成本 | 每步均full retrieval+节点调用；前置档案池也对每步检索 | 以支持缺口为触发的检索/重求解，等LLM/ANN成本比较；最坏n=6有≤13次archive+node embedding查询（archive去重后更少） |

注意：flow.prepared 的16384断言（package/frozen_flow.py:65–70）原先同时预留输出tokens；v6节点与Reader调用都传False,0,0（:55,:101），因此只检查prompt+8。报告可将其视为预算口径不一致的工程问题，而不能声称它已解释模型精度下降。

### 三个无模型的源码反例

我直接载入未经修改的 package/core.py 运行了以下构造；它们验证程序语义，不代表真实评测题的发生频率。

1. parent未解、answer=''、sources=[]；child依赖parent且回答1900、勾child_doc。`node_state`仍返回 `resolved=true`、closure=[child_doc]。
2. parent的direct=[direct]、closure=[grandparent,direct]，pool=[grandparent,direct,fresh]、retrieved=[fresh]。source_panel(k=3)返回[direct,fresh]，丢掉grandparent。
3. 六个resolved proofs分别为[a]、[b]、[c]、[d]、[e1,e2,e3,e4]、terminal=[e1,e2,e3,e4,f]；k=5时终端proof可行，但select_sources返回[a,b,c,d,e1]，保留4个非终端proof，未保留终端。此例对应合法但含无用分支的plan；它特别说明终端识别与选择目标须联合设计。

## 5. 从老版出发的增量创新建议

以下是研究假设，不是已验证收益；是否能称为新颖方法需与近期论文定位交叉核对。与负责新版核读的agent已核对：新版已实现精确span、actual-used-parent的AND/OR support routes、supported才grounding、冲突局部失效/重求解、最多2个细化、必要终端覆盖优先、预算/公平份额与final reserves、visible chain与结构证书。不能把这些已有能力再包装成新创新。

### 优先1：带下游反证的延迟实体提交（多答案假设，而不只是多来源）

老版每父节点只能一个answer；新版OR route也围绕单一node.answer/scope。可在桥实体歧义明显的节点保留至多2–3个互斥答案候选，每个候选须携带原文关系证据，而非自报confidence。对每个候选接地下一跳，按“原问题目标关系被证据满足/被反证/缺失”评价，不按dense相似度选答案。只有下游关系证据支持后才提交；反证时局部重放受影响子图，不重跑所有节点。

可写成：`hypothesis=(answer, supporting_docs, binding_constraints)`；带最终需求的 `support(h)` 与 `contradict(h)`；action为保留/扩展/提交/回退。限制总LLM/检索额度，并缓存共享证据。避免把多候选每个都扩展到终点造成调用爆炸。

代码入口：core.node_state/ground 与 v6 controller的states；保持档案池、检索器、Reader、temperature、tokenizer、labels流程不变。最先做双候选仅桥节点，不重写整个新版。

可证伪预期：桥实体歧义子集的错误传播率降低，整体F1提升并且无歧义题不退化；若仅增加调用得到同收益，则贡献需改为效率或鲁棒性。消融必须含同预算self-consistency、单候选+verification、随机扩展与去下游反证，不能只比零额外调用的老版。

### 优先2：目标条件的证据收益预算（可作为1的预算机制）

老版最大化“闭包数”，新版已有必要终端优先与固定预算/公平分配；尚无证据条件的action效用调度。可用原问题必要关系组成终端需求集T，测量现有证据对T的缺口、候选桥实体的分歧与反证。下一次检索/验证/候选扩展由预期减少终端不确定性的收益/真实token或latency成本决定，而非对每节点同样追加检索。

目标可描述为：在全局预算B内最大化终端需求支持、对错误绑定的反证与最终答案正确率的校准代理；对无法估计收益的动作使用保守默认而非伪精确confidence。该策略应在held-out开发题估计，测试期只读当前证据，不读gold。旧core的≤6节点穷举保留，可把proof weight从等权改为target-conditioned；新增的真正研究点在action调度与证据收益估计，不是knapsack换公式。

测量：F1/EM与延迟、总LLM input/output tokens、ANN数的Pareto曲线；各数据集/跳数分层。等调用预算与等实际tokens均报告。与新版fair-share/max-budget单独对照。

### 优先3：关系覆盖驱动的语义计划修复

旧planner只验证语法/拓扑，新版只加细化且冻结终端。可将原问题实体、限定词、比较/时序/否定条件编译成可审查需求；每个node须说明承担哪个需求，显式target_slot。发现未覆盖约束、无用分支或错误关系后，允许受限替换/删节点/重绑父子关系，保留已经由原文建立的事实并只重算受影响子图。

这与“让LLM再想一次”区别在于修复输入含具体未满足需求和原文反证，操作为有限集合，并保存前后覆盖证书。风险是planner增加误修复，所以先测原计划错误发生率，优先只修有可定位反证的错误。消融：仅语法修复、只细化、无证据重规划、证据触发语义修复。报告invalid plan率、约束漏失率、修复收益/损害率及额外成本。

### 低成本必要诊断：Reader链的因果暴露校准

新版visible-chain和span证书已是工程实现，不宜独立冒充创新。更有价值的研究是回答“Reader何时应相信链、何时应原文重答”：固定同一selected20，以无链/正确链/错误链/置换链/原文加入明确反证作诊断（人为错链仅做鲁棒性评测），计算链答案服从率、错误链纠正率、正确链背叛率与格式净增益。正式方法仅对supported且实际选集中闭包完整的节点链暴露；有争议时提示具体反证，或对终端答案做独立的小成本关系验证。相比再加全局审计器，先定位既有87–99%复制是否在错误链上造成系统损失。

### 不应再次包装为新增主创新

全语料节点检索、单调用JSON无thinking、答案链注入、证明闭包枚举均属旧v2已有；source_span/AND-OR/冲突失效/终端优先/预算证书/visible-chain属新版已有；answer_type硬结构约束在方法卡已有判负，不能忽略负证据简单再推。BM25混合、cross encoder rerank、更多top-k或更大模型可作增强基线，但单靠这些难形成区别明确的论文主贡献。

## 6. 建议最小实验顺序

先保留frozen non-thinking v6为anchor，复现模型/语料/评分/1000题ID口径；新增机制另建模块与输出目录，不修改冻核。先在独立开发样本标注约50–100个失败题，按“计划错误/桥实体错/检索缺完整组/证据误引用/链服从/格式或解析”归因。不能凭方法卡汇总推断各类发生率。

随后选一条主线，以old-v2、新版当前方法、old-v2+基础证据验证、old-v2+双假设+下游反证四个臂配对跑同题；所有臂持有同一LLM/ANN/tokens预算上限和调用实数。开发阶段与测试题按固定ID划分，所有阈值/触发规则冻结后再跑测试，test labels仅在生成结束后评分。论文主表包含所有题（协议失败计零、服务中断保留pending），共同成功题只作为辅助表，防止拒答把F1虚抬。

每题保留plan、检索命中与面板、互斥候选、确切原文、绑定/反证、每次action、预算消耗、终端闭包及最终答案。主指标F1/EM/all@k、桥实体错误传播、citation precision、错误链纠正、token/延迟；使用paired bootstrap报告差值区间，多seed仅在方法实有随机性时需要。按2/3/4跳及数据集分层，至少提供terminal-direct和reader无链消融。若收益只在高歧义桥节点出现，应把适用范围如实写明。
