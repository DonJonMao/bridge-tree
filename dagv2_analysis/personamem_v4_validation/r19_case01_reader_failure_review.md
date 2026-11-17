# R19 第 1 题：Reader 失败与最终阻塞的独立审查

结论：本题自然发布 `unresolved_or_exhausted`，不是新 handoff advisory 的拒绝，也不是总 LLM/ANN 配额耗尽。明确链条为：**旧未决义务需要复核 50 个来源，但后续草稿仅复核 8 个；两次有界修复又同时引用并重述明确冻结的同一行；留下 75-source 失败/未读责任；继续原查询的最小新窗口真实超限；最终 response 因不能越权处理另一查询的硬未读而没有执行。**

call 7/8 的直接重述错误是模型违反了同一作用域内一致的提示、实际 schema 和本地规则。未发现“提示要求重述、schema 允许且守卫错误拒绝”的矛盾。但不能把整个失败仅归因为重述：即使去掉重复行，尚有 42-source 复核覆盖缺口；真实容量与 owner 限制也是最终停滞的独立条件。

对象：RELEASE `0cc2cc78498bcd215252fb8e82d2168868a71b3f`，`outputs/v4_validation_r19`，固定序列第 1 题 `acd74206-37dc-4756-94a8-b99a395d9a21`。仅检查 canonical 行、其当前 attempt 的请求/响应结构、事件及对应源码；离线校验实际发送的 JSON schema。没有标签/评分、模型或 tokenizer 调用，没有修改源码、运行或结果。报告仅包含结构与哈希。

## 实际规划及前置状态

规划有四个无父 retrieval：`attended_events`、`music_preferences`、`cultural_interests`、`constraints`；response compose 明确依赖四者，输出契约是 semantic。四个历史变量均声明 `personal_history_summary`。没有将某个历史单变量的符号证书当最终答案。

call 2/3/4 分别读取前三个历史任务，均看到 50 个来源并返回合法 support，无 unresolved。它们与后续 constraints 使用同一来源命名空间，但任务、变量和 query identity 分开。最终四个历史值都仍绑定，只有 constraints 保持 pending；“已经有值”不等于旧证据问题已解决。

## 每次相关草稿、冻结授权及 schema

| 调用 | 实际输入与模型返回 | 审查结论 |
| --- | --- | --- |
| joint_read/5 | constraints；50-source window；support `obs1` 引用 8 个来源；同时保留 1 条 unresolved，未声明解除旧问题。 | 草稿结构合法，batch complete 不代表语义问题已消除。该未决项按现有规则绑定全部实际 visible 50-source window，生成 `obligation_49c18d3c0aea66f6fe403642`。 |
| joint_read/6 | constraints；75-source window；提供上述 50-source obligation。返回 support `fact_35c95e7e2fc071757f283aaa`，仍仅 8 个引用；unresolved 为空，并声明解除该 obligation。 | 实际 schema 合法，但有源复核仅覆盖 8/50，缺 42；本地解除守卫拒绝，形成 `id="*"` 的槽级修复。support 自身已通过验证，冻结于当前付费批次。 |
| joint_read_repair/7 | wildcard failed slot；明确 `frozen_observation_reviews.slot_observation_ids=[fact_35c95e7e2fc071757f283aaa]`。原完整行就在 failed slot 中；offer 的完整 observations 列表为空。模型填写该 reviewed ID，同时在 observations 原样提交同 ID，再次声明解除原义务。 | 同时引用和重述被提示明确禁止；实际 schema 的 observations.id 有 `not/enum` 禁止同一 offered ID；离线 schema 校验失败，本地冻结守卫也拒绝。仍缺 42-source 覆盖。 |
| joint_read_repair/8 | 冻结重述反馈；仍明确提供完全相同的 frozen ID，作用域仍是 constraints。同样返回引用加原样重述，继续声明解除原义务。 | 实际 schema 再次失败，本地守卫再次拒绝；达到每请求两次修复上限，该 paid batch incomplete。 |

call 6/7/8 中该 observation 的完整规范 JSON hash 完全相同：`b18c0ad8ba94822c7e1aa13bf694a13cc4cab0da3833c8e768eca2bf8210e1f0`。并非模型在修复中提供了新的覆盖行或新的充分证明。三次的所引 8-source 集合均是原 50-source obligation 的子集，缺失集合完全相同。

所有七次实际 Reader 请求中，返回 support 的实体/时间 scope 与该请求 requested scope 完全匹配。本次失败不是 scope 字符串错误、跨变量 frozen ID 授权，或误把另一子任务行当成当前草稿。call 7/8 的 offer 都是当前 batch 的 constraints 行；failed entry 的 variable、failed slot variable、requested_slots 以及 schema branch 都指向 constraints。

## 提示、实际 schema 与本地守卫是否矛盾

三者对 call 7/8 的冻结行为一致：

- 实际提示包含 “Already validated observations are frozen and must not be restated or changed.”，以及显式引用说明 “Do not restate or edit a frozen observation.”。
- 摘要幂等复核提示已明确区分历史已整合 route 与当前付费批次的冻结行，说明 wildcard failure 不解冻后者。不能从旧 summary 的复核权限推导本次可以重述 frozen observation。
- 实际 schema 的当前变量分支允许该 ID 出现在 `reviewed_observation_ids`，同时以 `observations.items.properties.id.not.enum` 禁止它作为普通 observation 返回。实际草稿两次都违反此约束。
- `joint_reading.py:1901` 起检查引用是否明确 offered、当前批仍有效及是否同时重述；`:2517` 与 `:2548` 的普通 frozen-row 检查也拒绝重述。`:2736` 起按当前冻结重述原因重新提供该范围的引用，与保存请求一致。
- call 6 的覆盖失败不完全由 schema 表达：提示和 `:1973` 起的 obligation guard 要求逐来源的已完成复核覆盖整个 50-source 集合；schema 合法并不证明语义复核充分。此处是刻意保留的语义/来源校验，而非 schema 授权忽略旧来源。

协议并未要求重复提交这个已冻结行。可保守保留未解决问题而撤回不成立的解除声明；若要真正解除，则需在引用已提供的 8-source 有效行之外，对其余 42 个来源给出真实的独立复核，且没有 unresolved。前者不等于完成任务，后者也不能由代码自动分类或补引用。本报告不声称模型一定能在预算内完成这项语义判断。

此外这是 plain 模式的提示 schema，保存 payload 没有服务端强制 schema 解码保证。离线 schema 拒绝证明模型返回未遵守实际 schema，不能表述为绕过已经启用的 constrained decoding。

## 从失败批次到最终停止

event 358 保存：当前 constraints batch `valid_rows=1`、`complete=false`，失败是 wildcard 冻结重述。已有合法 support 没有被删去。随后保留：

- constraints 的旧 evidence obligation：50 个来源、1 项未决描述；
- `failed_batch_5e3f53d07ed054b0fd2941b4`：75 个来源、冻结有效行和 wildcard 失败草稿；
- constraints query `126f244edfaa76f76bd28e89f85b58026df8cd3055726a43229efa605073e99e` 的 hard unread：75 个来源；
- 当前 constraints 有效 route：8 个来源，值仍绑定但 pending。

这些是重叠的保留集合，不能相加成 200 个原文来源。50-source issue 是 75-source 失败范围的子集；当前义务、失败草稿和实际曝光属于同一 constraints 任务，没有发现错误转嫁给无关 owner 的证据。offer 采用 slot ID 引用而非再次复制完整 observation，也没有发现本次 frozen offer 本身不必要复制整行。

后续存在 48 个尚未处理的邻接 prefix 组；**48 不是最终 hard unread 的数量**。control 的独立范围重建核对最小 prefix1 是 75 个保留来源加 2 个新来源，共 77。保存的 events 369/370 计数分别为 12303/12391，本审查独立核对了这两个 exact count 及请求哈希；没有再次调用 tokenizer。

按既定修复预留：`12391 + 4096 + 256 + 8 = 16751 > 16384`，超 367。event 455 因此记录 constraints 的真实局部输入超限。实际 call 7/8 输入分别为 11229/10911，其生成请求本身都适配；所有响应 finish_reason=stop，call 6 的初次 output cap=651 也没有导致截断。不能把先前 schema/冻结错误解释为那些 HTTP 生成请求的容量失败。

event 456 中，response 随后被 `mandatory_closure cannot settle relevant unread work owned by another query` 拒绝。它没有发送真实 compose 或 audit，也不能替 constraints 原查询清掉失败和未读责任。本题全部 handoff capacity_rejected 和 handoff_deferred 事件计数均为 0。

最终 LLM 8/24、ANN 4/36、JSON repair 2/6，仍剩 16、32、4；终端和审计调用均为 0。因此既不能只说“预算耗尽”，也不能断言允许更多调用就能解决这次容量和义务阻塞。

## 已确认与尚未证明

已确认：两次 repair 的模型重述违反同一 scope 的提示、schema 与 local guard；初始解除声明另外缺 42-source 覆盖；失败原文和未决状态保留后，真实后续读入容量及 owner guard 阻止结束。没有发现本例 handoff advisory 放宽、当前批 frozen 授权或 source scope 的实现矛盾。

尚未证明：所有 50/75 段在语义上都是最终回应的最小必要前提；planner 增加的全部 constraints 字段都不可省；删掉重复行即可成功；改提示、改序列化、提高额度或某种重规划一定能通过。完整来源窗口成为义务是当前保守规则，不等于每段都是支持答案的独立前提。后续设计判断应与本次保存轨迹及原样失败分开。

## 精确证据

完整结构与文件 hashes 见 `r19_case01_reader_failure_review.json`，由 `review_r19_case01.py` 只读生成。

| 调用 | 请求文件名主体 | 文件 SHA256 |
| --- | --- | --- |
| 5 | `ae214e42349c93fc8fae7b11d28ea67d6dd27f65e278a52c7530a80cee8ed9ef` | `807f0e3529e1bad4589351247680e8e368a9c69d9b9b8a6f8cc267651f999f69` |
| 6 | `f4b8eb87652bd53912441a31ffd8d579aaecc7d2f285d6ca6430de4a676d5489` | `a59bd8d580b2cfec7572d670eb31c90e95fed0ae2497a7b9e8ec0da166fbd43d` |
| 7 | `0d95e2590595d8e7135bb1a8b0c7f47b28480e47b1d663050d80e2b33112ee85` | `1ceb540e6eb9f64d0c750b3198a595afaccfe283f0eb41d612b5fcc92defe03e` |
| 8 | `576c15a0dbeaf8dc97ff832246cba0f432c8ab5e84f0c293f5ee492148338206` | `d29e2e29e6ebe4a05675de58e30acfc5800e3323fca94b09e1b6e0b096772e61` |

本报告不更改本题状态，也不依据本题提前停止固定 14 题运行。
