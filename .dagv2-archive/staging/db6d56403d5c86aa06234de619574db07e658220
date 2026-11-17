# R20 第 1 题：未决项语义与原文责任范围

冻结源码 `6c046374008ce2e45f817d6bc9876b3ab927ab18`；unit `acd74206-37dc-4756-94a8-b99a395d9a21`。只读已经自然结束的本题 canonical row、实际 Reader 请求、当前协议和设计文档。未读取标签或评分，未调用服务/tokenizer，未改源码、测试、运行、证据范围或状态。下文不导出原题、记忆、摘要或答案原文。

**本题发现了一个具体的 Reader 语义偏离：首次 `unresolved` 表述的是已读材料的范围和其余材料的类别，没有指出建立当前历史摘要仍缺少的具体条件。这与本次实际提示中的既有指导不一致。尚未发现义务保留与解除守卫违反当前协议；不能因此自动清除该条目或认定全部失败已经解释完毕。**

## 1. 与 R18 / R19 不同的实际起点

本次计划只有 `attended_events`、`music_preferences`、`cultural_interests` 三个独立历史 retrieval，以及依赖三者的 `response`。三个历史变量均为开放的 `personal_history_summary`。R19 的 `constraints` 变量本次不存在，因此不能沿用 R19 的“缺少限制条件”归因。

Call 2 的局部任务询问相关已参加活动，未要求列出全部历史活动。返回一条 3-source support，同时在 `unresolved` 写入一条说明：已读资料未提及其他已参加活动，其余资料属于其他经历类别。该说明本身没有指出一个尚未获得、且仍为建立当前历史值所必需的条件；它也没有提出有待消解的矛盾。

已独立检查实际保存请求的 system message，确有当前 `personal_task.py:87–88` 指令：

> Use unresolved only for a specific condition still necessary to establish this requested historical value, not hypothetical exhaustive coverage.

这与 R18 case 13 有局部子问题明确要求的能力等级/限制字段、R19 case 1 的 `constraints` 缺口不同。这里可确认的是“范围说明被放进硬未决字段”的具体迹象，而不是 planner 所选某个实体/条件确实缺失。不能仅凭该观察进一步断言原摘要语义充分、最终答案可确定或整题本来应当成功。

## 2. 三类责任不能混为一谈

| 类别 | 本题实际状态 | 能证明什么 / 不能证明什么 |
| --- | --- | --- |
| 查询语义缺口 | Call 2 的单条范围说明进入 `unresolved` | 证明 Reader 宣告了未决状态；该文本未标识必要缺失条件，不证明存在 50 个必要事实。 |
| 已曝光原文义务 | 一项 `attended_events` evidence obligation，50 个来源 | 这 50 个来源精确等于 Call 2 整个可见窗口。由于字段没有逐项来源映射，当前代码保守保留全部原文；不代表每段都是支持答案的前提。 |
| 失败草稿责任 | `attended_events` failed batch 80 个来源；`cultural_interests` failed batch 104 个来源 | 这些是各次失败阅读实际曝光后的可追溯恢复范围，保留草稿、相关反证及原文。不是新增的 80/104 个语义缺口，也不能当作新的已支持事实。 |

精确集合关系：50-source issue 是 attended 80-source failed 范围的子集；attended 80-source 范围等于 Call 6 完整曝光，也等于最终 hard unread 的 80 个来源。文化 failed 104-source 范围等于 Call 11 完整曝光。两个 failed 集合交集 75、并集 109，不能直接将 50、80、104 相加。

## 3. 当前保守规则如何形成阻塞

`joint_reading.py:1953` 起的 `_update_evidence_obligations` 明确规定：非空 `slot.unresolved` 绑定全部实际可见原文，因为该字段没有逐项引文映射。解除需要 offered ID、原文可见、没有未决/partial，且真实 settled reviews 覆盖原义务全部来源。程序不将新 support 自动解释为旧问题已消失，也不替模型把其余原文标为无关。

本题 Call 3 请求解除 50-source issue，但其 support 只复核 3 个来源，少 47。Call 4/5 又出现冻结行同时引用与重述；这些独立的协议事实见 Reader 报告。即使仅修正冻结重述，50-source 覆盖责任也不会自动消失。最终保留 80-source 失败曝光和 hard unread，有已发生的阅读/草稿责任依据。

`_store_failed_reviews`（约 1802 行）保留原始和当前失败请求的可见来源并集；`_payload`（约 763 行）将与当前变量/父依赖相关的义务与失败原文带入后续 scope。它没有宣称每个来源都是答案的语义前提。`_mandatory_scope_payload`（约 2208 行）禁止另一个 query 的 compose 直接清掉原 owner 的相关 unread，因此“最终任务能看到这些原文”不等于有权替历史任务解除责任。

独立集合检查还确认：Call 7 音乐偏好 support 的 19 个引用、Call 8–11 文化兴趣 support 的 17/7/6/6 个引用，全部都已位于 attended 的保留 80-source 范围内。文化任务四次下游容量拒绝都报告 80 个来源。因此减少该文化草稿引用数量，没有减少已保留的那 80-source 整体来源集合。这里只确认集合关系，不据此声称已独立重建所有 handoff payload/token，也不把后续容量拒绝全归咎于这条初始未决项。

## 4. 与理论设计的关系及结论边界

设计文档第 4.2 节把活跃需求限定为仍可能影响输出或其必要来源核验的需求，第 6.2 节要求保留必要旧原文、冻结合法记录并明确未读范围，第 7.3 节不要求所有检索原文与所有节点全映射。当前协议针对已宣告未决、已曝光而失败的局部阅读保守保留出处，与“不无依据地丢失反证或责任”一致；它没有要求全库穷尽或全节点交叉映射。

这里暴露的具体边界是：当前自由文本 `unresolved` 无法结构化区分“仍有必要条件缺失”和“对已读证据范围的说明”，而本次 Reader 没有遵守已有的语义区分指导。非空字段一旦进入状态，就合法地产生较宽的恢复责任。**这是本题可定位的输出契约执行问题与表示粒度限制，尚不能称为一个新发现的 guard 实现/理论矛盾。**

任何后续改进都需保持真实语义复核、原文责任、反证和失败记录；本审查不建议自动删项、自动归为 irrelevant、缩小来源集合、放宽 owner/冻结/覆盖规则或修改本题结果。即便修复了初始表述，也没有本题轨迹证明一定能完成 terminal/audit，更不能据本题推断准确率提升。

证据索引：`r20_case01_obligation_scope_review.json`，SHA-256 `f61825281f7f90189d2c9f6bce2e5b31947f96428274d1a95ea21070a3f445be`。其中保存源码/请求/row hashes、实际指导存在性、集合等式与各次引用结构；Reader 协议细节另见 `r20_case01_reader_failure_review.md`。
