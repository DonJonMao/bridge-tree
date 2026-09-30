# 五个 normal 组新增错误：真实 v2 日志审计

审计日期：2026-09-30。运行：`start_20260927_034132_625737`。本报告仅分析用户此前给出的五个 dense 对、evidence_bridge 错的题目，不把开发检查当作新的确认实验。

原始日志根目录：`outputs/diagnostics/evidence_v2_20260930_logs/run`。机器可读的任务 ID、实际 reader 请求比较、来源偏移、模型映射原文与需求见 [loss_cases_actual.json](loss_cases_actual.json)。没有改动运行代码，没有调用模型，也没有进行补证据重放，因此本文证明的是流程中实际发生的信息丢失，不能将单次答案差异当作严格干预因果。

## 可确认的共同事实

五对实际 reader 请求均不同，但除 messages 外的请求参数完全相同：同一 endpoint 指纹、`deepseek-v4-flash`、temperature=0、max_tokens=512。实际 ContextPlan 的生成预算均为 8192；dense 都保留 12 条原始 Memory。下表 token 数是日志记录的**完整 reader 输入估算**，包括 query、选项、提示词，不是纯 memory token，更不是总方法成本。

| qid 简写 | dense 答案/Memory 数/reader tokens | EB 答案/Memory 数/reader tokens | EB 候选数/映射数 | 主要观察 |
|---|---:|---:|---:|---|
| aa2c7800 | d / 12 / 4755 | c / 0 / 467 | 31 / 0 | 规划成烹饪视频通用效果评估；相关个人历史全被判无关 |
| dbbd6663 | a / 12 / 4759 | b / 5 / 2130 | 26 / 33 | 规划新玩法细节，遗漏过去拒绝 flashcards 的原因；m36 被映射排除 |
| 17273334 | c / 12 / 4521 | b / 3 / 1487 | 24 / 12 | 需求有过去课堂经历，mapper 仍错误拒绝直接支持的 m39 |
| 40d94e80 | b / 12 / 4577 | c / 0 / 566 | 32 / 0 | 规划成外部图书属性需求；个人阅读口味被判不属于推荐证据 |
| 2c7661cc | b / 12 / 5025 | a / 2 / 1520 | 30 / 30 | 只保留书友会相关片段；但 gold“最初喜欢”与可见历史有解释歧义 |

所有五题都是 `normal`：完整映射且未截断。但“完整映射”允许所有单元得到 `assessments=[]` + `irrelevance_reason`，并不保证映射语义正确。两个题在 0 条有效映射、空选集、全需求缺失的情况下仍算 normal，随后无个人历史进入 reader。这个状态定义是当前日志契约，不是结果伪造；它不能充当“算法机制已正确”的证据。

四个证据最明确的题（烹饪、flashcards、painting、书推荐），区分选项的历史都已经在 EB **初始召回池**，也在完整候选池，被 mapper 实际读取后判无关。最终 selector 没有机会选它们，因为没有生成有效映射、没有进入 eligible memory 集合。主要问题不是没搜到，也不是最后 selector 又删除了已正确映射的关键证据，而是需求与映射准入限制。

## 1. aa2c7800：通用问题解释替代了个性化依据

- qid：`aa2c7800-7f7d-401b-acfa-9af67910f9f7`，persona 1。
- dense task：`f0c041d28dd403e72496bb8e71435da6f6fd64896469d5e348d47323786c08db`。
- EB task：`e81d586fa8ac5130c3fa0e9d4698ee790762e08f132d9d1a576d024155fa0e15`。
- 实际 reader context：`modules/context.jsonl` 第 112 / 114 行。

query 问烹饪视频要不要写脚本。四个选项却在回顾书评与即兴讨论的历史偏好，正确项 d 强調以前觉得书评限制创造力。query 与选项主题确有错位，应作为数据/任务语义现象记录。

planner 的六项需求是：脚本/即兴视频观看参与与留存效果、制作时间与工作量、成功创作者案例、观众真实感/精致感偏好、表达自然度、变现/增长潜力。没有用户过去对结构化创作与自发表达的偏好。

初始池 m27 的用户原文（6:358）包含：

> I also abandoned the idea of writing reviews. I feel that they tend to limit my creativity ... a rigid framework ...

该片段实际进入 dense reader，未进入 EB reader。mapper `call_index=3` 将它判无关：

> User discusses abandoning writing reviews due to creativity constraints, not related to cooking videos.

m27 后半句对流动讨论的偏好也被拒绝为“不属于 cooking video scripting”。最终 31 候选、0 映射、空选集。dense 输出不但选择 d，还显式将上述偏好类比到 cooking videos；EB 无历史输入选择 c（过去喜欢结构与清晰），与 m27 相反。

**结论：已召回个人依据被对 query 的狭义领域解释排除。** 这比仅说“dense 信息多”更准确；决定性区别是 relevant personalized information 被需求边界判出局。不能据此保证补入 m27 的任何一次 reader 调用都会答对，但信息丢失路径已直接可见。

## 2. dbbd6663：旧历史原因仍被过滤，但过滤位置已经变了

- qid：`dbbd6663-a17f-4b84-8579-6d39ad99c738`，persona 6。
- dense task：`efe8672d22a2698a5421c654fea8a9f939e1663a07be36f23a60d78faeb268e6`。
- EB task：`b064e703ea9c56512bb35b1ada017a75455ea9adf97e454624f891866e539808`。
- 实际 reader context：第 233 / 235 行。

query 是现在借 flashcards 团体游戏获得乐趣。planner 必要需求是新玩法具体形式、挑战种类、学习科目、活动场所；另外问变化时间与学习效果。没有询问过去为什么不认可 flashcards。

初始池 m36（6:312）原文：

> I used to enjoy engaging in flashcard activities, but I realized they weren't conducive to deep learning ... surface-level retention ...

dense 第 4 条保留此 Memory，实际 reader 含该原文，选择 a。mapper `call_index=2` 给出：

> This unit discusses past flashcard use and its limitations, but does not describe the specific new method, challenges, subject, context, time period, or outcomes requested in the requirements.

这说明 mapper 并非完全没看懂片段：它识别出“过去使用和局限”，然后因为冻结需求没有这一项而排除。m93 的最近 flashcard 改造方式也因为“个人学习，而 query 是群体”被判无关。

EB 选集为 m94（当前 query）、m08、m41、m16、m30，5 条主要支持考试/小组/挑战的泛化细节；m36 不 eligible，不可能交给最后选择器。reader 选择 b，捏合为“以前重复且无聊”，与历史确切原因不同。

**结论：历史原因在初始召回就有，需求遗漏经映射变成了确定性准入排除。** 与旧 activation 的结果相似，但 v2 直接原因是需求→映射，不是旧 R 负边际。

## 3. 17273334：需求并非完全缺失，mapper 有可直接检查的语义错误

- qid：`17273334-b524-4398-baae-bfb459f149e0`，persona 3。
- dense task：`3ffdf6433d0315622e66ed87c44a4226240210f38a593c4574ddde2fe4e64084`。
- EB task：`b1ccd2edcc28f175e0947808203ba80166379fc5ce194a22f558baf03d07f6b4`。
- 实际 reader context：第 166 / 168 行。

planner 前四个必要需求问 art center 名称、加入日期、课程安排/结构、课程要教的媒介与风格。r6 是可选项：

> The user's previous experience with painting classes (e.g., when and why they stopped)

m39 位于初始池第 4 条，250:644 用户原文明确包含：

> I discovered that the structured environment of classes, while educational, often imposed a rigidity that stifled my natural inclination toward experimentation ...

mapper `call_index=2` 承认该单元讨论“偏好在线教程胜过结构化课堂”，却继续写：

> It does not provide ... the user's previous experience with painting classes.

这是对 r6 的直接漏映射，不能全部归为 planner 缺少需求。代码仍判成功，因为 source ID/JSON/角色等合法性检查不能验证这种语义否定。

最终 eligible 只有 m11、m28、m81，selector 三轮均保留这三条（最近参加画画课/工作坊/当前表态），缺少 m39。dense 选择 c，EB 选择 b（以前独自在自然中寻找灵感）；那不是被保留三条中的明确历史事实。

**结论：必要/可选权重使关注点偏向无关具体项，且存在独立的 mapper 语义错误。** 单纯增加 planner 提示或给出 r6 还不够；需要验证映射负判断或保留独立召回路径。

## 4. 40d94e80：把个性化推荐变成“历史里是否已有一份推荐答案”

- qid：`40d94e80-9557-48dc-9101-1cc6c12486a9`，persona 7。
- dense task：`c9fe5dbdebc1e5503eb253cddb24805d727555ee6c08cb3b90278af9b89a5c59`。
- EB task：`3edb1e93241a3ecf7893a96f2cad3dc521fc26d1ade047ded6c13cb035c97d12`。
- 实际 reader context：第 344 / 346 行。

planner 想找的是：正念/冥想/精神恢复书目、周末能读完的篇幅、实际练习、评价良好；没有用户偏爱的阅读主题。

dense 第 1 条 m03 的用户原文：

> creating a reading group dedicated to self-help books that explored the intricacies of relationships.

m31 也写用户创建书友会，重点是 `the psychological aspects of love`。两条都在 EB 初始池。mapper 分别判为：

> ... past experience creating a reading group for self-help books about relationships, not a request for a book recommendation for a weekend retreat.

> ... does not recommend books for a weekend retreat focused on mindfulness, meditation, or spiritual renewal.

这里映射器把“支持生成推荐的用户偏好”误要求为“已经包含推荐结果的原文”。甚至 m08 的用户正念 retreat 经历也因 `not a book recommendation` 全拒。最终 32 候选、0 映射、空 reader 历史；dense 选关系/依恋主题书 b，EB 选一般精神成长书 c。

**结论：个性化依据与答案内容被混淆。** 更多搜索不解决 mapper 对整个证据类型的拒绝。

## 5. 2c7661cc：真实缩窄与标签歧义需要分开

- qid：`2c7661cc-4a9f-4520-932b-46ec48f122c5`，persona 8。
- dense task：`456a30d10291cfc24c19c14562a6ea2973c1416b70fbfd9b64c372da2cd3ef82`。
- EB task：`61c4dffddc14f280ea07c6091e684cd034b86aad8e0e676add7fd8b9325cecfc`。
- 实际 reader context：第 487 / 489 行。

planner 问全国书友会名字、加入年份、逃离忙碌生活的动机、参加后的影响、俱乐部读过哪些书。没有完整 romance 偏好历史需求。

EB 仅保留 m13 与 m68：前者用户说 `romance novels just weren't engaging for me`，后者是近期创建 romance 读书会、感到安慰。m26 从怀疑到被一部爱情小说打动、m05 参与爱情写作工坊都已经召回，但被判“不属于 national book club”。其中 m26 真实理由：

> ... discusses reading a popular romance novel recommended by a friend, not joining a national book club ... Irrelevant to all requirements.

所以“信息范围被缩窄”是事实。但当前 gold b 说“Initially, you enjoyed reading romance novels”，EB 选择 a 说“Initially disliked, eventually grew fond”。完整 visible history 中与 romance 相关的用户段落，除了 m05 的写作活动外，明确阅读历史依次是 m13 不感兴趣、m26 initially skeptical 后喜欢、m68 最近读书会。m26 甚至说 `a whole new genre I had previously overlooked`。并没有发现明确的“最初就喜欢阅读爱情小说”原文。

**结论：此题不能包装成“dense 保留了明确正确历史，所以答对”。** EB 的需求/映射范围偏窄，但 dense 的 gold 命中是否代表更正确的证据理解仍有疑问。应该单列时段/标注一致性复核；不要改 gold、不要以当前模型输出作为数据更正依据。

## 对方法解释的含义

1. “改了很多次”主要修的是接口可靠性、引用、预算和搜索调度；这些改动没有校准 query-only planner 对 PersonaMem 个性化续答任务的理解，也没有使 mapper 的否定判断可靠。
2. 在这四个清晰案例里，EB 已经有 dense 的关键历史却主动失去它。算法多做的中间判断具有单向丢证据能力；此时增加检索次数/预算收益很低。
3. dense 的最终 reader 输入在这些题上确实更长、更多条，但仍未用满相同 8192 上限。不能从 reader 单次输入长度推导 dense 总成本更高；EB 还有 planner、成批 mapper、选择/修复、搜索的额外成本，成本对照由独立审计表给出。
4. `normal` 应被理解为“协议处理正常”，不能理解为“语义证据充分”。需要另外监测 zero mapping、empty context、必要需求缺失、映射拒绝 dense 关键历史等行为。
5. 可优先设计受控消融：同一初始候选，保持 dense 作为可用底座，分别接入 planner/map/select，看哪个门控降低 key-history retention。对 planner 强调个性化依据/历史变化，对 map 的无关判断允许原文复核；不要先加更复杂搜索，也不要在当前运行上改变规则。
6. 干预验证应保持模型/提示/选项与请求口径一致，预先确定配对重复。当前五对请求不同，观察到的信息丢失提供了强机制线索，但不能排除 reader 波动或其它同时变化的上下文因素。
