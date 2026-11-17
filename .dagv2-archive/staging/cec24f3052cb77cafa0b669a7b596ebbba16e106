# Compose / audit 来源范围只读设计审查

审查对象：`/Users/mao/projects/dagv2-personamem-v4`，提交 `50d1ba0b2edb623384e51ac42ea12b36e5b69229`。本报告只读代码、设计、测试与已归档离线分析；未修改生产代码或测试，未运行测试，未调用服务，未读取评价标签，未改变运行或提交。

## 结论

当前 compose 与 audit 都把“需要复现的证据 span”提升为“包含这些 span 的文档”，再把这些文档内**所有已映射 span**作为当前调用身份的阅读工作。该扩张是真实代码行为；目前找到的设计要求是结合受支持父结论、必要原文、相关反证及既有未完成事项，**未找到必须重读证据所在文档全部已映射 span 的要求**。因此，这是一项超出已明确局部来源范围的额外选择策略，值得作为实现与设计的偏差修正；不是来源校验和反证保留本身有误。

将“检索候选文档阅读”和“合成/审计时复现已有证据”分成明确入口，在概念上合理。后者必须真实调用模型，完整携带既有受保护来源闭包，保留相关既有 unread/evidence/failed 事项，不能通过空参数早退、删除义务或忽略反证使运行成功。这个结论不证明调整后必然答对，也不能解释旧版全部准确率差距。

## 1. 已确认的数据流

### Compose

- [residual_control.py:652](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:652)：从有效父事实取 `source_ids`，在 654 行变成去重 `parent_docs`，丢失 span 级选择范围。
- [residual_control.py:668](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:668)：无论 retrieval/compose，先将 `local_pools[nid] + parent_docs` 交给 `read_progress`。
- [residual_control.py:534](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:534)：`read_progress` 处理输入/效果去重，552 行仍原样传递文档列表，没有区分“新候选”和“证据复现”。
- [joint_reading.py:1842](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1842)：选择这些文档的全部已映射 alias；非审计仅排除当前 `(identity, alias)` 已读项。历史阶段读过不等于当前新身份已读。
- [joint_reading.py:1857](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1857)：为所选 alias 注册当前身份的 unread；1861–1864 行还为窗口加入相邻 span。后续容量失败会保留 pending 并报错（1868–1874）。

这里不是“整个语料库”或“文档每个字节”被重读，而是**给定文档里当前已映射的全部 span**。未被父 proof 选中的额外 span 不等于已经证明无关，不能因此把它标为 irrelevant。

### Audit

- [residual_control.py:425](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:425)：先由证书或实际语义依赖确定审计变量及来源。
- [residual_control.py:455](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:455)：证书/依赖来源变成文档 ID；456–465 行还加入相关 route 及 revoked/counter 来源所在文档。
- [residual_control.py:466](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:466)：`reader.read(... audit=True)` 再读这些文档；reader 1843 行的 `audit or ...` 直接绕过已读过滤。
- [residual_control.py:469](/Users/mao/projects/dagv2-personamem-v4/dagbt/residual_control.py:469)：当前审计身份所有实际 batch 均需 `audit_complete`。审计不能在后续窗口未通过时仅采用前一窗的 supported。

这与“核验当前回答所用支持及全部已知相关反证”不同。后者必须保留，但不自然推出重读这些来源所在文档的所有其它 span。

## 2. 与设计的对应

- [DAGBT_LOCAL_TERMINAL_V1.md:13](/Users/mao/projects/dagv2-personamem-v4/docs/DAGBT_LOCAL_TERMINAL_V1.md:13)：合成“直接结合受支持父结论和必要来源求解”，父证据齐备不重新检索 Q；缺口由相关父任务补查或有限细化解决。
- [RESIDUAL_MEMORY_DESIGN_f4e38df.md:204](/Users/mao/projects/dagv2-personamem-v4/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:204)：局部联合阅读，不对所有原文与所有节点做全量交叉映射。
- [RESIDUAL_MEMORY_DESIGN_f4e38df.md:216](/Users/mao/projects/dagv2-personamem-v4/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:216)：输入为当前需求、必要父结论及来源、当前待判原文、相关已知反证；不无条件重传全部历史；容量包含修复预留。
- [RESIDUAL_MEMORY_DESIGN_f4e38df.md:240](/Users/mao/projects/dagv2-personamem-v4/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:240)：审计针对当前输出采用的支持与已知相关反证，不要求所有已检索原文完成对所有节点的映射。
- [README_PERSONAMEM_V4.md:83](/Users/mao/projects/dagv2-personamem-v4/README_PERSONAMEM_V4.md:83) 与 [README_PERSONAMEM_V4.md:94](/Users/mao/projects/dagv2-personamem-v4/README_PERSONAMEM_V4.md:94)：完整原文、反证、真实容量与已有未读/失败义务必须保留。结合前述设计，“完整原文”应理解为必要来源及义务涉及的完整权威 span，不能据此自动推导“同文档其它全部 span 也必读”。这是设计解释，不是已实现的新接口。

## 3. 现有 `_payload` 已维护什么，尚不能替代什么

[joint_reading.py:463](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:463) 的 `_payload` 已会复现：

1. 受支持父结论及其递归实际父依赖、版本、scope、来源。
2. 请求变量的全部已知 routes，以及嵌套来源、祖先和 counter 关系。
3. 相关 `evidence_obligations`、`failed_batch_reviews` 及这些事项要求的完整来源。
4. 父任务输出证书、当前身份 clues 和本窗明确新增的 alias。

485–500 行递归收集来源并拒绝缺失 source identity；521–523 行提供原文及权威坐标、角色、消息/时间字段。故不能把“去掉自动文档扩张”表述为“只送摘要”，也不能缩成一条最小支持 route 而删去相关反证。

**重要限制：** `_payload` 不直接枚举 `unread_obligations`，并且只加入当前 identity 的 clues。旧 unread 仍由 `pending_variables()` 使状态未完成，但不保证 `aliases=[]` 会把它们放入本次复核或正确结清。因此不能声称空 aliases 自动保持并处理所有工作；必须显式保留这些事项的身份、来源和完成语义。

**Audit 当前闭包较广：** controller 在 466–467 行把审计 step 的 `inputs` 设为全部非终端任务，`_payload` 466–477 行因此还会包含这些输入中所有有效父值及其真实父闭包，不只证书最小来源。当前 audit 的全部非终端 `step.inputs` 契约不在所讨论修订的缩减范围。即使调整文档选择策略，也不能未经另行审查就改成只保留证书 source IDs。审计变量的其它真实路线及反证更不能因不属于单条 selected proof 被排除。

## 4. 完整闭包复核与“把源 ID 再当候选”的区别

建议的概念边界是：**bound-evidence 模式对完整 mandatory closure 进行真实复核；retrieval 模式读取明确选择的候选文档；必要的额外原文与既有待办单独表达。** 此处仅为设计审查，不是实施或发布决定。

- 闭包是每次请求必须完整带入的证据底座，不能靠把闭包拆成窗口使每次只见部分必要前提/反证。
- 如果没有真正新增原文或必须继续处理的已登记待办，完整闭包应对应一次真实合成/审计操作及原有有界修复，不必再为闭包每个源创建候选组。
- 把同一批 mandatory source IDs 作为普通候选传入现有分窗器，会重新产生 unread、邻接扩张和多窗；每窗又完整重带 mandatory closure，不能解决闭包本身过大，并可能再次制造本无必要的续窗。
- 若某项额外邻接原文确有解释需要，应作为明确选择且计入容量的待判原文。不能由父 span → doc 的隐式扩张代替选择。
- 对当前实现要求完整单次复核的 evidence/failed 义务，不能把单次覆盖改成跨批默默累计。若闭包本身不容纳，仍应诚实失败；需要另行设计可验证的压缩/复核机制，而不是删源。
- 非终端 compose 在无 aliases、无可执行既有义务时会由 [joint_reading.py:1853](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1853) 直接返回。因此不能仅将 `doc_ids=[]` 替换进去；bound-evidence 模式必须显式保留真实调用和阶段契约。
- 已登记的 unread/evidence/failed 事项不能在模式切换时被抹掉，也不能因别的身份读过同文档而视为本事项完成。若 bound-evidence 模式需要处理相关既存 unread，应显式保留/报告其原文和所有权；不能借新 query 清除旧 identity 的 unread，也不能给已付费失败免费恢复。原始反证、作用域、来源、pending、发布新鲜性必须保持。

## 5. Handoff 与执行范围并不完全相同

[joint_reading.py:1754](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1754) 的 mandatory handoff 用 `probe._payload(... aliases=[])` 检查下游完整受保护来源底座。实际 `run/audit` 却额外把父来源扩成文档内所有映射 span。因此 handoff 通过不是“今后所有扩张窗口与新增状态一定可容纳”的保证。

这揭示两条路径的范围差异，不能反过来认定容量检查应放宽。尤其产生新 terminal route 后，known-observation 元数据也可能变大，即使 mandatory 原文集合不变。bound-evidence 入口应与 handoff 的真实 payload/阶段/计数对齐，同时仍按实际当前状态重新计数。

## 6. 第三题已有实例及证据边界

control_v4 的独立离线归档报告 [r15_terminal_continuation_expansion.json](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r15_terminal_continuation_expansion.json) 重建首个 terminal 请求且完整 wire hash 相同：

- selected 父证据闭包 36 个原文来源，分布在 12 个文档；文档扩张后 117 个已映射 span，额外 81 个。
- 117 个 span 在历史阶段均已读；新的 terminal identity 仍创建 117 个组。这不代表历史判断自动足够替代终端复核，而是说明复核范围由文档扩张重新决定。
- 第一 terminal 窗消耗 16 组、涉及 17 spans，后续剩 101 组；在该点仍有 100 个 unread markers。
- mandatory 来源仍为 36 个，无新增 mandatory 原文；known-observations 字节数从 7,839 增至 9,372。字节数不是 token 数。

[r15_terminal_continuation_review.json](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r15_terminal_continuation_review.json) 中 101 个续窗候选的初次/修复 wire 共 202 项均精确匹配归档；最小一组为 3 个新窗口 span、39 个可见来源，修复输入 12,095 + 输出 4,096 + 余量 264 = 16,455，超过 16,384 上限 71。

**不得扩大结论：** 零新增组的 exact wire 无已归档计数，不能断言当前 36-source 闭包单独一定能放下或一定放不下。本例直接证明自动扩张制造了额外续窗及待办，并遇到真实容量失败；尚未证明改变入口后该题会通过审计或答对，更不能把该 V4 样例直接当作 V3.1 所有失败/有效答错的根因统计。

## 7. 应保留的测试边界（本次只读，未运行或新增）

- [test_v4_reader_review.py:245](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_reader_review.py:245)：完整合法复核可释放义务，后续 proof 只保留必要来源；审查覆盖与最小 proof 不同。
- [test_v4_adaptive_initial_cap_review.py:266](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_adaptive_initial_cap_review.py:266)：后续窗口容量失败不能删除未读后缀或已接纳历史。
- [test_v4_reader_review.py:140](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_reader_review.py:140)：带来源的未解父事项阻止重用既有终端。
- [test_residual_runtime.py:523](/Users/mao/projects/dagv2-personamem-v4/tests/test_residual_runtime.py:523)：新选局部证据可以撤销真实 grounding parent，不能仅检查本节点输出而忽略父反证。
- [test_v4_control.py:107](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_control.py:107)、119、231、255：审计反证保留、纠正后重新审计、有限重试、撤销后不可发布旧答案、checkpoint 保护。
- [test_v4_joint_reading.py:39](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_joint_reading.py:39)：compose fixture 传文档，但小 fixture 不能证明父文档多余 span 全部必读。

若以后实施，应覆盖同一父文档多 span、最小支持外的真实相关反证、早已登记的 unread/失败事项、非终端 compose 确实调用、audit 全部相关路线/反证、上下游相同真实预算/来源身份、审计后实际依赖新鲜性。测试成功仍不能替代同题同预算准确率对照。

当前仅确定这些边界。按 root 决定，等待 R15 全部 14 题后再讨论实施，继续保持本轮不改源码。
