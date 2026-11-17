# PrefEval：论文与公开实现设置复核

核验日期：2026-10-12。仅阅读论文、会议页和公开源码；未调用生成模型或读取本项目评价标签。

- 正式会议：[ICLR 2025](https://iclr.cc/virtual/2025/poster/29686)。题名 *Do LLMs Recognize Your Preferences? Evaluating Personalized Preference Following in LLMs*。
- [论文](https://arxiv.org/html/2502.09597)，主要依据 §3.1、Appendix A.3/A.4/A.7/A.8。
- 作者仓库：[amazon-science/PrefEval](https://github.com/amazon-science/PrefEval)，本次固定 commit `50795054b5ff5f418d2b768a331d71e480f93331`。
- 原始下载与 SHA256 清单在 `prefeval/source_manifest.json`。

## 论文报告

1. RAG 使用 `princeton-nlp/sup-simcse-roberta-large`，按当前 query 与历史内容相似度取 top-5 exchanges。A.7 比较不同 k，说明 k=5 与 k=10 的生成效果接近；k=10 召回更好并未带来更好偏好遵循，主表采用 k=5。
2. 主要方法对比使用 Claude 3 Sonnet/Haiku、Llama 3 8B/70B、Mistral 7B/8x7B。其他模型的子集结果和主表不能混为一种设置。
3. A.8 的 10/70/300 turns 约对应 3K/23K/100K 历史长度。这是偏好与目标 query 之间的对话条件，不能当作统一 LLM 请求 token 上限。
4. 有生成任务和 MCQ 分类任务。生成偏好遵循评价使用 LLM-based evaluation；MCQ 是分类准确率。均不是 PersonaMem 的同一批题。

## 代码核验与易误读点

- [generation_task/benchmark_generation.py:59](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/generation_task/benchmark_generation.py#L59) 和分类入口默认 `topk=5`。
- [config.yaml](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/config.yaml) 设置 `max_gen_tokens=300`、`max_mcq_tokens=5`。
- [utils/common_utils.py:43](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/utils/common_utils.py#L43) 默认温度 0。Claude/Mistral/Llama 分支传 output cap；GPT/Gemini 分支对应参数被注释，不能宣称所有模型实际采用同一解码参数。
- [generation_task/baselines_handling.py:64](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/generation_task/baselines_handling.py#L64) 显式偏好分支从预存分数中选择 role-tagged 消息，用户偏好与助手响应是两个候选项。不能直接等同于本项目的 user–assistant pair。
- **公开实现保留原历史，再追加 top-k 提示。** [utils/explicit_utils.py:388](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/utils/explicit_utils.py#L388) 先加入 preference/pref_generation 和 `multi_inter_message`，然后加入包含检索结果的新 query；[implicit 对应函数](https://github.com/amazon-science/PrefEval/blob/50795054b5ff5f418d2b768a331d71e480f93331/utils/implicit_utils.py#L387) 也保留 conversation 和中间对话。

因此，不能把 PrefEval 描述为“总输入只有五条记忆”，也不能据此断言其所有实验只需几千 tokens。top-k 是检索提示数量，历史长度与总输入容量是另两项参数。

## 对当前 a48 实验的适用范围

可借鉴：保留显式/隐式偏好任务区分、冻结 k、使用同一模型与评价方法、分别报告检索召回与最终偏好遵循。

不可直接移植：将其 top-5 当作 DAG 每次读取的硬截断；将 MCQ 的 5-token 答案上限用于携带 typed values 和 provenance 的结构化中间输出；以它为 residual 单独扩容 24K 的依据。

本项目如迁移该方法，应明确命名为 PrefEval-style RAG port，并记录数据、模型、消息切分及保留全历史的差异；不能直接拿原论文分数与 PersonaMem 比较。
