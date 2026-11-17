# Preference / personalized-memory RAG：与 DAG + BT 剩余求解方法最接近的正式会议工作

核验日期：2026-10-12。依据已下载的正式会议页面、论文全文与固定公开代码；本轮没有调用付费生成服务或读取实验答案标签。比较对象为 `tmp/pdfs/dag_bt_innovation/method.txt` 中的方法，并结合当前 a48 实现边界。

## 结论

**RF-Mem（ICLR 2026）是最应正面对比的方法。** 它已经实现自适应切换与多轮记忆扩展，因此“动态检索”“链式唤起”“按需扩大搜索”“不使用额外 LLM 的轻量检索”本身不能作为我们的独有创新。可论证的区别在于：RF-Mem 用检索分数与熵判断走哪条检索路径，用轮数或条目数结束扩展；DAG + BT 用当前事实对原问题的剩余求解状态，判断哪些未决事实仍能改变输出，再将这些需求交给原文条件化检索。

**A-Mem 与 MemoryOS 主要是长期记忆库如何组织、写入和更新；我们的主要对象是当前问题的求解状态。** 二者可以作为完整系统 baseline，也可能与我们组合，不能简单写成彼此替代的同一模块。**PrefEval 和 PersonaMem 是 benchmark 贡献**；准确说法应为“其中的 Dense RAG / prompting / memory baseline”，不是把 benchmark 名当成独立新检索算法。

当前实现支持原文来源、版本、反证撤销及局部实体/时间范围，不等于已经实现持续在线的用户偏好演化系统。历史观察、当前偏好与未来推荐可以分别声明范围；源文本能否建立对应事实仍由语义读取判断。并没有一般性的时间逻辑推理器、偏好更新优先级规则或跨任务持久画像生命周期。

## 1. RF-Mem：最直接的检索机制对照

- 正式题名：**Evoking User Memory: Personalizing LLM via Recollection-Familiarity Adaptive Retrieval**。
- 会议：**ICLR 2026**，正式 [poster 页面](https://iclr.cc/virtual/2026/poster/10008269)。
- 论文：[§2.1–2.3](https://arxiv.org/html/2603.09250)；本地 `a48_v3_validation/research/sources/rfmem_paper.txt` 第 132–204 行。
- 官方代码固定版：[d6a2cb3416e8320bcb1439921d319729aeccec8e](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/tree/d6a2cb3416e8320bcb1439921d319729aeccec8e)。

机制：先做 probe top-K，计算平均相似度及 softmax 分布熵。高熟悉度走一次 top-K Familiarity；低熟悉度走 Recollection。后者对候选向量做 KMeans，以簇中心和当前/原始 query 向量混合得到后续查询，在 beam/fanout/depth 限制下多轮扩展。最后返回各轮结果并集的 top-K。§2.3 明确以最大轮数 R 或收集到目标数量结束；其“residual”项是向量混合中保留原 query 的项，不是原问题程序的剩余表达式。

公平差异：

| 维度 | RF-Mem | 本方法可以准确主张的区别 |
| --- | --- | --- |
| 控制对象 | retrieval path、向量候选与检索轮次 | 事实绑定后的未决任务及输出依赖 |
| 扩展依据 | query–centroid 向量混合 | 当前局部子问题和原文线索条件化桥接 |
| 停止依据 | R 或目标条目数量 | 支持的形式子语言中，剩余未知量已不能改变所需输出；另有预算耗尽等非成功停止 |
| 证据状态 | 返回检索片段集合；公开方法未描述 typed binding 的父版本失效/证书 | typed facts、替代支持路线、实际父依赖版本、反证撤销、来源闭包 |

不能声称 RF-Mem 没有多跳、没有条件化查询、没有自适应预算，或没有任何来源信息：其源码保留消息索引 metadata。更精确的区别是，它没有在所检查的方法中将来源组织为用于残余求值和停止验证的版本化事实证明状态。

建议实验：Dense 与 RF-Mem 共享 turn memory pool、相同 embedding、相同 top-K，另与完整 DAG + BT 比较；保留 RF-Mem 原生机制，单独统计额外 reasoning 成本。它原论文将公平性限定为 retrieval-only comparisons；我们的多次生成不应被描述为与它等算力。PersonaMem setting 为 top-K=10，B=3，F=2；完整参数和源码与论文差异沿用现有 baseline protocol 文档。公开 driver 的 cutoff 与参数问题需要修正并公开，不能据此断言原论文泄漏。

## 2. A-Mem：存储演化与来源支持的区别

- 正式题名：**A-Mem: Agentic Memory for LLM Agents**。
- 会议：**NeurIPS 2025**，正式 [poster 页面](https://neurips.cc/virtual/2025/poster/119020)。
- 论文：[§3.1–3.4](https://arxiv.org/html/2502.12110)；本地 `sources/amem_paper.txt` 第 92–141 行。

机制：每个交互生成 memory note，包含原文、时间戳、关键词、tags、LLM contextual description、embedding 和链接。新 note 先检索近邻，再由 LLM 判断链接；memory evolution 会修改既有近邻的 context/keywords/tags。查询期按 embedding 取 top-K，论文架构图还描述访问相连记忆。它把“如何建立并演化记忆结构”作为主体贡献。

不能说 A-Mem 没有原文或没有时间信息：其 note 公式明确包括原始 content 和 timestamp。差异是它的 link 表达语义关联，**不是自动等价于**“结论成立所必需的前提依赖”。我们的来源闭包、OR 替代路线与父版本失效用于保障当前推理状态，不是在发现新交互后改写整个长期 note 库。当前方法不能宣称取代 A-Mem 的长期写入和记忆演化。

实验边界：原论文主要为 LoCoMo/DialSim，并非直接同一 PersonaMem。迁移需要按逐题 cutoff 构建 memory 快照，并把 note 建库、link/evolution 调用纳入成本。论文 top-K 随模型/类别而变，不能只引用 README 的默认 10。

## 3. MemoryOS：层级记忆管理与每题残余求解的区别

- 正式题名：**Memory OS of AI Agent**。
- 会议：**EMNLP 2025 main**，正式 [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1318/)，DOI `10.18653/v1/2025.emnlp-main.1318`。
- 依据正式 PDF §3.2–3.4；本地 `sources/memoryos_formal.txt` 第 186–320 行。不要混用早期 arXiv 设置。

机制：STM 保存近期 query/response/timestamp dialogue pages，并生成 dialogue-chain metadata；FIFO 溢出迁移到 MTM。MTM 按语义及关键词分数将 pages 组织成 topic segments；访问次数、交互长度和 recency 组成 heat，用于保留、淘汰及长期 persona 更新。LPM 含 User Profile、User KB、User Traits 和 agent persona。查询时取全部 STM、两阶段 MTM 检索及相应 LPM 内容后生成。

这确实包含对用户兴趣、习惯和偏好的持续维护，因此不能把“动态偏好管理”据为本方法已实现的新能力。MemoryOS 管的是记忆保存、迁移、淘汰和画像；我们的 F_t 管的是**这一题哪些事实还需要求解**。它的 heat/recency 是存储管理与检索信号，并非当前输出对未决变量的逻辑依赖检验。

## 4. PrefEval：偏好遵循评测依据，不是独立记忆算法

- 正式题名：**Do LLMs Recognize Your Preferences? Evaluating Personalized Preference Following in LLMs**。
- 会议：**ICLR 2025**，正式 [poster 页面](https://iclr.cc/virtual/2025/poster/29686)。
- 论文：[§3.1、3.6、Appendix A.4/A.7](https://arxiv.org/html/2502.09597)。

机制/贡献：3000 个 preference-query pairs、20 topics、显式与两类隐式表达，生成与分类两种评测。方法比较含 zero-shot、reminder、self-critic、few-shot CoT、RAG，并研究 finetuning。RAG 用 `sup-simcse-roberta-large` 取 top-5 exchanges；固定公开实现保留原对话后追加检索片段，不能说总输入仅五条。§3.6 的动态偏好实验插入多项与冲突偏好，检验后述偏好遵循，属于评测设计与行为发现。

用途：为偏好推断、长历史遗忘和冲突偏好提供任务动机/补充评测。不能据此推出“DAG + BT 已实现偏好冲突自动消解”或宣称比整个 PrefEval benchmark 创新。对照应具体命名 `PrefEval-style RAG` 或某个 prompting baseline，并注明数据和上下文差异。

## 5. PersonaMem：最直接的数据与动态场景依据

- 正式题名：**Know Me, Respond to Me: Benchmarking LLMs for Dynamic User Profiling and Personalized Responses at Scale**。
- 会议：**COLM 2025**，已核对 OpenReview 的 `venue=COLM 2025` 和正式论文页眉。
- [OpenReview](https://openreview.net/forum?id=6ox8XZGOqP)；[论文 v2](https://arxiv.org/abs/2504.14225v2)，§4.4 / Fig.5。

机制/贡献：模拟用户长期多会话、变化的 persona 与 preferences，评估按当前状态作答、追溯变化原因、跟踪演化及迁移到新场景等能力。论文 RAG 基线使用 BGE-M3 top-5 messages，另含提取 facts 的 Mem0；消息/turn 合并细节不能从“messages”单词独断。该 benchmark 证明研究问题重要，不证明我们的算法已经解决动态偏好。

用途：当前主评测。相同题、cutoff、公开选项、共享生成模型与评分器；除总 accuracy 还报告各 question type 及执行失败。对“track evolution/latest preferences”的提升只能作为实验结果报告，需先完成可靠的全量对照。

## 对创新表述的约束

建议定位：**面向长期交互记忆的、由剩余求解状态驱动的证据访问与推理框架**。最有价值的链条是：原问题依赖关系提供可执行的输出语义 → 已证实事实让残余状态更新并约束后续记忆访问 → 完成时保留可检查的实际来源和依赖关系。

不应写成：首次动态 RAG、首次多跳记忆、首次记忆图、首次动态偏好、保证检索到全部证据、保证证书代表自然语言事实真、或者所有 PersonaMem 开放推荐都具有形式化唯一答案证明。代码已区分 `certified_symbolic` 与 `semantic_assessment`；只有前者可以在支持的表达式/域/约束及已验证语义绑定条件下主张输出不变性。单次停止还必须区别预算耗尽/未完成与成功完成。

与 RF-Mem 的差异适合用受控实验检验：在控制检索池/模型与报告成本的前提下，比较固定扩展、RF-Mem 的分数/熵控制、DAG 全部执行和残余状态执行。额外统计无关分支访问、证据撤回后依赖失效/重新激活、正确停止与错误提前停止。不要只展示平均少检索几条就声称必要性已被证明。

## 可追溯资料

全部原始下载在 `/Users/mao/projects/dagv2_analysis/a48_v3_validation/research/`：

- RF-Mem：`sources/rfmem_iclr.txt`、`rfmem_paper.txt`、`rfmem_EmbdRetri.py`。
- A-Mem：`sources/amem_neurips.txt`、`amem_paper.txt`。
- MemoryOS：`sources/memoryos_acl.txt`、`memoryos_formal.pdf`、`memoryos_formal.txt`。
- PrefEval：`prefeval/venue.html`、`paper.txt`、固定源码文件；venue canonical URL 与题名已核对。
- PersonaMem：`personamem_sources/openreview_6ox8XZGOqP.json`、`personamem_v1_paper.txt`。
- 设置细节：项目文档 `docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md`。本文件侧重机制与创新边界，不表示外部 baseline 已实现或成绩已复现。
