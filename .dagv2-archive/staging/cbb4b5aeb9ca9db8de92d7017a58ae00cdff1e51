# PersonaMem-v1 官方代码与数据证据

核验日期：2026-10-12。只读官方公共资料；没有调用模型服务、没有改生产代码。本文区分发布代码、数据文件和论文报告；论文证据另见 `personamem_paper_evidence.md`。

## 可用于配置决策的结论

1. **32K 是历史上下文数据版本**，不是“32K 样本”、训练集名，也不自动要求 RAG 每次推理输入 32K。官方有 32k/128k/1M 三种长度版本。
2. **论文 §4.4 另有 RAG：BGE-M3 检索 top-5 messages；Mem0 检索 top-5 facts；GPT-4o / GPT-4o-mini 回答。** 但本次核验的官方 GitHub 源码是完整历史输入的选择题评测，没有找到这些 RAG 参数的可执行实现。论文报告与当前代码覆盖范围必须分开写。
3. 官方 OpenAI、Gemini、Lambda 推理调用没有显式指定输出 token 上限或 temperature；**未指定不等于无限制，也不等于某个可复现固定默认值**。Claude 分支写了 `max_tokens=128000`，这是源码事实，不能据此推荐其它模型采用这个值。
4. 官方一次问题对应一次回答请求；本仓库的多阶段检索/推理应独立报告总调用与 token 成本。官方资料不能证明 `16K + 24 次 LLM` 是基准统一标准。
5. HF 的 `split=32k/128k/1M` 是长度子集名称；本项目自己的 development/confirmatory persona 划分必须明确标为本地协议。

## 固定证据版本

- 官方仓库：<https://github.com/bowen-upenn/PersonaMem>。
- 检查的源码 commit：`d07e6ade22e85e0e5d562247323a9c3e07553226`；下面链接均固定到该 commit，避免将后来 README 的更新误当论文原始实验配置。
- 本地 BridgeTree 数据固定到 HF `bowen-upenn/PersonaMem-v1` revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`。
- 官方固定数据卡：<https://huggingface.co/datasets/bowen-upenn/PersonaMem-v1/blob/fd7c30f071d5c2ee2a211506783be222d7b6002e/README.md>（本地副本 `personamem_sources/hf_pinned_README.md`）。数据卡 L20–28 将长度版本命名为 split；L43–54 解释 token 长度；L60–76 解释字段及 cutoff。
- 注意：PersonaMem-v1 的 arXiv **论文第二稿**和 PersonaMem-**v2 数据集**是不同概念。

## 源码默认与实际执行路径

| 项目 | 核验结果 | 固定来源 |
| --- | --- | --- |
| 默认模型/版本 | CLI 默认 `gpt-4o`；示例 `inference_gpt_4o.sh` 也是 gpt-4o，默认数据为 128k | [CLI L281–289](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L281-L289)、[脚本 L4–11](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/scripts/inference_gpt_4o.sh#L4-L11) |
| 输入 | 先按 `end_index_in_shared_context` 截断未来消息，再发送全部已有历史，末尾附问题、4 个候选回答及回答标记说明 | [cutoff L216–221](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L216-L221)、[prompt L25–40](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L25-L40) |
| top-k / chunk / embedding / reranker | 上述完整历史评测路径不涉及这些参数；检查 README、所有推理脚本及全仓代码未找到对应 RAG 实现。此为已检查源码范围的结论，不替代论文其他实验的描述 | 同上完整执行路径；本地 clone 可复核 |
| 输出与采样预算 | OpenAI 只显式传 model/messages；Gemini、Lambda 同样未设 max output/temperature。Claude 则显式 max_tokens=128000 | [多后端 L54–101](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference.py#L54-L101) |
| 模型调用数 | 正常评测循环每个 CSV 问题调用一次 `query_llm`；没有多跳检索/多轮反思环节 | [循环 L197–221](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L197-L221) |
| 评测指标 | 4 选 1 正确率；`<final_answer>` 后提取 a–d，必须提取集合只等于正确选项；还会 fallback 到完整回答提取。它不是自由文本 ROUGE/BLEU 或 retrieval recall | [答案判定 L48–78](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L48-L78) |
| 错误样本处理 | 公布脚本异常时只记录错误并 continue，未给该题写 score 行。复现若只对成功行求均值会改变分母，须另外保留全题分母和失败数 | [L256–267](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L256-L267) |
| train/dev/test | 评测函数遍历传入 CSV 所有行，未做 train/dev/test 拆分；HF 公布 split 按长度命名 | [L156–178](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference_standalone_openai.py#L156-L178)；固定数据卡 L20–28 |

## 32K 的构建含义及本地数据实测

官方生成代码把 10 个 conversation blocks 命名为 32k、20 个命名为 128k、60 个命名为 1M；生成脚本默认 20 个 persona、每个 2 个 ordering variants。这是发布生成脚本的设置，不保证其它 release 恰好满足相同计数。

- [长度命名映射 L286–299](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference.py#L286-L299)
- [生成脚本 L12–34](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/scripts/run_generate_benchmark.sh#L12-L34)
- token 统计使用 GPT-4o tokenizer：[L603](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference.py#L603)、[计数 L168–173](https://github.com/bowen-upenn/PersonaMem/blob/d07e6ade22e85e0e5d562247323a9c3e07553226/inference.py#L168-L173)。这不能当作 Qwen/DeepSeek 服务的精确输入容量。

本地固定 `questions_32k.csv` 只统计 metadata 列，不使用答案标签：`csv.DictReader` 物理读取并解析了包含 `correct_answer` 的 CSV 行，然后仅选择 persona/question/type/context ID/token-length 五个字段计算下表；未读取 `evaluation_only.json`、未输出正确答案或将其用于调参。不能将此过程表述为“从未读取任何含标签文件”。

- SHA-256：`cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c`，与 BridgeTree 固定值一致。
- 589 题、20 personas、题目引用的 37 个 shared context IDs。
- `context_length_in_tokens`：最短 15,560、最长 29,539、均值 24,845.82、中位数 25,690。
- 没有 train/dev/test 列。
- 机器可读报告：`personamem_sources/local_32k_metadata_stats.json`。

这说明 16K 的**完整历史**基线无法自然容纳该版本的大多数上下文，更何况还要加说明、选项和输出预留；但 RAG 只发送选中的记忆，所以不能把这个统计直接当作 RAG 中间步骤应该设置多少 tokens 的答案。若提高本项目中间推理窗口，应按服务实际支持容量、统一对照设置和成本报告说明，不能写成“PersonaMem 官方规定”。

## 对齐建议（研究建议，非论文事实）

保留固定 589 题和原始 cutoff、四候选选项、全题分母与 question-type 分组正确率；统一所有对照的生成模型及解码设置。将“完整历史基线的历史容量”“RAG 最终证据预算”和“多阶段方法的中间请求/总调用预算”分列报告。若采用本论文 RAG 参照，用 message 粒度与 top-5，并明确把模型替换为本项目统一后端是受控复现变体；不要把 user–assistant pair 或固定 token chunk 默认为论文原设置。
