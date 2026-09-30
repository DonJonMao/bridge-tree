# v2 两个 normal 独对案例：实际日志审计

审计日期：2026-09-30。只读分析现有模型输出；没有调用模型，没有改变实验代码。

日志根目录：`outputs/diagnostics/evidence_v2_20260930_logs/run/`。以 `outcomes/*.json` 为权威任务结果，结合 `candidate_pool/*.json` 中的原始 planner/map/select 请求与响应、`modules/context.jsonl` 的 `record_kind=task_snapshot` / `event=final_context` reader 请求，以及 `visible_memories/*.json` 中的原文。以下“正确”指现有 outcome 的评测标签，不代表已验证每一步推理正确。

## 结论先行

两个正常完成的 EB 独对案例，**都不能证明复杂搜索补回了 dense 缺失的决定性历史**：

1. `56fb1ba3…`：EB 最终原文集合为空。模型在没有任何检索历史的情况下答对，因此这次正确不能记作搜索/证据链成功。
2. `8f6defba…`：决定性历史是 dense 排名第一、双方均已拿到的 `m00002`。EB 只留这条及一条一般性补充历史后答对，dense 在较长上下文中选择了泛泛回复。支持“上下文组织/去噪可能影响 reader”的解释，但单次输出不能分离删去干扰、新增辅助历史和模型随机性。

两题 planner 均出现明确的任务理解问题：用户是在续聊，planner 却要求补充课程/项目的日期、地点、名称等事实细节；真正用于个性化回复的旧偏好/偏好变化没有成为核心需求。**“任务理解正确性”应排在继续增加搜索机制之前审查。** 这不是建议给 planner 暴露标准答案；query-only 也需要知道任务是基于个人历史回应用户，而不是补齐用户未问的事件信息。

“保留 dense 底座”仍适合作为受控消融，但本次两个 win 明确限制了这个建议：它保证保留原文，不保证保留 EB 的答题优势。尤其第一题 `D ∪ S = D`，恢复全部 dense 原文会回到本次已记录的 dense 错误输入；不能宣称该修改只修复 loss、不会损伤 win。

## 案例一：夏季辅导项目与冥想偏好

- persona：`6`
- question：`56fb1ba3-55fa-41a9-b638-28622623534b`
- dense task：`3b59796d46c19ec4e5d8698362a4f7422662856c0caf55bc6c33a8c347ff4e51`
- EB task：`66ff03c5c847b4b8a381da82a26732662ba4832aae9c5c5aa0e1b0cd9685f607`

用户当前消息说自己开展高中生夏季辅导项目，包含学习技巧、时间管理和“类似自己在冥想中学到的减压实践”。它不是询问项目名称/日期的事实问题。

reader 的四个选项都以肯定辅导项目开头，区别在于冥想偏好的历史顺序：

- (a)：起初喜欢冥想作为放松工具，后来失去兴趣，之后发现专注收益。
- (b)：起初无感，然后不喜欢，之后欣赏收益。
- (c)：起初不喜欢把冥想当专注工具，后来转而欣赏其收益。
- (d)：从最初就喜欢冥想的专注收益。

### 实际输入与输出

| 项目 | dense | evidence_bridge |
|---|---:|---:|
| 最终记忆数 | 12 | **0** |
| reader 输入 token 估计 | 5195 | 525 |
| reader 预算 | 8192 | 8192 |
| 预测 | (a)，错误 | (c)，正确 |

dense 选择：`m00038, m00021, m00089, m00039, m00066, m00022, m00005, m00063, m00077, m00037, m00064, m00032`。reader 按时间顺序渲染原文。

EB 的实际 `modules/context.jsonl` reader 消息在 `Retrieved personal memories (chronological):` 后是空白，之后直接接四个选项。不是日志遗漏，也不是用 claim 替代原文：权威 outcome 和 selection 的 `selected_ids` 都是 `[]`。

### 为什么会选空集

planner 的六个冻结需求是：项目名称、启动年份、合作学校名称、参与学生数、具体学科、量化成效。其中前五个标为必要，第六个可选。**没有冥想早期体验、后续变化或变化原因。**

之后实际执行：

- 30 个候选，260 个 source units 全部被成功评估；
- 0 个 evidence mappings，0 个 eligible memories；
- 六项 coverage 全为 missing；
- 20 次映射调用，加一次 plan、一次 select，合计 22 次 evidence LLM 调用；
- stop 为 `feedback_evidence_call_budget_exhausted`，未进行 gap probe；
- 没有 JSON repair、没有截断、没有 partially mapped，所以被计入 `normal`。

select 原始理由明确写道：`No evidence exists in the ledger to support any of the requirements, so an empty set is returned.`

这不是“充分证据支持了正确答案”，而是错误方向的需求使所有候选被排除，最后 reader 在空历史输入上选中了标签。无法从现有日志判断这是选项先验、较少干扰还是随机波动；能确定的是没有检索证据贡献。

### 原文核查

dense 已有的 `m00021`、`m00038`、`m00089` 都有对冥想专注收益的正向描述；`m00022` 有 `encouraged me to try again`。这些可以支持“后来认可冥想”，但不自动证明选项 (a) 的完整变化顺序。

可见历史中 `m00008` 的用户说改用 flashcards “worked better for me”，助手接着说 `Sometimes meditation apps don’t work for everyone.` 这条包含早期不适配的线索，**不在 dense 最终集合，也不在 EB 的 30 个候选池中**。由于前后文和角色问题，不应把这句助手话直接等同用户明示“不喜欢冥想”；它至少说明不能把空集答案称作有原文支持的早期偏好推断。

### 对修法的约束

此题 `S=∅`，所以保留 dense 后的 `D∪S` 就是原 dense 集合。按相同 reader/渲染得到的是已记录的 dense 输入，当前输出为错误 (a)。重跑是否仍错未知，不能证明新增底座必然降低准确率；但足以否定“保底座不会损害现有 win”的保证。

真正直接可见的问题是 planner 没有识别个性化续答任务，以及 `normal` 标签允许“所有源评估完但没有任何可用证据”。建议在分析上另列 `normal + empty evidence`，不把它当作证据机制成功；这不要求伪造失败标签或改变已有结果。

## 案例二：周末烹饪课

- persona：`3`
- question：`8f6defba-992d-45f1-9a7d-dded76e6e5d5`
- dense task：`10f5404dd425a90c04d15884122333a23c2ecbe8bfb8e1fac5947f4d704a5e6a`
- EB task：`0d28cb854f65e97ef2b3b7112f4eaa96e214fc20e166643a3985ef1fed2c37c9`

当前用户消息：`Over the weekend, I spent some time at a cooking class.`

reader 选项：

- (a)：记得你不喜欢烹饪课；
- (b)：记得你喜欢音乐节；
- (c)：泛泛表示周末尝试烹饪课很愉快；
- (d)：记得你以前喜欢烹饪课，很高兴你又能参加共享活动。

### 实际输入与输出

| 项目 | dense | evidence_bridge |
|---|---:|---:|
| 最终记忆数 | 12 | 2 |
| reader 输入 token 估计 | 4422 | 884 |
| reader 预算 | 8192 | 8192 |
| 预测 | (c)，错误 | (d)，正确 |

dense 选择：`m00002, m00062, m00011, m00051, m00068, m00023, m00054, m00048, m00067, m00027, m00049, m00060`。

EB 选择：`m00002, m00046`。与 dense 交集为 `m00002`；删掉 11 条 dense 原文，增加 `m00046` 一条。

### 决定性历史 dense 已经有

`m00002` 的用户原文：

> I actually joined a weekend cooking class recently. It’s been a fun way to meet people who share my love for cooking. … it’s a great break from the usual routine and allows me to unwind while doing something I love.

这条是 dense 检索第一名，也是 dense reader 按时间顺序看到的第一条原文，直接支持正确选项 (d) 中“你以前喜欢烹饪课”。因此 dense 这次错误不能归结为没召回关键喜好。

新增 `m00046` 的用户内容只说正在探索约会与新活动，包括“从 cooking 到 outdoor adventures”的课程/社交活动；助手接着举 cooking classes 有助建立联系的例子。它提供一般背景，但不是首次带来“以前喜欢烹饪课”的证据。

`m00046` 在 `initial_bridge:00007` 已被发现（以 `m00023` 作种子，命中 rank=3）；因此它也不是后续多目标 A 搜索或 gap retrieval 才发现的记忆。后续 conditional 阶段又返回过它，但首次发现发生于初始桥接扩展。

### 规划与选择仍有错位

planner 冻结需求为：课程类型/主题、具体日期、地点、菜品、厨师、体验/成效。前四项必要，后两项可选。应服务个性化回复的“用户以前是否喜欢这个活动”只与最后一项可选体验需求部分相近。

29 候选、245 units 全部评估，形成 31 mappings，6 个 eligible memories。最终 coverage 只有体验这一项 covered；三项 partial、两项 missing。做过一次 gap 检索，最终 stop 为 evidence call budget exhausted。期间一次覆盖修复，未导致 terminal failure，故仍属于 normal。

select 原始响应已说明 `m00002` 是主要信息源，`m00046` 只是一般性补充，不能填补地点/厨师等缺失。最后的 reader 没有收到这些 coverage 或 explanation，只收到两条原文与相同选项。

### 能得出的结论与不能得出的结论

可以确定：EB 没有补回 dense 缺少的决定性历史；它大幅改变了上下文，保留一条直接证据并去掉许多画画课、聚餐、Zumba、旅行等旁支记忆后，reader 从泛泛回复改选个性化回复。

尚不能确定：仅 `m00002` 就能稳定复现 (d)；`m00046` 是否必要；dense 的 11 条其他记忆是否具体导致干扰；是否存在 reader 单次随机波动。需在固定 reader 下比较 `m00002`、`m00002+m00046`、`D+m00046` 等受控输入才能拆分。

## 全体已完成配对任务的集合观察

本日志导出比用户粘贴的 72 题稍晚：normal 配对为 **73** 题，新增一题双方都错。这里只统计双方权威 outcome 均成功的同 persona/question，未把 live/task_snapshot 重复累计。结果独立读取 outcomes 与每题 candidate_pool 得到。

| 集合指标 | 全部 EB 成功配对 | normal 配对 |
|---|---:|---:|
| 配对题数 | 146 | 73 |
| dense 答对 | 100 | 55 |
| EB 答对 | 93 | 52 |
| dense 最终记忆全部在 EB 候选池 | 146 | 73 |
| EB 最终删去至少一条 dense 记忆 | 145 | 73 |
| EB 最终集合是 dense 子集，含空集 | 92 | 54 |
| EB 最终有 dense 外新增记忆 | 54 | 19 |
| EB 最终为空集 | 14 | 10 |
| 两方法最终集合完全相同 | 0 | 0 |
| EB 最终保留全部 dense 记忆 | 1 | 0 |

normal 中的 10 个空集全部是 0 mappings；其中 6 个答对、4 个答错。配对分解为双方正确5、双方错误2、EB独对1、dense独对2。**空历史上碰巧答对是准确率的一部分，但不能作为桥接检索或证据选择具有有效性的证据。**

normal 的 73 题中，50 双方正确、16 双方错误、2 EB独对、5 dense独对。两个 EB 独对的详细情况如上；5 个 loss 由另一份逐题审计负责。

这组观察强化了“候选扩大后存在大量原文删减”的事实，但不能单独证明每次删减都有害。事实上，烹饪课独对支持精简可能有利；空集独对更说明单次答题正确不等同证据机制正确。

## 修法优先级修正

1. **先校正 planner 的任务定义**：区分明确事实问题与个性化续聊。后者需要相关既往偏好、经历、变化，不应凭空把日期/地点/名字标为必要。仍保持 query-only，不把标准答案或选项偷偷喂给规划。
2. **让映射成为可审计信息，而不是唯一的删除依据，需作为独立消融验证**：当前数据确认所有 dense 记忆进入了候选，却经常被整体删除；但取消门控或保留 dense 并不是已证明最优。
3. **将 dense 底座方案作为单独受控对照**：同 reader 预算下比较，不与需求修订/搜索改动打包。第一题会失去现有空集输入；第二题也可能重新引入旁支内容，所以需要同时观察 gain 与 loss。
4. **先不继续增加搜索**：两个 win 没展示后续复杂搜索发现决定性新增历史；本批 73/73 dense 原文已在 EB 候选池，增加召回不能直接修复错误的需求与删除。

来源定位：两个 task ID 分别对应 `outcomes/<task_id>.json`、`candidate_pool/<task_id>.json`；原文文件为 `visible_memories/56fb1ba3-55fa-41a9-b638-28622623534b-7778082d5af5.json` 和 `visible_memories/8f6defba-992d-45f1-9a7d-dded76e6e5d5-375b219ff376.json`；实际 reader 请求可按 task ID 在 `modules/context.jsonl` 中唯一定位到完成的 task snapshot。

## 补充：另外五个非 normal 独对案例

为避免只检查正常子集而遗漏真实搜索收益，继续核对了全部成功配对中的另外五个 EB 独对题。范围为实际最终 reader 原文、候选首次发现来源、两方法最终选集及选项区别；没有进行反事实模型调用，也没有把新增来源自动归为答对原因。

**这里确实发现一例有意义的定向补检增量：`1da9453e…` 的 `m00016` 由 evidence gap 阶段首次找回，补上了更早的书评博客负向经历。** 因此不能把“两个 normal win 没体现新增关键历史”推广为“整个 run 的搜索完全没用”。但该例仍没有隔离出新增记忆对正确答案的因果贡献，而且增量来自 gap 检索，不是 A 条件搜索首次发现。

| 题目 | 完成类型 | EB 原文数 | 新增至 dense 外 | 快速审计结论 |
|---|---|---:|---|---|
| `1da9453e…` / persona 1 | truncated | 16 | 8 条：5 initial_bridge、3 evidence_gap | **gap 新增了相关的早期负向博客经历**；dense 已有后期负向/恢复经历，尚未证明新增是答对必要原因 |
| `b8e89a15…` / persona 6 | truncated_and_partially_mapped | 4 | `m00087`，initial_bridge | 决定性 yoga/meditation 记忆本来是 dense 第一名；新记忆弱相关 |
| `8823918d…` / persona 3 | truncated | 5 | `m00025`，initial_bridge | 决定性重新喜欢读书会的 `m00059` 已在 dense；新记忆是 karaoke 焦虑 |
| `d43bdf34…` / persona 8 | partially_mapped | 1 | 无 | 只保留 dense 第一名，泛泛回应变成回忆用户喜好的回应 |
| `bdeba04a…` / persona 6 | partially_mapped | 3 | 无 | 全是 dense 子集；选中原文不能直接支持选项区分所依赖的早期冥想偏好 |

### 1da9453e：gap 找到早期负向博客经历，属于真实相关信息增量

- question：`1da9453e-94f6-4e6d-9ae4-b7481217fdd1`
- EB task：`6ba88b5c67aa0975467c884a5351e9882afa45006266245bd7908a6a51debba0`
- dense task：`3ea4ec80716b09569060cc119976bd6c5d61984a63abce269d95bf362910cc14`

当前用户说重新开始 book blog，探索文学的情绪反应。正确 (a) 回忆先前不喜欢“书籍博客”，dense 错选 (b)“体育博客”；其他选项区分最初无感或最初喜欢后来不喜欢。

dense 的 `m00026` 已经写出“文学内容持续产出的压力使自己害怕写作，决定退一步”，`m00037` 已写出恢复写书籍博客。EB 两条都保留，并新增：

> `m00016`: I even started a blog about book reviews, but I lost interest quickly. It felt more like a chore at times. … the excitement fizzled out … the pressure to consistently produce content.

这条原文比 `m00026` 更早，直接提供书评博客失去兴趣/变成负担的阶段。首次发现来源是 `evidence_gap:00035`，probe 明确查询未满足的 r1：用户以前的 book blog，包括原本内容和活跃时间。该次结果为 `m00016,m00020,m00019,m00033`，其中 `m00016,m00020,m00033` 最终入选。

其余最终新增 `m00013,m00031,m00027,m00029,m00028` 来自 initial_bridge，分别涉及作者启发/书店、作者播客、放弃书评写作、书籍产品与周边。无最终新增记忆首次来自 conditional 阶段。

**判断：有明确新增相关原文，最强的正面案例是 targeted gap 恢复更早的阶段。** 但 dense 不是完全没有“书籍博客负向体验”证据；它错选 sports 的原因不能仅从集合断言。需要移除/加入 `m00016` 的同预算配对，才能证明这条导致准确率收益。planner 在这题有“以前的 book blog”这一需求，说明需求正确时 gap 机制具有合理的信息增量路径。

### b8e89a15：核心减压活动原文在 dense 第一名

- question：`b8e89a15-dbb5-4309-868a-3755bcb6b5da`
- EB task：`d5b23466b558588e3ec5d20cde2d9795e85bcb38da60c461d56586421fa76e5e`
- dense task：`e5c3f70c91a9166ad9dfc9c8515d0eb7027d9dcf67b24f105b73a999b212b503`

用户说周末做活动缓解一周 consultations 的压力。dense 错选泛泛建议探索新放松方式，EB 正确选回忆 yoga 和 guided meditation 的 (a)。

双方都有、且 dense 排名第一的 `m00066` 几乎逐字说明：`practiced yoga and meditation after a particularly long week of consultations`，以及喜欢 `gentle flows and guided meditation`。它已直接区分正确选项。

EB 最终 `m00066,m00081,m00082,m00087`；后三条分别包含健康愿景板/园艺挑战、园艺积极体验、公开演讲效果和停止用复杂学习指南。其中新增 `m00087` 来自 `initial_bridge:00011`，不是瑜伽/冥想偏好的缺失证据。最合理的待测方向是精简/上下文选择影响，而非补回关键历史。

### 8823918d：读书会偏好变化已在 dense，新增 karaoke 不决定正确选项

- question：`8823918d-36cc-4caa-87f7-075f846a0be5`
- EB task：`067b3edf23fb998ee5e79ede9126d33671a2c5b4990c1e0906e5300e8a45185a`
- dense task：`1a719e6ea1b7c1b0a383134fe6745e7fada7f93cf2ae6540b9d6d2dd2a1d24e4`

用户说不再享受读书会，分享思想的压力太大。正确 (d) 回忆曾因讨论和人际联系重新喜欢读书会；dense 选 (b)，强调自己阅读的宁静。

EB 选择 `m00047,m00014,m00059,m00021,m00025`。`m00047` 说退出过度学术化的重返读书会、想念独自阅读；`m00014` 说读书会缺乏社交而失望；`m00059` 说重新加入文学小组、怀念 camaraderie 和 thought-provoking discussions。**这三条都已在 dense**，其中 `m00059` 直接支持正确选项的重新欣赏讨论/社交。

新增 `m00025` 在 `initial_bridge:00009` 首次命中，描述初次 karaoke 紧张自觉被注视。它可能提供一般性社交压力背景，但没有新增读书会经历。日志不能证明新增这条有益；也不能把 dense 选择另一段真实历史的原因简单归为缺信息。

### d43bdf34：只留 dense 第一名，未发生新增检索收益

- question：`d43bdf34-9dfb-4792-8e76-6b5780633457`
- EB task：`484f0efe68be4cb70dc2db4475a5084fbabf623047624dd9bfc94a3d8b61d704`
- dense task：`5de8c211be1cefbcca59e765e83a9fc1ff19563ba69ba4eb660ab53d0bf90b99`

用户说又去博物馆特别展览，遇到有趣的人。正确 (c) 回忆用户喜欢博物馆；dense 选 (a) 泛泛回应。

EB 仅选 `m00064`，也是 dense 第一名。用户原文明确形容博物馆体验 fantastic、invigorating、delightful，并在展览遇到艺术趣味相同者。此例直接证实 EB 可以在不新增原文的情况下答对而 dense 错，属于更短上下文/重组与 reader 输出的差异，未隔离其因果机制。

### bdeba04a：全为 dense 子集，完整偏好链未被提供

- question：`bdeba04a-c530-4d9f-8f1c-b28ef539cd37`
- EB task：`83a4cdb81b7311f19693c0be8d9307783515dfec2f83cc48cddca133bf983aeb`
- dense task：`40adfc16440151ccc040748df17c2ae76afcd4af8a916bebd86873fa0d7a7d6d`

用户谈学习小组将 flashcards 变得更有趣。正确 (d) 和 dense 错选 (c) 的区别是最初“disliked meditation for focus”还是“enjoyed meditation for focus”；两项后面都包含冥想变有效、曾不喜欢 flashcard、现在喜欢。

EB 只选 `m00093,m00028,m00017`，三条全在 dense 中。核对完整用户及助手原文：分别是让 flashcard 色彩/形式更有趣、学习小组视频分享、协作调研学习 app，**都没有提供早期冥想喜好或完整历史变化链**。所以 EB 虽答对，不能认定检索/证据链完成了答案中的历史推理；与第一空集 win 类似，需要区分标签正确与证据充分。

### 七个独对的范围结论

7 个 EB 独对中，3 个最终集合没有 dense 外新增（含1空集）；4个有新增。最终全部新增共11条，首次来源为8条 initial_bridge、3条 evidence_gap，**0条首次来自 conditional**。这只说明这些 win 中没有“最终选中了 conditional 首次发现的记忆”这一直接收益路径，不能排除 conditional 候选通过后续映射/截断/选择间接影响决策。

至少一例 gap 有清楚的相关信息增量，因而保留需求定向补检作为待验证机制是合理的；继续声称复杂搜索整体无价值则超出日志证据。更精确的下一轮比较应拆开 initial bridge 扩展、A 条件搜索和 requirement gap，而不是把全部额外检索算作同一个收益来源。
