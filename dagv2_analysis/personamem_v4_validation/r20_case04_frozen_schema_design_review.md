# R20 case 04：冻结禁止集合与复核授权集合的独立设计审查

**可以把“当前批次禁止普通重述的 ID”与“本次明确允许引用的 settled ID”分开表达。这是对现有运行期规则的 schema 镜像，不需要赋予 unknown/partial 任何新引用权限，也不应改变义务解除、证据保留或事实更新规则。** 下述边界是该结论成立的条件。

本审查只读 RELEASE 的 R20 已结束 case 04 请求、Reader 报告，以及 RECONCILE 冻结源码 `dagbt/joint_reading.py`（SHA-256 `f7a01fd53130d1782766c1fbdb09cc43d7ead1ca864e77c5597272b896cb7490`）。未改 repo 文件、测试或运行，未执行测试或调用服务/tokenizer，未读取标签/评分，也未导出题目、选项或答案文本。相关 schema、frozen offer、whole-value 和 durable helper 在 RELEASE/RECONCILE 的函数内容 hashes 一致。

## 实際缺口及其边界

运行期在 `_observation` 规范化成功后，将所有合法 observation 的 `(variable, id)` 加入本批 `frozen`，不限于 support/contradiction/irrelevant。后续 repair 在两个位置拒绝普通 observations 重述任何这些键。

现有 `_schema` 却只从 `repair_scope.failed[].frozen_observation_reviews` 收集 ID，再同时生成 `reviewed_observation_ids` 的许可枚举与普通 observation ID 的禁止枚举。而 `_frozen_review_wire` 有意只允许带有效来源、scope 合法的 settled 行进入复核 offer，排除 unknown/partial，以及不满足其余复核要求的行。因此“不可重述”严格宽于“可以引用”，两者共用一个集合漏掉了运行期已冻结而不能引用的行。

本次保存请求的独立核对：Call 10/11 都没有 `response` observation ID 禁止规则，没有 reviewed ID 许可，也没有 settled frozen offer；但模型返回的是 Call 9 已合法规范化、随后被本批冻结的 unknown 行。实际提示仍明示冻结行不得重述。于是这两个返回可通过已提供 schema，却被运行期冻结 guard 拒绝。这是 schema 表达不完整，不是应当取消运行期保护的依据。

一个重要时序澄清：Call 9 是新的 semantic-compose 批次；每批局部 `frozen` 初始为空。Call 9 复用 Call 7 已存在的 known route ID，不能仅因该 ID 出现在历史状态就按当前批次冻结规则禁止。Call 9 的 unknown 被本批验证后，Call 10/11 才受本批禁止重述限制。

## 两个集合应承担不同职责

对当前修复请求中的变量 `v`，定义：

- `F_v`：当前批次、当前时点 `frozen` 中属于 `v` 的 ID。它只表达“不允许作为新的普通 observation 重述”。
- `R_v`：由现有 `_offer_frozen_reviews` 明确提供、且仍满足现有有源复核条件的 ID。它只表达“可通过 reviewed_observation_ids 引用这条完整不变的 settled 行”。必须保持 `R_v ⊆ F_v`。

建议在 controller-owned `repair_scope.frozen_observation_ids` 中按变量列出排序后的 `F_v`，schema 在该变量分支为 `observations.items.id` 设置禁止枚举；`reviewed_observation_ids` 继续只使用原 `R_v`。如果没有显式 offer，不因存在 `F_v` 就添加 reviewed ID 权限。空 `R_v` 也不能导致 `F_v` 的禁止失效。

为兼容已有只含 settled offers 的 fixtures/schema 输入，禁止枚举可以按变量取新字段与旧 offer IDs 的并集；生产数据中现有 offer 本来就保证 `R_v ⊆ F_v`，这个并集不改变有效生产范围。兼容合并只影响禁止普通重述，不能反向将新字段并入 `reviewed_observation_ids`，也不能跨变量合并。旧输入不含新字段时，保持旧 offer 的禁止效果。

新字段不代表缺失证据已经解决、不把 unknown/partial 变成 settled、不证明任何来源已完成复核。模型仍需保留或诚实报告未决问题；可以省略被冻结的普通行，不等于删除 controller 持有的原行/原文/责任。当前运行期所有守卫继续独立检查，不能让模型提交的输入字段或 schema 通过替代这些守卫。

## 必须保留的四类边界

| 边界 | 正确镜像方式 | 不能采用的替代 |
| --- | --- | --- |
| 全值复核与其他解冻 | 从 summary-revision、whole-value、handoff 等失败处理完成后的最终 `frozen` 重新构造 `F_v`。具体已退回可编辑的 support ID 不再禁止；同变量仍合法的 counter/其他行继续禁止。 | 因变量出现 whole-value review 就整体解冻；或从上一轮缓存禁止列表，误禁本轮已合法退回修改的草稿。 |
| 相同 ID 出现在不同变量 | 始终以 `(variable, id)` 为身份，在各自 schema 分支禁止；只为当前 requested/failed variables 输出必要集合。 | 全局合并裸 ID，导致另一个变量合法的新草稿被禁止。 |
| known route 与跨批次状态 | 新批次 `F` 初始为空；旧 known routes 不因历史上已验证就自动进入当前 `F`。本批规范化后才按现有流程冻结。 | 从 known_observations、state.routes 或历史 source ID 推断冻结，错误禁止 Call 9 这类合法重审。 |
| durable failed recovery | durable 记录本身不授权 frozen reference，也不自动填入新批 `F`。其 required failed IDs 仍按原规则可修复；新批验证后才冻结，接下来才禁止普通重述。 | 将 durable.validated_observations 或 failed drafts 直接导入 `F/R`，阻断已有恢复权限或凭历史记录授予复核权限。 |

`F_v` 还包括一些不能进入 `R_v` 的其他合法行，例如无来源或 scope 不满足 settled-reference 条件的 irrelevant/unknown 行。生成禁止列表不应再次施加 `_frozen_review_wire` 的引用资格筛选，否则会重现同类缺口。

## 对后续实现的约束与验证目标

这里只建议一项表示补全：在现有 repair 构建处、所有解冻处理之后，由 controller 生成禁止集合，并让 schema 使用它。不要更改 runtime 的冻结/解冻、settled offer、源覆盖、counter、owner、durable recovery、预算或 terminal 判据。该元数据要进入真实 request 的容量计算及修复 identity；不能为新增文本扩大预算、隐藏原文或跳过 overflow。

后续最小验证应分别覆盖：unknown/partial 被禁止但不能引用；已授权 settled 的引用仍可用而重述仍禁止；未授权 settled 也禁止普通重述；全值支持合法退回可编辑且 counter 仍冻结；不同变量同 ID 不串扰；新批和 durable 边界不继承旧冻结；summary/handoff 退回草稿不被错误禁止；模型即便忽略 schema，现有运行期守卫仍拒绝；元数据/完整 schema 按实际 wire 计数。此处没有新增或执行这些测试。

该补全能使 Call 10/11 的 schema 表达与现有 runtime 一致，不能据此承诺模型在 plain 模式一定遵守，也不能解除 Call 7/9 的 18/16-source 义务、解决初始语义缺口或保证本题成功。既有失败记录必须保留。

结构证据：`r20_case04_frozen_schema_design_review.json`，SHA-256 `c1004cca79323f4580ab008c6e80885a87d430921b1709d19dccd1574808f893`。
