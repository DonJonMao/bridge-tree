# 近两年顶会基线：同数据身份、公开成绩与无训练复现审计

检索与复核日期：2026-09-15（Asia/Shanghai）。本次重新读取会议官网、论文 HTML、官方 GitHub API 及固定 commit 源码，并重新计算官方数据文件 SHA-256；未运行外部模型、未安装上游工程、未改变当前实验代码。此文是研究证据与复现方案，不是已完成的 baseline 复现实验报告。

## 1. 结论与推荐顺序

**RF-Mem（ICLR 2026）是当前最优先的无训练、同 PersonaMem-v1 32k 复现候选。** 已核实其公开仓库的两份 32k 数据文件与我们的固定版本逐字节相同。但“相同文件”和“相同评测协议”是两回事：当前公开 driver 没有应用每题的 history cutoff，并有命令行参数缺口，不能原样运行后直接比较论文分数。

A-Mem（NeurIPS 2025）和 MemoryOS（EMNLP 2025 主会）可作为无训练的第二批迁移基线。它们的原论文主要评测 LoCoMo（A-Mem 还包括 DialSim）；本次核实到的 PersonaMem 数字来自 RGMem 作者在 **128k** 设置下的重测，不是其原论文已验证的同 32k 成绩。

| 候选 | 顶会身份已核实 | 同 PersonaMem-v1 文件 | 同 32k split | 当前可直接保证同协议 | 无训练复现判断 |
|---|---|---|---|---|---|
| RF-Mem 主启发式版本 | ICLR 2026 Poster | **是，两文件 SHA 相同** | **是，589题** | **否，需修正/审计 driver** | 首选；检索核心可移植到统一 harness，无额外 LLM 建库 |
| A-Mem | NeurIPS 2025 Poster | 本次未核实 | 原论文及研究仓库默认不是此 split | 否 | 可迁移；LLM 生成/演化记忆，无须更新模型权重 |
| MemoryOS | EMNLP 2025 主会 | 本次未核实 | 原论文及复现入口不是此 split | 否 | 可迁移；分层记忆管理，无须更新模型权重 |
| RGMem（作为重测来源/扩展对照） | 不在本子任务重复会议审计 | 本次未核实其原始文件 hash | **原报告为128k，非32k** | 否 | 可另作工程量更高的迁移对照，不混入严格匹配清单 |

“无需训练”不等于“无需 LLM 调用、无需校准、零建库成本”，也不等于“替换底座模型后仍能复现论文原始数值”。

## 2. RF-Mem：会议、代码和数据身份

### 2.1 官方身份与固定源码

- 论文：*Evoking User Memory: Personalizing LLM via Recollection-Familiarity Adaptive Retrieval*。
- [ICLR 2026 官方页面](https://iclr.cc/virtual/2026/poster/10008269)：页面明确为 Poster，论文标题匹配；[ICLR 2026 论文索引](https://iclr.cc/virtual/2026/papers.html)也列出该条目。
- [论文 HTML](https://arxiv.org/html/2603.09250)；[复现声明](https://arxiv.org/html/2603.09250#Sx2)链接至官方代码。
- [官方 GitHub](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem)。2026-09-15 查询 `commits/main` 返回 **`d6a2cb3416e8320bcb1439921d319729aeccec8e`**，commit 时间为 2026-02-25T07:35:04Z。[固定 commit](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/commit/d6a2cb3416e8320bcb1439921d319729aeccec8e)。以下源码审计均基于此 commit。
- 官方 README 另给[原投稿 supplementary material](https://openreview.net/attachment?id=f7p0F2X6XN&name=supplementary_material)。本次访问 OpenReview API 返回 403 `ChallengeRequiredError`；未进一步取得、审计原投稿代码，因此不能确定当前 GitHub driver 与表格产出版本完全相同。会议身份采用可访问的 ICLR 官网核实，不依赖仓库自称。

### 2.2 相同文件，不仅是名称相同

我们的数据：`bowen-upenn/PersonaMem-v1`，revision **`fd7c30f071d5c2ee2a211506783be222d7b6002e`**，split `32k`，589题。

本次重新下载 RF-Mem 固定 commit 下的两个文件并计算 SHA-256，同时重新计算本地固定数据 hash，结果完全一致：

| 文件 | 官方 RF-Mem 与本地共同 SHA-256 |
|---|---|
| `questions_32k.csv` | `cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c` |
| `shared_contexts_32k.jsonl` | `217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a` |

固定文件 URL：[questions](https://raw.githubusercontent.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/data/questions_32k.csv)、[contexts](https://raw.githubusercontent.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/data/shared_contexts_32k.jsonl)。

这是“本次审计到的公开代码携带相同数据”的直接证据；它本身不能证明所有论文表格都使用了该 commit 的同一运行流程。

## 3. RF-Mem 公开成绩：可以引用什么，不能推断什么

[论文 Table 1](https://arxiv.org/html/2603.09250#S3.T1) 的 32K block 直接报告：

| 方法 | Overall accuracy | 平均输入 tokens（论文口径） | Retrieval time（论文口径） |
|---|---:|---:|---:|
| Zero Memory | 38.54% | 464.6 | NA |
| Full Context | 61.29% | 24,657.8 | NA |
| Dense Retrieval | 59.08% | 3,515.9 | 3.14 ms |
| Recollection | 62.14% | 3,711.1 | 7.09 ms |
| RF-Mem | **63.50%** | 3,566.6 | 5.09 ms |

表内 RF-Mem 比 Dense 高 **4.42个百分点**、比 Full Context 高 **2.21个百分点**。这只能描述该论文表内实验，不能与我们当前未完成批次直接排名。

重要限制：

1. [Appendix B](https://arxiv.org/html/2603.09250#A2) 对 PersonaMem 生成器只写 **“advanced LLM”**，未在该处明确型号；检索器明确为 `multi-qa-MiniLM-L6-cos-v1`。因此不能把表中63.50%无条件标成GPT-4o-mini、GPT-4.1-mini，或我们的DeepSeek成绩。
2. [公开 main_batch.py 第40–44行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L40)把API生成器写为 `gpt-4.1-mini`。这证明**当前代码默认值**，不自动证明 Table 1 的模型身份/部署快照。
3. Appendix B 的运行时间为独占单张 A100 环境；论文毫秒级 retrieval time不是我们的HTTP embedding、reranker和生成端到端时延。不能把5.09ms与我们几分钟/task直接相除。
4. 主方法的阈值路由不训练；[Appendix D.6](https://arxiv.org/html/2603.09250#A4.SS6)另研究 learned strategy selector，32k用前400题训练、后189题评估。这个扩展不能纳入“无训练、全589题”版本，也不能把其189题成绩混作Table 1。

## 4. RF-Mem 公开 driver 的可证协议缺口

### 4.1 每题 cutoff 未被应用

[utils.py 第58–80行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/utils.py#L58)加载完整共享 history 后直接 `yield row_data, current_context`；没有按该题 `end_index_in_shared_context` 截断。[main_batch.py 第92–98行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L92)读取了 end_index，但马上对完整context调用 `build_from_history`，没有使用cutoff。

相反，该仓库自带[data README](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/data/README.md)明确要求 `context[:int(end_index_in_shared_context)]`。

结论边界：可以确认**本次公开driver存在可见信息协议缺口**；不应凭此指控已发表表格一定泄漏，因尚未追溯实际产表代码。我们的公平复现必须采用严格prefix，且注明这是协议修正。

### 4.2 可运行性与参数选择

- `main_batch.py` 第111、161行等访问 `cmd_args.rag`，但[第274–301行完整argparse定义](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L274)没有 `--rag`。不能称当前入口下载即跑。
- [run.sh 第14–30行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/run.sh#L14)是10个alpha乘6个tau的**60组参数扫描**，不是一组冻结配置。它指定 `topk=10,B=3,F=2`、32k两文件，结果路径重复。不可把整个脚本当用户下一步复现命令，也不可用全589题答案挑最好参数。
- parser虽提供 `score_th/score_bt`，[main 第101行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L100)实际路由写死0.60/0.30。应审计有效配置，不只记录CLI字符串。
- [main 第178行之后](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L178)生成参数包括 `max_tokens=32,temperature=0,top_p=0.9,seed=42,max_concurrency=200`，不同于我们512输出上限及服务负载条件。不要直接采用200并发。

### 4.3 记忆单元、选项可见性与实现细节

- [EmbdRetri.py 第31–102行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/retri_mdoel/EmbdRetri.py#L31)合并同角色消息、将user-assistant配成记忆，但跳过system消息，丢弃无后续assistant的user单条。我们的配置含system persona并保留独立user条；这也是需要显式对齐的差异，不只是都叫pair granularity。
- 主检索使用原始 `question`；选项只在[main 第129行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/main_batch.py#L129)加入最终回答prompt。与我们query-only检索原则一致。
- [utils.py 第153–158行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/utils.py#L153)把score乘20、softmax后取 `-(p*log(p)).mean()`。论文公式与代码的sum/mean口径应分别记录；不能改成sum还沿用原tau。
- [EmbdRetri.py 第285行](https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem/blob/d6a2cb3416e8320bcb1439921d319729aeccec8e/RF_mem/personamem_data/retri_mdoel/EmbdRetri.py#L282)使用 `sklearn.KMeans(random_state=42)`，不是任意球面聚类；更换会改变算法。

## 5. A-Mem 与 MemoryOS：可比较，但不能冒充同32k已验证成绩

### 5.1 A-Mem

- [NeurIPS 2025官方Poster页面](https://neurips.cc/virtual/2025/poster/119020)确认标题 *A-Mem: Agentic Memory for LLM Agents*。
- [原论文Dataset and Evaluation](https://arxiv.org/html/2502.12110#S4.SS1)列LoCoMo和DialSim；不能将其LoCoMo F1或BLEU当PersonaMem MC accuracy。
- [研究复现仓库](https://github.com/WujiangXu/A-mem)，旧URL `WujiangXu/AgenticMemory`当前重定向至此。2026-09-15 API查得commit **`0c8039f28fdcc08189a23c07a3437d9d2482f9c2`**。[固定README](https://github.com/WujiangXu/A-mem/blob/0c8039f28fdcc08189a23c07a3437d9d2482f9c2/README.md)说明该repo用于论文复现，默认LoCoMo；应用库另有入口，不能混同版本。
- README区分原JSON-schema入口与robust plain-text入口；后者兼容更多后端，但改变解析实现，正式复现需固定模式。默认 `retrieve_k=10`，README建议k-sweep；我们不得在589测试题上择优汇报。
- [RobustAgenticMemorySystem 第352行后](https://github.com/WujiangXu/A-mem/blob/0c8039f28fdcc08189a23c07a3437d9d2482f9c2/memory_layer_robust.py#L352)分别配置embedding和LLM，通过 `add_note/process_memory`做推理时记忆演化。可以使用同DeepSeek服务进行记忆写入与最终回答；需要统一HTTP embedding adapter，而非仅改SentenceTransformer模型名。

### 5.2 MemoryOS

- [ACL Anthology正式论文页](https://aclanthology.org/2025.emnlp-main.1318/)确认 *Memory OS of AI Agent*，EMNLP 2025主会，页码25961–25970，DOI `10.18653/v1/2025.emnlp-main.1318`。摘要描述LoCoMo实证，不是PersonaMem32k主结果。
- [官方仓库](https://github.com/BAI-LAB/MemoryOS)，本次API查得commit **`587ed7755c7aed179965792830ff1b5ad9a6fa92`**。[README复现段](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/README.md#L443)为 `eval/main_loco_parse.py`，不是我们的CSV任务适配器。
- [memoryos.py 第30行](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-pypi/memoryos.py#L30)支持 `openai_base_url,llm_model,embedding_model_name`；LLM可替换，但embedding默认仍是本地SentenceTransformer/FlagEmbedding，需要API adapter。
- **评测污染风险：** [get_response 第338–346行](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-pypi/memoryos.py#L338)用温度0.7/max_tokens1500作答后，将测试query和模型回答写回记忆。应隔离检索与统一生成器、冻结题目快照，不得让测试答案污染下一题。
- **错误吞掉风险：** [utils.py 第61–64行](https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-pypi/utils.py#L61)把LLM异常转为字符串 `Error: Could not get response from LLM.`；我们的适配层必须标作基础设施失败，不能计作正常答案或记忆文本。

### 5.3 后续PersonaMem重测数字的来源

[RGMem论文Table 1](https://arxiv.org/html/2510.16392#S4.T1)及[实验设置](https://arxiv.org/html/2510.16392#S4.SS1)明确使用PersonaMem **128k**；Appendix B.1也明确GPT-4o-mini和GPT-4.1 backbones。表格报告：

| 方法 | GPT-4o-mini，PersonaMem128k | GPT-4.1，PersonaMem128k |
|---|---:|---:|
| A-Mem | 49.17% | 63.95% |
| MemoryOS | 54.23% | 65.03% |
| RGMem | 63.87% | 74.01% |

以上是**RGMem作者的重测报告**，不是A-Mem/MemoryOS原论文成绩，也不是同32k结果；本次未核实该128k评测的数据revision/文件hash及每题cutoff实现，不应把它当我们严格协议已核验的可直接比较排行榜。它支持“值得迁移重跑”的候选判断，不支持“换成DeepSeek便应达到某个百分比”。

## 6. 模型对齐后如何做最小公平实验

建议第一批只加入 `RF-Mem-Familiarity`、`RF-Mem-Recollection`、`RF-Mem-routed`，保留现有Dense作锚；第二批再加入A-Mem/MemoryOS，避免把工程和建库故障同时引入。

1. **数据与可见信息：** 固定上述revision、文件hash和589题ID；每题只用 `messages[:end_index]`。system persona、末尾user-only/与query相同的记忆处理须所有方法一致，公开记录。不能先用全历史生成摘要/图谱，再按时间过滤，因摘要已经可能含未来信息。
2. **模型：** 所有回答以及记忆写入/改写/检索规划使用同一个实际DeepSeek-V4-Flash-284B INT8服务，固定服务模型ID、量化/思考模式、解码及prompt。embedding统一Qwen3-Embedding-8B，统一query instruction、归一化、维度及缓存key。记录实际部署身份；不能凭模型名推断官方最大推理能力。
3. **无训练边界：** RF-Mem用启发式主版本，排除learned gate。A-Mem/MemoryOS的推理时记忆写入允许，但计算成本完整记录。不为本来没有reranker的baseline额外加reranker，否则改变了算法。
4. **预算：** 最终生成输入上限8192、输出上限512、同一parser/温度0。原生top-k与内部参数预注册；需要公平预算消融时另开同预算实验，不把强制同top12等同于公平，尤其raw pair与压缩笔记的条目大小不同。记忆结构化输出用单独、公开的token预算，不能盲目设512导致JSON截断。
5. **参数选择：** 首先报告冻结公开参数的model-aligned port；Qwen embedding的score分布可能使0.6/0.3路由阈值失配，若校准仅用预声明开发集或无标签统计。不得将589题测试答案用于选k、alpha、tau后又报同题最终成绩。
6. **生成与成本审计：** 同一最终wire request应有不受selected_ids原始顺序影响的request hash；对同请求重复评测或在配对设计中共享生成结果，避免把模型服务波动误判成检索收益。分开统计冷/热缓存、离线建库、在线检索、回答、失败和重试成本；限定并发，不压迫仍运行的实验服务。
7. **结果表：** 固定分母准确率、coverage/成功率、共同成功题的配对win/loss、按question_type分层；报完整589题而非只成功样本。新结果标为“模型与输入协议对齐复现”，附上游commit、适配改动和有效配置，不称精确复现原论文数值。

## 7. PDF中建议保留的简短表述

> 首选对照为RF-Mem（ICLR 2026）：其官方代码携带的PersonaMem-v1 32k两文件与本实验SHA-256完全一致，主检索方法不需要训练。论文Table 1报告63.50%，但生成模型在正文实现说明中未明确到型号，公开driver还存在cutoff及参数问题，因此该数字仅作论文内参考。我们应在统一严格prefix、DeepSeek INT8生成器与Qwen3 embedding下移植核心算法并重跑。A-Mem（NeurIPS 2025）和MemoryOS（EMNLP 2025）是第二批无训练迁移基线；其已核实PersonaMem数字来自128k后续重测，不能冒充同32k直接成绩。

本次证据未证明所有满足条件的顶会方法均已穷尽；也未证明任何方法在我们的DeepSeek INT8部署上必然优于Dense。优先级依据是数据身份匹配、无训练属性、已公开实证与工程可复现性，而非承诺准确率。
