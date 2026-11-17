# V4 阶段、修复 ID 与 frozen 契约只读审查

源码提交：`50d1ba0b2edb623384e51ac42ea12b36e5b69229`。
`joint_reading.py` SHA-256：`08200e2ee7f84579762fdd123a8535a5c46cb1b6a17689c0aa5207d986b1e662`。
`personal_task.py` SHA-256：`7af9cc43b08364ea824c23c4aa2072395720ff945fb1499f62956bd4d889a9a3`。

本轮只读源码、既有报告和结构监控。未修改生产/测试、运行测试、调用服务、读取评价标签、改变实验运行。以下区分真实执行差异、提示歧义及未确认的因果关系。

## 结论

发现两处明确契约差异：**不带显式引用的 frozen 同 ID 重述仍会被旧路径忽略校验，并能按旧冻结行计入义务覆盖**，而提示要求不得重述；以及 **audit schema 未要求 audit_verdict，但运行验证要求该字段必须存在**。前者不接纳修改后的值/新来源；后者已在第六题 audit16 的归档请求与响应中直接确认，详见第 6 节。

另外两处与第五题相关的提示可以更明确：terminal 阶段的历史父摘要同样不能用 `summary_revision`；非法新增 ID 被记成失败后，下一次已成为必须保留修复的 ID，不能简单删除。现有 schema 没有阻挡这些阶段/修复中的合法保守动作。第五题出错序列与这些边界有关，但不能仅由发生序列证明提示导致了错误，更不能据此预测准确率提升。

## 1. Terminal 父摘要的权限：校验一致，提示的阶段限制不够直白

**实际权限一致：**

- [joint_reading.py:567](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:567)：只在 `personal && phase == history_evidence && !audit` 生成 `summary_revision_contracts`。terminal/audit 不提供。
- [joint_reading.py:612](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:612)：schema 仅有该合同才允许 `summary_revision` 属性；基础 observation 的 `additionalProperties=false` 在 [257 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:257)，因此 terminal/audit 不接受这个属性。
- [joint_reading.py:2037](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2037)：运行验证只在非 audit 的 history phase 传 `allow_summary_revision=True`；[1129–1131 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1129) 明确拒绝，错误为 `authorized only during personal history reading, never terminal or audit`。

**文字层面存在较窄的歧义：**

- [joint_reading.py:1111](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1111)：只要本次 requested 变量里存在 `personal_history_summary`，就追加整段 `SUMMARY_REVISION_INSTRUCTION`，包括 terminal/audit 中请求复核的父摘要。
- [joint_reading.py:192](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:192) 说明“只有 summary_revision_contracts 授权”，这是正确限制；但 [218–219 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:218) 禁止对象写成 `Ordinary facts, terminal choices and audits`。`terminal choices` 是变量角色，`audits` 是阶段；没有同样直说“terminal 阶段请求的历史父摘要也不能修订”。模型可能误读为历史摘要在终端仍属于可修订变量。
- [personal_task.py:119](/Users/mao/projects/dagv2-personamem-v4/dagbt/personal_task.py:119) 在 FINAL RESPONSE SELECTION 指导中继续要求非终端任务保留历史观察，没有单列“可以审查/反驳父事实，但不能在本阶段进行 compatible summary replacement”的动作边界。

这不是提示明确授权、schema 又禁止的硬矛盾，因为“只有显式合同授权”仍然成立。更精确的分类是**阶段约束表达不足**，尤其混合请求终端变量和父历史变量时。

当前允许的保守动作仍可表达：无新观察且无指定待修草稿的父变量返回空观察；原有同值的真实独立支持可正常报告；真实反证引用已有同变量 route；不完整的补充材料保留有源 partial/unresolved。兼容摘要替换必须回到获授权 history 请求，不能在终端给普通 support 随意改写旧整值。报告未验证 controller 在每种预算/失败状态都能成功完成该回流。

## 2. Named-ID 新行被拒后，下一轮权限发生变化，但反馈未解释

[joint_reading.py:2032](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2032) 先保存当前草稿；2034–2035 行在没有本变量 wildcard 失败、不是已失败 ID、也不是授权 duplicate replacement ID 时拒绝新增行：`Repair invented an unrequested observation`。

该行不会被遗忘：

- 它进入 `next_failures`，在 [2161 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2161) 成为下一次的 `failures`。
- [2177–2193 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2177) 将这个新 ID、草稿和同样错误文本放进下一次 `repair_scope.failed`。
- 下一次再提交这个 ID 时，因 `key in failures` 不再触发“invented”检查；可在原 ID 上纠正 stance/value/sources 等，仍经全部正常校验。
- 如果把新 ID 删掉，则 [2076–2079 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2076) 保留 `Required failed observation still unavailable`；[2109–2113 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2109) 也保留未修复的指定失败。

**具体歧义：** `invented an unrequested observation` 容易被理解成“删除这条多余行”，但下一次协议实际要求“它现在是已指定失败草稿，保留其 ID，纠正或诚实降为有源 partial/unknown；不得丢弃潜在反证”。SYSTEM [92–100 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:92) 总体要求保留指定失败 ID，却没有解释这项身份变化。

第五题由 root 观察到的 repair17 新增 ID、repair18 遗漏该 ID，符合这条校验路径，但未独立读取模型理由，不能证明其遗漏由该措辞造成。不是需要放开 named repair 任意新增 ID，也不是应删除真实失败草稿。

Schema 的 observation ID 目前只是 string（247 行），未按 named/wildcard 权限限制，所以结构 schema 本身不阻止合法原 ID 修复，也不提前阻止未授权新增；最终授权由上述本地校验执行。没有发现 schema 使这个状态只能继续违规或必须删除原反证。

## 3. 新确认：不带 ref 的 frozen 重述仍走兼容路径

**提示：** SYSTEM [100 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:100) 与 `OBLIGATION_REVIEW_INSTRUCTION` [149–152 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:149) 均明确不得重述/修改 frozen；义务复核可通过当前显式 `reviewed_observation_ids` 引用。

**显式 ref 的当前校验正确且严格：**

- [joint_reading.py:624](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:624)、[682 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:682)：schema 只允许本次 offer 的 ID。
- [joint_reading.py:1539](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1539)：校验同批、同变量、冻结行 identity、传输完整性和可见原文；1546–1547 行直接拒绝同一个 ID 同时出现在 refs 和普通 observations。

**但没有 ref 时存在另一条路径：**

1. 同 ID 普通 row 进入当前 `slot.observations`，且 `reviewed_observation_ids` 缺省/为空。
2. ref 校验无引用可检查，不拒绝该普通重述。
3. [joint_reading.py:2030](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2030) 遇到 `key in frozen` 直接 `continue`，不会再次验证该 row 的其余字段，也不会发出“不得重述”的错误。
4. [joint_reading.py:1595](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1595) 只取普通 reported observation ID，再从此前 `valid` 中选同 ID 的旧冻结行计入本次 coverage。

因此，不含 ref 的重述甚至可以只包含合法 frozen ID 而其它字段畸形，从这条本地路径借旧 valid 行参加覆盖。标准 schema 会禁止畸形 observation，但运行代码不能仅凭对端必然执行 schema 来保证这一契约；完整但擅自修改的 frozen 行本来就能通过基本 schema，也仍走这条路径。

**风险边界：** 旧冻结行本身仍是真实已验证内容。该路径不会把重述的修改值或追加来源接纳为新事实；覆盖使用旧来源，不能靠写更多源凭空增大覆盖。这里确认的是未完全强制当前声明的引用/复核方式，而不是已经发现伪造来源进入 state。reader_v4 已独立静态确认这是未收紧的旧兼容行为。

第二题先 ref+重述被拒、后去掉 ref 只重述而保留 17/52 覆盖，与此机制相容。但即使纠正该执行差异，剩余 35 源仍须真实复核；不能把这个缺口当作第二题未覆盖来源的完整解释。

### 3.1 若以后统一执行契约，必须保留的显式例外

不能按“此前出现过该 ID”一律拒绝，也不能只看失败项文本决定冻结状态。应区分**当前仍在本次 paid batch 的 frozen 集合中的合法记录**与**明确退回修复、尚未冻结或属于获授权新 batch 的草稿**。

| 路径 | 当前授权及实现 | 不应破坏的边界 |
|---|---|---|
| 普通跨 repair frozen 重述 | SYSTEM 禁止；2030 行仍忽略重述，1595 行可能借旧行计覆盖 | 这是本报告指出的待统一路径；不得把重述的修改字段采纳为事实。当前有效 ref 仍可按原严格规则使用。 |
| 显式 `whole_value_reviews` | [120–134 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:120) 明确写“Exception to freezing”；[2126–2135 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2126) 先从 valid 移除不一致 supports，再 `frozen.discard`，把原 ID/原来源交回复核 | 这些已解冻 support 必须允许原 ID 修复；原草稿来源仍由 2050–2054 校验保留。已验证 counter 保持 frozen，不能因整值修复一起解冻。已整合 known routes 也不能当作可随意改写的草稿。 |
| Summary 冲突或 downstream handoff 拒绝 | [2120–2125 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2120)、[2151–2156 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2151) 将被拒 support 从 valid 移除并解冻，加入 named failure | 必须允许同 ID 在原有预算内纠正；不是未经授权篡改已接受事实。义务释放在 handoff 失败后仍回滚。 |
| 非法 envelope 中的 `required_counter_observations` | [1936–1971 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1936) 在外层格式校验前捕获草稿及 source-validated counter 关系，**不冻结支持，也不先整合反证**；正常校验成功才在 2069 行冻结 | 首次外层失败里的 counter 仍是必须原 ID 提交的未冻结草稿。允许它在修复 envelope 后重发，并由 2044–2046 及 2114–2118 校验原 counter 身份。不能因“见过 ID”而拒绝，也不能取消 envelope 校验前的反证捕获。 |
| 后续 envelope 异常碰到已接受 frozen counter | envelope 错误本身没有通用解冻；已接受 counter 通常已在 `accepted_counters` 满足保护关系 | 不能把“外层格式失败”当作改写既有 counter 的许可。保留本地 accepted 行；仍需修复的未接纳草稿单独处理。若同 ID 又携带新 counter，仍要保留新关系的失败证据，不能因拒绝重述而忽略它。 |
| Duplicate replacement | SYSTEM 95–97 与 2171–2172 明确授权确定性的 replacement IDs；2055–2068 对已合法草稿保护除 id/reason 外全部内容 | 这些显式新 ID 不能被 named-only 的普通新增禁令误拒；也不能接受只重述原 ambiguous ID 而丢掉其它草稿。 |
| 获准的 durable failed-batch recovery | [166–186 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:166) 允许 `review_allowed=true` 的付费恢复；新 batch 在 1897 行重新建立本地 valid/frozen；1360–1378 保留旧 counter/来源 | 可以按原 failed ID 复核，不能依据全局历史 ID 判作当前 frozen 重述。没有 `review_allowed` 或新原文/绑定资格时，不能借此免费恢复。 |
| 同一响应里完全一致的重复草稿 | [1926–1935 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1926) 按完整 digest 去重，既有测试将其视为幂等 | 这是同响应完整相同行去重，不等于跨 repair 仅凭 ID 借旧 frozen 行；不能混成一条拒绝规则。 |

`whole_value_reviews.known_observation_ids` 还只是输入的无损存储引用（158–163 行），与输出的 `reviewed_observation_ids` 权限不同；前者不授予编辑已整合 route 或借取跨批覆盖的权利。

已只读核对 [test_v4_joint_reading.py:78](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_joint_reading.py:78)、94、121、139 的 envelope/counter 修复边界，及 [408 行](/Users/mao/projects/dagv2-personamem-v4/tests/test_v4_joint_reading.py:408) 的同响应幂等与 duplicate replacement。未运行测试。后续修改若有，应同时覆盖正常冻结重述拒绝与这些合法例外；本报告不授权直接对所有 frozen/曾见 ID 加统一拒绝。

## 4. 另一处较小的审计结果措辞歧义

[joint_reading.py:234](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:234) 的 `AUDIT_INSTRUCTION` 写 `supported ...; unknown otherwise`，而 [personal_task.py:142](/Users/mao/projects/dagv2-personamem-v4/dagbt/personal_task.py:142) 要求 `conflict/unknown`，schema [265 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:265) 及校验 [2094 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2094) 允许三种 verdict。

这里没有 schema 表达障碍，但二分的通用措辞与三分的专用协议不完全一致。可在后续提示整理中明确真实冲突与证据不足的区分；现有材料不能证明它造成第五题或其他题失败。

## 5. 已知 wildcard 歧义及本轮范围

已有 [r15_wildcard_repair_contract_review.md](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r15_wildcard_repair_contract_review.md) 已说明：`(variable, '*')` 失败时本地校验允许新增唯一观察 ID，但通用提示未明确这项例外。这里不将它作为新发现重复统计。它与上述 named-ID 状态转移应一起解释：wildcard 允许补充真实审查；具体 failed IDs 仍必须保留；冻结行的复核方式另有授权，不因 wildcard 自动变得可编辑。

本报告没有发现必须通过减预算保护、删除原文/反证、自动合并摘要、无偿恢复失败或接受非法输出才能解决的 schema 障碍。适合的后续工作是明确阶段/ID 授权并统一 frozen 重述的执行契约，再按原来源、scope、预算和审计要求验证。继续等待 R15 全 14 题，本轮不实施。

## 6. 第六题实证：audit schema 允许缺 verdict，validator 必须有 verdict

**源码差异明确，且同时覆盖 generic / PersonaMem audit 与其普通 repair：**

- 基础 [SCHEMA:265](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:265) 定义 `audit_verdict` 的三态 enum，但顶层 `required` 只有 `slots`。
- [_schema:606–691](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:606) 在 audit 输入下未把 `audit_verdict` 加入 required。仅声明字段类型/enum 不意味着字段必填。
- [_payload:559–560](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:559) 为所有实际 audit 设置 `audit_instruction`；PersonaMem 额外有 `phase=response_audit`，generic audit 不依赖该 phase。故不能仅检查 PersonaMem phase。
- [read:2092–2095](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2092) 对 audit 每次响应都检查显式三态 verdict，缺失时 `get` 为 None，拒绝为 `Audit must return an explicit verdict`。
- 普通 audit repair 在 [2177 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2177) 继续以 `audit=True` 生成 payload；2195–2196 行还保留 `audit_instruction`。每次都经同一 `_schema(current)` 与上述 validator，因此相同差异延续到 repair。

**本轮独立核对的已归档实例：**

第六题（manifest 索引 5），stage `['audit_joint', '16']`，请求文件：
[5bfa03cd…json](/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r15/personamem/dagbt_residual_memory_v2/attempts/b272b6ee35b862af92390ff973abed213738f35ec47b46e46aeffd1255605071/attempt-001/requests/5bfa03cd20beaf835daf985a43de4484250a8283fec81f46e0ab47926be6f35c.json)。文件 SHA-256：`4bef4a9a6b76307f4c3daab11af81198f5958e2a5c36cdb9de6b0c439992e534`。

- 从实际 system message 尾部提取到一份 schema：`required=['slots']`；audit_verdict 定义为 `string`，enum 为 `supported/unknown/conflict`。
- 响应顶层键只有 `['slots']`，确实没有 audit_verdict；`finish_reason=stop`，不是这次响应截断导致的字段缺失证据。
- 对应 `fusion_events.jsonl` 的 `joint_read_completed`（sequence 552）为 `audit_joint`、`audit_complete=false`；5 个 failed slots 均为 `Audit must return an explicit verdict`，该 batch 没有其它 failed-slot 错误。
- 请求使用 `plain` 输出模式，schema 被放在提示中，而非服务端 strict response_format；这不改变两套契约不一致的事实，但意味着仅修 schema 不能保证模型以后绝不遗漏字段。

**最小修订边界，仅供之后实施：** 对真实 audit payload（现有明确标记是 `audit_instruction`，同时覆盖 generic 与 PersonaMem）在 schema 顶层要求 `slots` 和 `audit_verdict`，保持三态 enum 与运行校验。不得把缺失值自动填为 supported，也不应伪造 unknown 来掩盖未返回审计结论；仍应按原有有限 repair/失败路径处理模型违规。

历史 phase 必须保持仅 `slots`，不得因基础 schema 中存在 audit_verdict 属性就全局将其设为必填。普通 terminal selection 也不应新增 verdict 要求。terminal-only repair 在 [2224 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2224) 明确仅由非 audit 路径调用，并在 [1807–1811 行](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1807) 要求且只允许 `slots=[]`、`semantic_answer`、`final_prediction`；这套契约须保持。

这证明第六题该审计调用的一次明确协议失败，以及 schema 未表达 validator 的必填要求。尚不能证明缺 verdict 是整题唯一最终失败原因或修复此项就能答对。此次仍未改源码、运行测试或调用服务。
