# R16：数据历史长度与请求容量定义复核

审查对象：冻结源码 `b9e28a7faa8d419f9f1283574fa095399919c243`。仅核对本地 README、配置、既有研究记录及容量代码；不复算 R16 第二题，不读取问题/选项/标签，不请求网络或模型，不修改配置与 gate。

**结论：当前数据是 PersonaMem-v1 的 32K 历史版本，并不存在本项目选用了“PersonaMem 16K 数据版本”的证据。16384 是既有对照实验保留的单次完整模型请求容量约束，不是数据集长度、检索文本的净预算，也不是文献统一规定。早期研究文档已经明确区分这些量。**

## 1. 各个数字的准确含义与出处

| 项目 | 本项目事实 | 直接出处 |
| --- | --- | --- |
| 数据历史版本 | `PersonaMem-v1`、revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`、`split="32k"`；589 题、20 personas | [data/personamem/manifest.json](/Users/mao/projects/dagv2-personamem-v4/data/personamem/manifest.json:2)；只读取 manifest metadata |
| 逐题可见历史 | `messages[:end_index]`，先截断未来消息，再分割记忆 | 同 manifest 的 `protocol.cutoff`；[已定对齐协议](/Users/mao/projects/dagv2-personamem-v4/docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md:53) |
| 单请求实验容量 | `fusion.context_tokens=16384` | [v4 配置](/Users/mao/projects/dagv2-personamem-v4/configs/personamem-v4.json:13)；旧 `residual-memory.personamem16k.json` 同值 |
| 结构化推理输出上限 | 4096，来自配置默认；v4 JSON 未覆盖该值 | [dagbt/config.py](/Users/mao/projects/dagv2-personamem-v4/dagbt/config.py:18) |
| 输入/安全余量 | residual reasoning 的 input margin 256，另有固定 safety 8 | v4 config；[Reasoner preflight](/Users/mao/projects/dagv2-personamem-v4/dagbt/reasoning.py:115)；[Transport gate](/Users/mao/projects/dagv2-personamem-v4/dagbt/transport.py:122) |
| 每题调用预算 | ANN 36、LLM 24、JSON repair 6，每请求 repair 最多 2；与 context 是不同维度 | [v4 配置](/Users/mao/projects/dagv2-personamem-v4/configs/personamem-v4.json:8) |

文件名 `personamem16k` 指实验请求配置，不能当作数据版本名称。32K 历史也不要求每次 RAG 请求完整放入 32768 tokens，更不等于输出上限。

## 2. 16384 实际包含什么

Reasoner 构造请求时，system 指令与 JSON schema、user 数据及消息封套都进入实际 wire。当前配置使用部署侧 `vllm_chat` 计数。正常请求约束为：

`完整输入计数 + 实际 max_tokens + 256 + 8 <= 16384`

满额 4096 输出时，**完整输入**最多 12024 tokens；这不是原始记忆单独可用的 12024。系统指令、schema、来源原文/元数据、变量/父绑定/已知观察及义务等实际序列化内容共同占用输入。

不同 repair 规则不能混成“每个请求一律扣两个 4096”：

- 普通 reader `_fits` 计算 base 输入与预构造的 repair envelope 输入，使用 `max(base, repair_envelope) + 4096 + 256 + 8`。当前 mandatory compose/audit 使用此完整检查。[joint_reading.py:802](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:802)
- 特定 fresh history 的 whole-review forecast 另为尚未知的首次生成草稿留工作空间。满额形式为 `forecast_input + 4096 初稿空间 + 4096 repair 输出 + 256 + 8`；合格 adaptive 情形的初稿空间使用实际 cap。这是为将来修复请求做的准入预测，并非把同一 HTTP 请求声明成两个输出。[joint_reading.py:814](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:814)
- mandatory 下游读取、已有真实失败草稿的 durable recovery 不额外套用未知初稿 forecast。真正 repair 仍对实际 wire 单独检查。[同函数说明](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:824)

因此，仅知道必要闭包有 39 个来源，不能单独推导实际请求是否超过 16K；应使用归档的精确完整输入及对应阶段预留。R16 第二题的数量/失败链由另一个审查独立核验，本报告不替代它。

## 3. 该上限从哪里继承

1. 原算法的 [package/frozen_flow.py:65](/Users/mao/projects/dagv2-personamem-v4/package/frozen_flow.py:65) 已硬编码 `count + first_tokens + final_tokens + 8 <= 16384`。旧 residual 配置也为 16384。
2. [2026-10-12 baseline 对齐协议:13](/Users/mao/projects/dagv2-personamem-v4/docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md:13) 明确写道：文献没有共同规定“16K / 24K 请求上限、24 次 LLM 调用”；数据历史长度、检索条目、单请求容量和每题成本须分别报告。文档明确决定保留共同 16K，不单独将 residual 改为 24576，并注明“这不是宣称 16K 来自论文”。
3. [同文档:83](/Users/mao/projects/dagv2-personamem-v4/docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md:83) 说明保留原算法内部预检，通过部署 tokenizer 修正计数失配；相同名义 context 不代表内部预检、输出分配或总计算成本完全相同。研究 decision JSON 也记录只新增 opt-in tokenizer、保留原预算。
4. [早期 WORK_STATE.md:15](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/WORK_STATE.md:15) 明确是 v4 **retains existing** 16k/36ANN/24LLM。它记录工程继承，不是新的文献推导。
5. [当前 README:3](/Users/mao/projects/dagv2-personamem-v4/README_PERSONAMEM_V4.md:3) 只简写“两组……相同 16384 context 设置”，没有把数据写作 16K，也没有完整解释输入/输出/repair 分配。完整定义需结合协议和代码；这处简写不能当作净检索预算的定义。

既有原算法内部预检与 residual 预留机制并不相同；共享最终部署请求 gate 的 nominal 上限不能被表述成所有中间预算完全等价。远端模型真实最大支持容量也不能由本地 `16384` 配置或模型名称推断。

## 4. 是否有用户明确要求

这一子任务可见的用户原话是：**“调研一下preference rag顶会baseline，看看人家咋设置的，保持一致”**。可见会话没有直接要求“PersonaMem 使用 16K 数据版本”，也没有找到用户明确指定“完整模型请求必须等于 16384”的原话。

用户曾执行命名为 `residual-memory.personamem16k.json` 的配置，能证明既有实验使用了该协议，不能据此补写一条用户从未明确说出的数值要求。WORK_STATE 的 16k 描述是代理对继承配置的工作记录，不能冒充逐字用户要求。

这是有限材料中的出处结论，不断言不可见历史中绝无其他要求。当前任务已明确冻结配置并要求不得因失败修改 gate，且 R16 的证据属于这套固定协议；本报告没有产生更改上限的授权或建议。

## 5. 本地参考 baseline 文档记录的事实

以下复用 2026-10-12 已下载/核验的本地研究文档，没有再次联网，亦没有运行外部 baseline：

| 来源 | 与 context 定义有关的记录 | 不能推出的结论 |
| --- | --- | --- |
| PersonaMem，COLM 2025，§4.4/Fig.5 | 主 RAG 对照使用 32K 历史，BGE-M3 top-5 messages；相关实验段没有统一请求 context/output cap | 不能推出该 RAG 的完整请求必须 16K，也不能把 32K 当 RAG 输入限额 |
| RF-Mem，ICLR 2026，Appendix B/Table 1 | PersonaMem 32K；turn-memory/top-10；32K 表平均输入 Dense 3515.9、RF-Mem 3566.6、Full Context 24657.8；公开 driver 最终输出 cap 32 | 均值不是 cap；最终选项 32-token 输出不等同本项目结构化推理 4096 reserve |
| PrefEval，ICLR 2025，A.4/A.7 | 另一偏好数据集，top-5；代码保留已有对话再追加检索；generation/MCQ 输出上限分别 300/5 | 不能以 top-5 推断全部输入很短，也不能据此确定 PersonaMem 的完整请求 cap |

直接本地证据：

- [PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md:21](/Users/mao/projects/dagv2-personamem-v4/docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md:21)
- [personamem_paper_evidence.md:19](/Users/mao/projects/dagv2_analysis/a48_v3_validation/research/personamem_paper_evidence.md:19)：32K/128K/1M 是历史长度版本，§4.4 没有固定 retrieved-context token cap。
- [personamem_code_evidence.md:34](/Users/mao/projects/dagv2_analysis/a48_v3_validation/research/personamem_code_evidence.md:34)：既有 metadata 统计的历史长度最短 15560、最长 29539、均值 24845.82；这不是本次重新读取 CSV 或标签得到的数值，也不能直接决定 RAG 中间请求限额。
- [preference_rag_baseline_resource_alignment_20261012.md:7](/Users/mao/projects/dagv2_analysis/a48_v3_validation/research/preference_rag_baseline_resource_alignment_20261012.md:7)：明确区分数据历史、k、平均 token、输出 cap 和服务真实 context，解释共同 16K 是当前受控实验条件。

**定义审查结果：历史完整研究记录没有把 32K 数据历史混同为 16K 请求容量；“16K 数据设置”这一说法需要纠正。现有 16K gate 的出处是继承与保持共同资源条件，不是顶会统一规定。该出处区分不等于 gate 已失效，也不证明 R16 失败仅由定义混淆导致。**

唯一写入项为本外部报告；源代码、运行配置、当前实验和 release 状态均未修改。
