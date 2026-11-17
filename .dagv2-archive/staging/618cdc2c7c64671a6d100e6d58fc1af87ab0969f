# R18 frontier / exposure 只读结构审查准备

状态：**PREPARED，尚未对 R18 执行。** 本文不是运行通过回执。

仅补充新 `discovery_frontier`、`discovery_contexts`、`discovery_promotions`、
`source_exposures` 的结构审查。R17 的 mandatory actual-scope 检查逻辑可以复用；
不重写评分器、运行器或通用验证框架。生产正在修正 alias 恢复与异常同步回归，
实际执行前必须记录主代理给出的最终冻结 commit/hash，不能使用早期 freeze 当作通过依据。

## 0. 执行边界与输入清单

- 只有主代理确认新运行目录后，读取该目录 `manifest.json`、`progress.json`、
  PersonaMem residual arm 的 canonical `rows/*.json`、对应 authoritative attempt 的
  `result.json`、`fusion_events.jsonl` 和 `requests/*.json`。必要时读取该 attempt 已保存
  的 observation-boundary checkpoint。先核 canonical row 的 unit ID/arm/attempt；
  历史 attempt 只提供历史记录，不重复算为新结果。
- 允许为 source 身份核验读取**公共原始记忆**与其 speaker/time/offset 元数据，或调用
  最终冻结版本的纯 `build_source_spans`。禁止读取 `evaluation_only.json`、任何 gold/label
  文件或评分汇总；禁止执行评分、模型、tokenizer/embedding/LLM 服务。
- 请求正文、原始记忆、模型输出仅在本地内存中核对。报告只写题序、run/attempt 标识、
  source/query 哈希、计数、布尔和固定错误类别；不写题目、选项、答案、记忆原文或自由文本错误。
- 不修改 run、repo、rows、requests 或 checkpoint。输出仅写外部 validation 目录。
  live run 只报告当前 canonical rows 的截面，不写“最终通过”；缺文件/半行记 `not_yet_observed`
  或 `unavailable`，不能当作零问题。未启动时不生成实测计数。

## 1. 固定身份与正确统计口径

1. 记录最终 release commit、两个生产文件 SHA-256、manifest 中 source hashes/config identity，
   对照主代理冻结回执。确认 R18 是新目录/新 manifest；不能继续写 R17。
2. 按 manifest 题序统计 residual 当前行状态。planner 在 reader 创建前失败的行，新增字段
   可能整体缺失：单列 `reader_not_reached`；不得伪造空 frontier/exposure，也不算检查通过。
3. 成功行必须具备完整 reader/fact/terminal/audit 诊断。字段缺失是结构检查失败，不能按
   `dict.get(..., [])` 当作没有义务。

主要入口：`row.diagnostics.joint_reading`（下称 J），
`row.diagnostics.fact_state`（F），`row.diagnostics.terminal_input`（T）。

## 2. Source 身份可追溯

检查 J 的 frontier `item.source`、exposure `sources[]`、promotion `origin.source`，
以及 exposure 中保留的 `discovery_origin.source`。

1. 每项具有 source alias、稳定 `source_id`、`doc_id`、64 位内容身份；同一 row 中这些引用
   可以追溯到 candidate documents。相同稳定 source ID 的 doc/content 身份必须一致。
2. **alias 不是跨快照主键。** 跨恢复、跨导出比较使用稳定 `source_id` 和完整内容身份；
   在单个实际请求内，alias 必须唯一解析到该 source。合法 alias 重编号不得判内容变化，
   也不得只凭旧 alias 相等判断同一原文。记录 alias 变更计数，不能覆盖历史 owner/version。
3. 全量内容身份须按最终冻结 `_source_identity` 的**实际公式**重算。原 mapper span 来自
   候选文档的 `build_source_spans(doc_id, document, min(400, max_quote_chars))`，再绑定
   稳定 `source_id`；纳入 text、offset、role、message indices、time、premise groups、
   原文 hash、邻接等原始字段，排除最终实现定义的临时 alias 字段。只记录匹配计数/失败哈希。
   若缺少重建所需公共文档，记 `content_identity_recomputation=unavailable`，不能称全验。
4. 将每条 exposure 的 `(operation, logical_call_index)` 对应到同 authoritative attempt 的
   archived request。按已有 codec 解开 `source_span_columns`、`source_documents` 等可逆
   表示；比较完整请求 source 集合、doc/offset/role/time（不是仅 batch 主 aliases）。
   必须覆盖邻接、父证据和 failed-review/repair 原文。
5. `request_status=not_sent` 是 preflight 前后已保守登记的工作，不要求物理请求文件存在。
   `attempted` / `failed` / `returned` 不能直接换算成实际 HTTP 成功数；物理成本仍看 ledger。
   缺 archived wire 的已记录逻辑请求标 `request_trace_unavailable`，另行核对，不当作空输入。

## 3. 同 query 分离与跨 query 历史

对同 query identity，以当前 alias→稳定 source 映射构建以下集合：

- U：frontier 中 `status=unoffered` 且 `provenance=explicit_discovery` 的 source；
- E：所有 source exposures 的 source，包括 failed/not_sent/attempted；
- R：`read_states` 中已出现的 source（read/invalid/irrelevant 都算）；
- H：`unread_obligations` 的 owner/source 工作。

必须满足 **U∩E=U∩R=U∩H=∅**。不能通过未 citation、无 observations、请求失败或换日志名
将实际曝光 source 放回 U。`discovery_contexts` 对同 identity 唯一，frontier 的 task、变量、
scope、program identity/revision、parent versions 与其 context 一致；旧 context 可历史保留，
不要求它等于当前最新父版本。

跨 query 的同一原文可以同时存在“旧范围未发送”与“新范围已读”，这**不是自动冲突**。
应分别记录 owner、scope、版本及 status，不能按 source 全局去重清除旧工作。若有前后
checkpoint，逐个核对旧 hard 工作：保留，或有真实 offered ID 的解决记录，或合法版本/依赖
变化使它不再参与当前证明；仅 query 改名、frontier 暂停、enqueue/dequeue 不能是清除理由。

同 owner 的 frontier 消失应可追踪到 exposure 的 `discovery_origin` 或 promotion 的 `origin`。
只有最终 row 而无较早 checkpoint 时，报告 `historical_retention=partially_observable`：
可核对保留记录内部一致，不能凭终态证明全部过去工作未曾被删除。

## 4. 复用 actual mandatory 审查

复用 `review_r17_closure.py` 中 archived request 的解码、required-source 收集与实际
`joint_read_completed` 分组逻辑；复用时改为 R18 明确目录和外部输出，不直接执行写死 R17
输出路径的旧脚本。

1. 初始 `semantic_compose`、`audit_joint` 以及 task.execution=compose 的 `joint_read`
   才属于本处 mandatory initial 请求。`*_repair` 另外计数，它是同批修复，不是新的成功前缀。
2. required 集合包含本次选择证明的完整递归共同前提、相关 counter、supported parents/
   task outputs、evidence obligations、failed-review originals 与授权 clues。
   同值的非选中 OR 路径可以归档；summary revision 累积来源不能误当独立 OR 删掉。
3. 每个实际 initial request 必须 `required ⊆ visible`。额外 visible 需核对是否合法 clue/
   保护材料，单列 `requires_review`，不能只因 extra>0 自动判错或忽略。
4. 同 `(operation, query identity)` 检查 initial request、completed batch 数及 source set。
   mandatory 主 batch 必须等于完整可见原文范围，不能只读成功前缀。多个 initial batches
   必须逐个核查；协议 repair 不重复计数，合法 audit correction 应有新身份/真实版本依据。
5. 确认 exposure 对上述实际请求完整覆盖；ordinary frontier 的提前返回不能改变 mandatory
   initial source 集合、把共用前提拆成多个片段，或豁免失败修复里的必要材料。

## 5. 成功行的 hard 义务与 terminal / audit freshness

对 `answer.status=ok`：

1. 不读取 prediction/semantic_answer 的文本用于报告，不做 parse-choice 评分。PersonaMem
   应沿实际方法契约具有 `completion_kind=semantic_assessment`、无伪造 symbolic certificate、
   `diagnostics.audit_complete=true`、T.validation_complete=true。
2. 从 T.binding_dependencies 得到实际终端依赖 D，核各变量当前 version 一致、绑定 identity
   与 F.facts 的 digest 一致。只输出匹配布尔/计数。必要时跟随当前选中 route 的真实
   parent_versions/source_ids 递归核闭包，不能用所有规划节点代替实际依赖。
3. D 与 F.pending_variables、J.unread_obligations、failed_obligations、
   evidence_obligations 及未解决 failed reviews 的实际变量交集必须为空。
   合法消去且不在 D 中的 sibling 可保留 pending，不能要求全局所有义务为空。
4. T.logical_call_index/response_ref 对应真实 terminal generation 或 terminal-only repair；
   terminal 不能仅由 history summary 冒充。其曝光与源范围可追溯。
5. 定位之后实际执行且最终通过的 audit：显式 verdict=supported、required slots 完成、
   无影响 D 的未决或失败，并核当时实际父/绑定版本与当前发布版本一致。audit correction
   后必须是修正后的 terminal/audit；不能用旧成功 audit 或简单“见过 audit 请求”当作 fresh。
6. 若 public row 不含证明 freshness 所需 identity，应读取同 attempt 的最终 checkpoint/
   archived wire/events，或使用最终冻结纯状态验证器做只读核对。证据仍不足则记
   `freshness=unavailable`，不能仅凭 `audit_complete=true` 宣布全通过。

失败行保留其 source/owner/失败原因类别及成本，只核结构，不要求它没有 hard 工作。
frontier 数量不等于漏读率，`ok` 不等于答对，完整 audit 也不证明语义上没漏反证。

## 6. 输出回执与关闭标准

使用旁边 `r18_frontier_structural_review_receipt.template.json`，填入实际运行后才把
`review_state` 从 `prepared_not_run` 改为 `live_observation` 或 `closed_run_review`。
所有未核字段保持 null/明确 unavailable，不填 0 或 true。分三类列出：

- `confirmed_failures`：可定位到某题/请求身份的实际不变量违背；
- `requires_review`：来源不足、extra clue、同身份多 initial、历史无法完整观察等；
- `checks_passed`：有实际 row/request/source 证据支撑的结构检查计数。

只有 writer 已停止、计划 canonical rows 全部存在、冻结/manifest 一致、所有检查具备证据
且无未处理失败/疑点，才可写本结构审查完成。它依然不代替严格 smoke 全成功门槛，不授权
启动全量，不代表准确率或论文结论。

本准备工作只读取过 R17 的结构 schema 和既有检查脚本；未读取 evaluation_only、未评分、
未输出原文/答案，未运行 R18，未修改 repo 或调用服务。
