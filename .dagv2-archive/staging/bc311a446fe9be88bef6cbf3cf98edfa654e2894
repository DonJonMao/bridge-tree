# R20 PersonaMem terminal 相对选择契约只读复核

检查冻结源码 6c046374 及第 4 题实际 Call 7 system/user wire。实际 wire 包含全部 4 个公共选项，与 pinned public question 一致；原用户话语一致。未读 gold 或评分，未导出题目、选项、答案文本，未改源码/运行。

结论：现有 prompt 已明确是在四个候选中比较并选择最合适者，并没有要求存在“绝对完美”的选项；因此不能说相对选择目标完全没有实现。但“相对最优”与“没有选项达到绝对满意程度”的弃答边界没有单独解释，这仍可能留下模型解释空间。

## 实际请求里已存在的原文

comparative_task:

> PersonaMem asks which response best addresses the original user utterance using
> personal history.

all_options_dimensions:

> At response selection compare ALL public_options for personalization, relevance,
> contradictions and current applicability.

supported_best_fit:

> For the personalized response-selection terminal ONLY, support means a source-grounded assessment that this candidate response best fits the user.

prospective_suggestion:

> A prospective suggestion need not have occurred
> in the memory: its personal fit must be supported, without asserting unavailable
> external facts such as live availability.

abstention:

> If the evidence cannot discriminate the options, leave the answer unresolved.

four_options:

> The four public_options correspond in list order to (a), (b), (c), (d).

whole_value:

> Each support value asserts the WHOLE value of that variable, including set/record
> variables.

null_for_unsupported:

> Unsupported conclusions
> have null labels.

## 判断边界

1. `best`、`compare ALL public_options` 和 `candidate response best fits the user` 明确给出了比较目标；实际四个候选也确实在请求中。这不是缺少 options 或把最终任务完全写成原子事实认证。
2. 现有 abstention 是“证据无法区分选项”，并非“所有选项都不够理想”。若证据能支持候选之间的相对差异，即使所有候选都有不足，后一陈述不能自动推出前一陈述。反之，如果关键比较条件确实缺失、冲突或无法区分，保留未决仍然与当前契约一致。
3. 当前 prompt 没有明确补充“所有候选可能均不完美，但只评价现有候选的相对适配”以及对应的弃答判据；通用 WHOLE-value / supported / null-label 规则又与个性化 best-fit 指令同处一份长 prompt。这是可辨认的解释边界，不等于已证明代码逻辑矛盾或本题应强制成功。
4. 第 4 题 Call 7 同时给出一个合法选项的 support 与未决/顶层 null，随后 Call 8 合法修复了 terminal 字段，但原义务仍保留。它证明模型在支持和保留意见之间产生了需要处理的不一致；不凭这个结构证据断定其未决一定虚假，也不能据此删除本题未决或强制成功。
5. 一般性语义审查应区分：缺了什么具体、会影响候选排序的证据条件；以及模型只是对所有候选的绝对质量不满意。此检查不决定哪个公共选项正确，也不提出按本题改结果的方案。

来源：dagbt/personal_task.py:115（final selection）；dagbt/joint_reading.py:1482 附近的 personalized terminal support 定义；dagbt/personamem.py:41（四选项输出契约）。所有引用均已核对存在于实际 Call 7 system，而非仅存在于源码。

JSON SHA-256：`46ad5aa9e7f89f67a4d53aeda2e6f5ce9e5a59116bf9eef53458769d3cc6ac11`。
