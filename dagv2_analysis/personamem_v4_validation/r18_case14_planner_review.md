# R18 第 14 题规划失败：实际协议对照

冻结提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`，自然结果为 `execution_failed`。本分析仅检查保存的请求、响应结构与冻结源码；不读取标签、分数，不导出题目、选项或答案正文，不调用模型或 tokenizer，不修改源码或运行目录。

## 实际三次请求

| 调用 | 节点数 / 历史节点数 | 唯一节点执行 / 父数 | mode / result_type / explanation | 本地结果 |
| --- | --- | --- | --- | --- |
| 1 | 1 / 0 | compose / 0 | semantic / text / semantic | Compose requires parents |
| 2 | 1 / 0 | retrieval / 0 | value / text / none | PersonaMem requires semantic/text response selection |
| 3 | 1 / 0 | compose / 0 | semantic / text / semantic | Compose requires parents |

三次均为 `finish_reason=stop`，终端问题与原始话语相等。没有进入检索或 Reader。预算为 3 次 LLM、2 次本地 JSON 修复；不能把此例解释为下游容量、证据召回或答案选择失败。

## 指令与守卫

三次保存请求的 system 字节相同（15890 字符），完整包含 `PERSONAL_PLAN_GUIDANCE`，且有 PersonaMem 要求优先于通用 QA 示例的明确声明。它要求 1..5 个有用历史任务加一个 `compose` 回应终端、非空历史依赖，以及 `semantic/text/semantic` 契约。

- `dagbt/personal_task.py:9` 开始的明确任务指令与 `:149` 开始的 PersonaMem 校验，在以上要求上相容。
- `dagbt/local_terminal.py:55` 正确拒绝零父节点的 compose。
- `dagbt/personal_task.py:152` 正确拒绝 value/none；`:158` 另要求有历史父节点的 compose 终端。
- `dagbt/engine.py:117` 实际追加 PersonaMem 指令并调用个人任务校验，不存在没有启用任务适配的证据。

因此模型确实违反了已提供的明确自然语言要求。本例没有证明这些守卫互相矛盾、合法计划不可构造，或需要放宽守卫。

## 已确认的 schema 与校验范围差异

实际 system 末尾提供的 JSON schema 仍允许：

- `mode` 为 value、one_reason、all_failures、semantic；
- `result_type` 为 bool、entity、number、record、set、text；
- steps 的 `minItems=1`；
- `execution=compose` 与空 inputs 的组合，没有对应条件约束。

对三个实际响应使用实际请求中的 schema，离线 `Draft202012Validator` 检查 **3/3 通过**。这证明 schema 比生产守卫更宽：匹配该 schema 本身不保证满足 PersonaMem 或 compose 契约。它是可修正的协议对齐缺口，但并不逻辑要求模型违反更严格的文字指令。

原因可在冻结源码中对应：`dagbt/residual_plan.py:81` 的 personal_history 分支为变量增加 evidence_semantics 描述，却未收窄 `:114` 附近的输出契约枚举；`dagbt/local_terminal.py:11` 只为步骤加入 execution 枚举，没有条件性非空父约束。

三个实际 wire payload 均无 response_format 字段。当前是将 schema 放入提示的 plain 模式，不存在服务端强制结构解码保证；`dagbt/reasoning.py:70` 至 `:102` 的行为与记录一致。不能把这里描述成模型绕过了已生效的 constrained decoding。

## 修复反馈的实际边界

第二、三次请求都只有 system 和 user 两条消息。user 数据仅含 `original_input` 与 `validation_feedback`，没有前一份错误计划，也没有累计错误列表。

第二次仅反馈 compose 缺父，模型改为 retrieval/value；第三次仅反馈 PersonaMem 必须 semantic/text，模型改回 compose/零父。轨迹与只处理最近一类错误的往返现象一致；无法从外部记录确定模型内部推理或量化反馈设计的因果贡献。对应通用修复逻辑为 `dagbt/reasoning.py:213` 起：每次从 original 输入构造 current，只追加最近错误。PersonaMem 的完整 system 要求一直保留，不能称之为模型没有收到其他要求。

## 结论与可复核材料

本例同时有明确的模型违约，以及可以静态确证的 schema/本地守卫范围差异。下一步若做通用修正，应保持任务约束与现有预算，优先核对 PersonaMem 专用 schema 与规划修复反馈的一致性；本报告不授权改动、不承诺修复后必过。

结构化证据：`r18_case14_planner_review.json` 保存三个请求文件名、payload/system/schema 哈希、校验结果、有限枚举、节点/父数和固定错误反馈，不含原始题目或答案。
