# Preference RAG 顶会方法：资源设置与可对齐边界

核查日期：2026-10-12（Asia/Shanghai）。本次只读取本地研究线索、会议官网、论文和固定 commit 官方代码；未调用实验模型服务、未运行上游算法、未修改实验源码或配置。PersonaMem 官方协议、PrefEval 由其他并行研究负责，此文聚焦 RF-Mem、A-Mem、MemoryOS。

## 结论

这三项正式会议工作**不能推出 preference RAG 应统一使用 24K context**。论文的数据历史大小、检索 k、平均输入 token、SDK 输出上限、服务实际 context 上限属于不同量，不能互相替代。

RF-Mem（ICLR 2026）最接近 PersonaMem 偏好检索任务，适合优先移植其检索核心。A-Mem（NeurIPS 2025）和 MemoryOS（EMNLP 2025 主会）适合补充动态记忆、长期画像对照，但原论文主要在 LoCoMo 等数据上评估，迁移到 PersonaMem、统一新底座后属于 controlled comparison，而非原论文数值复现。

当前 a48 对照若要求保持原算法和共同 16K 条件，应该保留并公开容量失败。`frozen_flow.py` 第 69 行有 `count + first_tokens + final_tokens + 8 <= 16384` 的硬约束；residual 的 `configs/residual-memory.example.json:13` 也配置 `context_tokens=16384`。只将 residual 调至 24K 会改变资源条件，不能用这些论文合理化。未来如开展更大共同 context 的独立实验，应先确认实际服务支持、对两方法使用同一有效上限并显式标记协议变更；该实验不能替代当前冻结 16K 结果。

本地依据：[original 16K 约束](/Users/mao/projects/dagv2-personamem-a48/package/frozen_flow.py:69)、[residual 16K 配置](/Users/mao/projects/dagv2-personamem-a48/configs/residual-memory.example.json:13)。本次没有重新运行容量失败样本，失败细节应引用主审计报告。

## 一览：不要把表中 k 当最终输入长度

| 方法 / 正式身份 | 论文主要评估与模型 | 记忆单位、检索范围 | 已核实的资源设置 | 可用于当前实验的意义 |
|---|---|---|---|---|
| RF-Mem，ICLR 2026 Poster | PersonaMem 32K/128K/1M；另有 PersonaBench、LongMemEval 检索评估。PersonaMem 生成器在 Appendix B 只称 “advanced LLM”；官方 driver 默认 `gpt-4.1-mini` | PersonaMem 按 user + assistant turn 建库；`multi-qa-MiniLM-L6-cos-v1`；公开 runner `topk=10, B=3, F=2` | 32K 表的 Full Context 平均输入 24,657.8；Dense 3,515.9；RF-Mem 3,566.6 tokens；driver 输出上限 32。未从所审实验段与 driver 得到一个统一 16K/24K 输入 cap | 最接近同任务的检索对照；必须固定 prefix、模型、有效参数后重跑，不直接搬论文成绩 |
| A-Mem，NeurIPS 2025 Poster | LoCoMo、DialSim；主表包括 GPT-4o-mini、GPT-4o、Qwen2.5 1.5B/3B、Llama3.2 1B/3B；embedding `all-MiniLM-L6-v2` | 原交互 + LLM 生成的 context/tags/keywords + 链接/演化笔记。不是简单固定 token chunk | Appendix A.5/Table 8：GPT-4o-mini 和 GPT-4o 的五类 k 为 **40/40/50/50/40**；其他模型 10–50。README 默认 k=10。robust vLLM 示例明确 `--max-model-len 8192`，但不是全论文统一 cap | 应保留其建库/演化机制；新底座、新数据、共同资源限制需标注迁移对照。k=10 可作公开默认起点，不能冒充 GPT 原表设置 |
| MemoryOS，EMNLP 2025 main | GVD：GPT-4o-mini、Qwen2.5-7B；LoCoMo：GPT-4o-mini、Qwen2.5-3B。正式实验段未明确 embedding 型号；当前 SDK 默认 `all-MiniLM-L6-v2` | page=(query,response,timestamp)；STM + MTM + LPM。top-m=5 segments；MTM top-k=5（GVD）/10（LoCoMo）；还加全部 STM、画像、LPM entries | 正式 PDF：STM=7 pages；MTM=2000 segments；User KB/Agent Traits 各 100；heat threshold=5。Table 3：3,874 recalled tokens、4.9 次 LLM calls 均为测得统计。SDK temp=.7、输出上限1500 | 适合作分层记忆对照；不能将 MTM 的 k=10 或平均 4.9 次调用当总输入/硬调用预算 |

## 1. RF-Mem：最相关，但论文模型身份和公开 driver 要分开说

正式会议身份：[ICLR 2026 官方页面](https://iclr.cc/virtual/2026/poster/10008269)，论文 *Evoking User Memory: Personalizing LLM via Recollection-Familiarity Adaptive Retrieval*。论文：[HTML](https://arxiv.org/html/2603.09250)。本次 GitHub API 重新核实 main=`d6a2cb3416e8320bcb1439921d319729aeccec8e`。

- 论文 §3.1 和 Appendix B：同一记忆向量空间对比 Zero Memory、Full Context、Dense/Familiarity、Recollection、RF-Mem；PersonaMem chunk 为一轮 user query + LLM response；λ=20、B=3、F=2、θ_high=.6、θ_low=.3。这里只明确检索器，没有给出 PersonaMem generator 的确切模型名。本地证据 `sources/rfmem_paper.txt:187–200,1326–1329`。
- 论文 Table 1 的 32K block：Full Context=24,657.8，Dense=3,515.9，RF-Mem=3,566.6 **Avg. Tokens**。数据 32K 是 memory corpus 大小；24,657.8 是平均实际输入，不是 24,576 的配置上限。表亦用 OOC 标注超出输入窗口，但不能据此补造具体 cap。本地 `rfmem_paper.txt:202–268`；[Table 1](https://arxiv.org/html/2603.09250#S3.T1)。
- [固定 driver 第40–44行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L40)默认 `gpt-4.1-mini`；第178–188行为 `max_tokens=32, temperature=0, top_p=.9, seed=42`。这只是已公开代码默认值，不能证明论文表的服务快照。第194行从服务 usage 取 prompt_tokens，是统计输入用量而非限制输入长度。
- [固定 run.sh 第14–30行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/run.sh#L14)传 `topk=10,B=3,F=2`，同时做10×6组 alpha/tau sweep。不能把这个脚本说成单一预注册配置；不得在测试答案上择优后汇报同一批结果。
- [main_batch.py 第92–101行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L92)读取 cutoff 却对完整 context 建库；配套 data README 明确要求 history prefix。移植应修正这个可见协议缺口，但不能据此断言论文实际表格已泄漏。第111行访问 `cmd_args.rag`，parser 没有定义该参数，直接复现入口也需要审计。
- [EmbdRetri.py 第31–104行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/retri_mdoel/EmbdRetri.py#L31)：忽略 system，合并同角色消息，配 user-assistant，末尾未配 user 被丢弃。将记忆单位都称为“turn”仍不足以保证相同输入协议。
- 检索 query 只含问题；选项在 driver 第129行才进答案 prompt。启发式主方法无训练；Appendix D.6 的 learned gate 使用400/189训练/评估切分，须与无训练主版本分开。论文 retrieval time 为独占单张 A100 所测，不能等同 HTTP 端到端时延。

可对齐项：每题可见 prefix、query/选项的可见性、相同 generator、embedding、解码和评分协议；记录 k、B、F、alpha、tau 及实际有效阈值。换 embedding 后 score 分布会变，阈值不能假定仍然最优。保留原算法、预注册参数得到的是统一底座迁移结果；如需校准须独立开发集。

## 2. A-Mem：k=10 不是 GPT 原表的统一设置

正式会议身份：[NeurIPS 2025 官方页面](https://neurips.cc/virtual/2025/poster/119020)。论文 *A-Mem: Agentic Memory for LLM Agents*：[本次固定读取 arXiv v11](https://arxiv.org/html/2502.12110v11)。研究复现仓库 main=`0c8039f28fdcc08189a23c07a3437d9d2482f9c2`；与 README 指向的应用库应分开标记。

- §4.1 明确 LoCoMo、DialSim；LoCoMo 用 F1/BLEU-1 等生成指标；不是 PersonaMem 的四选一 accuracy。§4.2 统一 system prompt，`all-MiniLM-L6-v2` embedding，主要 k=10，但明确按类别调整，细节放在 Appendix A.5。本地 `amem_paper.txt:143–153`。
- A.5/Table 8 原值如下，本地 `amem_paper.txt:1864–1909`。列顺序为 Multi Hop / Temporal / Open Domain / Single Hop / Adversarial。

| 模型 | Multi Hop | Temporal | Open Domain | Single Hop | Adversarial |
|---|---:|---:|---:|---:|---:|
| GPT-4o-mini | 40 | 40 | 50 | 50 | 40 |
| GPT-4o | 40 | 40 | 50 | 50 | 40 |
| Qwen2.5-1.5B | 10 | 10 | 10 | 10 | 10 |
| Qwen2.5-3B | 10 | 10 | 50 | 10 | 10 |
| Llama3.2-1B | 10 | 10 | 10 | 10 | 10 |
| Llama3.2-3B | 10 | 20 | 10 | 10 | 10 |

- [固定 README 第82–122行](https://github.com/WujiangXu/A-mem/blob/0c8039f28fdcc08189a23c07a3437d9d2482f9c2/README.md#L82)：原 JSON schema 与 robust plain-text 为不同入口；robust 示例 Qwen2.5-3B vLLM 设置 `--max-model-len 8192`；`--retrieve_k` 默认10，并建议 k sweep。这不支持“论文统一24K”，也不能将 robust 示例8192外推为所有模型和原论文的共同 cap。
- §4.3/Appendix A.3 的约1,200–2,500 tokens 等效率描述是测得消耗，不是额外证据窗口或配置上限。本地 `amem_paper.txt:642,1852`。其 note construction、linking、evolution 会调用 LLM，须独立计入建库和维护成本。
- [memory_layer_robust.py 第352–390行](https://github.com/WujiangXu/A-mem/blob/0c8039f28fdcc08189a23c07a3437d9d2482f9c2/memory_layer_robust.py#L352)分开配置 generator 与 embedding，通过 `add_note/process_memory`维护笔记。相同 k 的富化笔记与 RF-Mem 原始 turn 长度不可视作同 token 预算。

对当前协议的含义：不能把 LoCoMo 类别专属 k 原封不动映射到 PersonaMem 的七类偏好问题。可以预注册公开默认 k=10 作为迁移起点，再在独立开发集决定是否调参；须明确不是原 GPT 表设置。统一底座、prefix 与有效资源边界后重跑，记录结构化记忆调用失败及成本。

## 3. MemoryOS：正式版与早期预印本有配置差异

正式身份：[ACL Anthology](https://aclanthology.org/2025.emnlp-main.1318/)，*Memory OS of AI Agent*，EMNLP 2025 main，页25961–25970；[正式 PDF](https://aclanthology.org/2025.emnlp-main.1318.pdf)。官方代码 main=`587ed7755c7aed179965792830ff1b5ad9a6fa92`。

- 以正式 PDF 为准。§4.1（p.25966）配置 STM=7、MTM=2000、User KB/Agent Traits=100、heat τ=5；MTM 取top-5 segments，top-k pages在GVD=5、LoCoMo=10。本地 `memoryos_formal.txt:340–344,373–382`。早期 arXiv v1 写 MTM=200，不能混用，见 `memoryos_paper.txt:467–474`。
- §3.4–3.5（p.25965）最终答案用 STM 全部页、MTM 检索页，以及 LPM 的知识/画像；User KB 和 Assistant Traits 各 top-10，User/Agent Profile 与 User Traits 全部使用。因此 **MTM k=10 不是全部10条记忆，更不是10×固定chunk长度的总输入**。本地 `memoryos_formal.txt:267–320`。
- Table 1（GVD）使用 GPT-4o-mini、Qwen2.5-7B；Table 2（LoCoMo）使用 GPT-4o-mini、Qwen2.5-3B。GVD 由 DeepSeek-R1 评分，LoCoMo 使用 F1/BLEU-1。不能把该 judge 身份误认为 answer backbone，也不能与 PersonaMem accuracy 直接排名。
- Table 3（p.25967）：MemoryOS=3,874 recalled tokens、平均4.9 LLM calls；A-Mem*=2,712 tokens、平均13.0 calls。星号明确是 MemoryOS 作者在同环境重实现的 A-Mem，非 A-Mem 原论文数字。本地 `memoryos_formal.txt:384–426,445–447`。这些是统计量，不能设成每题硬预算，也没有给出“所有方法24K”的依据。
- [当前 SDK 默认第30–43行](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-pypi/memoryos.py#L30)为 `short_term_capacity=10, mid_term_capacity=2000, retrieval_queue_capacity=7`、GPT-4o-mini 和 all-MiniLM-L6-v2。SDK默认与正式论文 STM7/MTM-k10 不完全相同，因此应显式传参并追踪有效配置，不能只跑README默认就称论文复现。
- [SDK 第252–346行](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-pypi/memoryos.py#L252)展示最终拼接输入；`temperature=.7,max_tokens=1500`，作答后将测试query与生成答案写回记忆。PersonaMem controlled comparison 必须使用每题独立、按cutoff冻结的记忆状态，避免跨测试题写回影响后续题目。模型调用异常不能静默作为记忆正文继续使用。

## 4. 建议如何使用这些文献

1. **当前冻结 a48 验证保持共同16K。** 从文献得到的主要启示是记录真实输入和失败，不是选择一个更大的任意cap。报固定分母 accuracy、完成率、容量失败数以及共同成功题的配对差异；容量失败不能从分母排除后宣称胜出。
2. **优先增加 RF-Mem controlled port，再考虑 A-Mem/MemoryOS。** 上游官方代码与数据可见协议之间的差异应以适配说明公开；不将原论文数字当新服务的已复现结果。
3. **统一外部条件，保留方法内部机制。** 固定数据revision/题目/prefix、模型服务身份与量化、embedding、解码、答案parser；不为原无reranker方法强加reranker，不把所有方法强制同k等同公平。若比较reranker版本应另列增强条件。
4. **分别报告每请求 context cap、输出预留、每题调用数、总token成本、离线建库成本。** 相同context上限不自动等于相同计算量；相同k不等于相同输入量；相同模型名不自动等于同部署上限。推理、审核、repair等调用均应进入成本口径。
5. **更大共同cap只能是另一项预声明实验。** 先验证服务真实支持，再明确两种方法的有效cap、算法与裁剪是否变化。当前original含16K硬编码，不能只改一个共享JSON就声称两边已对齐，也不应偷偷改冻结original。

本结论是对所审三项论文、指定版本和入口的证据判断；没有声称穷尽全部个性化RAG论文，也没有将“未在所审部分找到cap”推断成该方法完全不存在其它部署限制。

## 来源留存

所有本次下载原件保存在同目录 `sources/`：

- `initial_manifest.json`：会议页面、论文HTML、GitHub main SHA的URL与响应记录。
- `pinned_source_manifest.json`：固定commit源码与正式PDF的URL、字节数、SHA-256。
- `rfmem_*`、`amem_*`、`memoryos_*`：原件及文本提取；本文本地行号对应这些文件。正式MemoryOS PDF经 `pdftotext -layout` 提取，双栏文字应结合论文页码理解顺序。
- 前期本地线索为 `/Users/mao/projects/bridgetree_preference_rag/reports/2026-09-15-audit/research_baselines.md`；本次关键数字均重新读取官方来源，没有把前期建议中的8192最终输入上限当作当前a48协议。
