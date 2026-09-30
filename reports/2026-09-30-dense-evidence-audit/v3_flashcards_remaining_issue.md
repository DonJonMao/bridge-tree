# Flashcards：v3 已保留正确历史，reader 仍选错理由

2026-09-30；真实服务开发 smoke，只读诊断，未新增模型调用。题目 `dbbd6663-a17f-4b84-8579-6d39ad99c738`，persona 6。数据是正式 PersonaMem 题目的开发子集；运行 API 将显式子集 identity 标为 synthetic，不是模拟模型结果，也不是未见测试集。

**可确认的结论：本次失败已经不是 m00036 未进入 reader。v3 的实际 reader 输入完整保留了直接区分正确选项的历史，但模型仍把旧问题的原因选成“重复、无趣”，而不是原文的“不能促进深度学习”。这证明恢复证据可见性不等于答案恢复正确。** 单次对照不能进一步证明四条删减、位置变化或服务非确定性中哪一项造成答案差异。

## 本次实际对照

| 项目 | dense | evidence_bridge v3 |
|---|---:|---:|
| 实际选中原始记忆 | 12 | 8 |
| reader 估算输入 tokens | 4759 | 3458 |
| 服务报告 reader 输入 tokens | 4878 | 3529 |
| 预测 / gold | a / a，正确 | b / a，错误 |
| reader 调用 | 1 | 1 |
| 额外 evidence 调用 | 0 | 21 |

两个原始 reader 请求的 system、query、四个选项、模型 `deepseek-v4-flash`、temperature 0、max_tokens 512 和 endpoint identity 全部相同。两次 HTTP 均一次成功、finish_reason=stop、无拒答，结果无解析失败。请求间变化是历史集合及随之变化的记忆编号、文本位置；不能仅因 temperature=0 就认定服务绝对确定。

v3 的 8 条是 dense 12 条的严格子集。逐条从 `serialized_context` 的 **Retrieved personal memories 段**分离原文后，与 `visible_memories` 比较：全部选中记忆全文和角色标签逐字一致，没有把选项里出现的文字当成历史证据。m00036 位于 dense 第 9/12 条、v3 第 5/8 条；这不是被摘要或截断后的引用。

## 历史和答案的实际语义

两个 reader 都收到下面的历史变化链，按相同观测顺序排列（time 是消息顺序，不是日历时间）：

- m00008，20：闪卡用于备考，曾经适用。
- m00026，56：曾喜欢闪卡，后来认为过于简单，需要更复杂、更全面的学习方法。
- m00027，59：尝试结合闪卡与间隔重复的新应用。
- m00036，78：明确说 “weren't conducive to deep learning”；随后解释闪卡主要带来 “surface-level retention”，因此转向强调批判思考、知识应用和跨内容联系的综合课程。这是学习深度不足，不是单纯重复或没有趣味。
- m00093，210：通过颜色、主题、数字/实物形式重新利用闪卡，变得有趣、利于记忆。
- m00094，211：当前 query 本身，强调同伴挑战、合作和竞争，让学习更有效、更愉快。

gold a 的旧理由是 “less conducive to deep learning”，直接对应 m00036。v3 选中的 b 将旧理由说成 “repetitive and unengaging”。它大体承认“过去不满意、现在喜欢”的变化，却没有准确保留不满意的具体原因。这两种解释相近，但并不等价：原文承认闪卡可以有趣，仍可能只促进表层记忆。故本例更准确的诊断是 **已有证据的理由辨别失败**；不能直接断言模型完全没有读 m00036，也没有证据显示代码打乱了时序。

v3 此次 planner 已询问过去体验和理由；m00036 有 11 条已验证映射，其中 r2 明确归纳“surface-level retention / wanting more depth”。selector 的 coverage 也引用了该原因并保留 m00036。诊断为 `mapped_only`、`evidence_raw_selected_count=0`：本题不能表述成“仅靠未映射原文通道救回”，需求/映射本身也已改善。reader 实际只收到原始记忆，不收到上述 coverage 解释。

## 删掉的四条是否是必要证据

| dense 独有、v3 未选 | 实际内容 | 与 a/b 区分的关系 |
|---|---|---|
| m00003，6 | 学习小组交流资源、讨论、批判思考 | 增加合作学习背景，没有给出另一条闪卡旧理由 |
| m00017，38 | 合作研究学习应用、调查同学意见 | 增加协作和学习技术背景 |
| m00029，63 | 分享学习视频后受鼓励，计划用博客记录 | 与已保留 m00028 的视频/小组经历相邻 |
| m00031，67 | 与同学分享学习指南，深化理解、保持动力 | 增加合作促进理解的背景 |

未发现这四条中存在 v3 缺失的、直接区分 a/b 的必要事实；关键旧原因和当前改善在 v3 已同时可见。它们可能改变合作、深度理解与竞争等主题的相对权重，但“删掉它们造成错误”仍是待验证假设。v3 还保留 m00076 的健康挑战/友好竞争经历，这是跨领域类比材料；它是否干扰答案也未由此次对照证明。不能仅据 b 的“competition”用词就判定它受该条误导。

v3 的选择输入确有 ledger 预算截断且部分映射未完成，reliability 为 `truncated_and_partially_mapped`；但 12 条 dense 原文在 raw review 中均完整可见，实际 reader 的 8 条也都完整。这些状态值得继续分层统计，不能代替此题具体的证据链核验，更不能直接当成本次答案错误的已证实原因。

## 本轮处理与边界

保留既定的相同 reader，不因这一个开发题临时改提示词、补一次答案或增加重试。将本题记录为“关键历史已恢复、结果仍错误”，不计作准确率改善案例。后续若研究原因，应预先固定重复测量/上下文消融方案，分别检验集合删减、呈现位置和输出稳定性；本次未执行这些实验，不能给出其因果结论。

核验来源（均相对项目根目录）：

- `outputs/diagnostics/evidence_v3_live_smoke/formal_run/modules/context.jsonl` 第 3、4 行：两个冻结 reader 原始请求和完整历史。
- 同目录 `outcomes/764ce12141da5ef3e7efabd644cf9c6616a07758bb7ebdb5557d87cf96470da3.json`（dense）及 `outcomes/50de52575d1c81bb737590c7ea8d386dd5c708ccaaf95b748fb057a295e65e14.json`（v3）：预测、正确性、选集和成本。
- 同目录 `candidate_pool/50de52575d1c81bb737590c7ea8d386dd5c708ccaaf95b748fb057a295e65e14.json`：需求、映射、选择/修复原始响应及预算状态；`visible_memories/dbbd6663-a17f-4b84-8579-6d39ad99c738-2c3fe05607f4.json`：原始记忆与角色。
- 同目录 `modules/requests.jsonl` 中 `operation=generation` 的 `http_attempt_completed`：真实服务成功状态及 token usage。
- `data/processed/personamem-v1/32k/queries.jsonl` 第 86 行：正式 query、选项和 gold a。gold 仅在此诊断核对，不是证据模块输入。
