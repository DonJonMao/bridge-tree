# R16 shared_history_text：未来集成路径与边界审查

审查基线：`b9e28a7faa8d419f9f1283574fa095399919c243`，`/Users/mao/projects/dagv2-personamem-v4`。本次仅阅读源码、现有测试及外部原型；未修改源码、运行测试、请求 tokenizer/模型服务或改变 R16。原型仍未集成。

**结论：适合在 JointReader 现有 wire 打包完成后增加候选变换，并让 system 指令与变换实际是否发生绑定。正常 reader、局部 repair、durable recovery、forecast、mandatory handoff 的主调用链可共用这一边界。确有绕过 `_wire_data` 的独立符号终端生成入口；不能按 `semantic_compose` 操作名在 Reasoner 全局打包。另发现原有 terminal-only repair 的 schema 准入/发送不一致，应在后续独立小修中统一。**

## 1. 三种数据必须保持分离

1. **规范状态及规范 payload**：`JointReader._payload`（joint_reading.py:477）构造来源、父值、known routes、query、义务、失败事项和作用域。不得改变其内容、字段顺序、状态身份、source 闭包或后续恢复权限。`_selection_data_identity`（1034）对保留字典顺序的 JSON 字符串求摘要，不能改为编码后内容。
2. **实际输入 wire**：`_wire_data`（710–794）依次处理文档元数据引用、来源列式表示、whole-value known route 引用、known observation 共享单元格表及个人指令去重。新变换应接在这些步骤之后，以整个旧 wire 为失败/无收益回退值；不要仅回退部分已解码的表。
3. **输出 schema 与真实输出**：`_schema`（620–707）继续接收规范 payload。输入共享引用不得成为 observation 输出的新值类型、引用来源、审查许可或新状态。`_observation`（1139 起）仍要求完整 `value` 和原有字段，不能允许 `value_ref`/`text_ref` 作为输出捷径。

原型只共享 supported parent 的精确长 text 值，以及与其严格相同的顶层 parent/known 字符串值和 grounded query 子串。不压缩来源原文，不递归改写 failed drafts、terminal expected value、反证、route metadata 或任意嵌套对象。输入解码后应恢复原有类型、文本、次序和所有证据字段。

## 2. JointReader 的全部直接入口

本次源码检索中，`_wire_data`、`_system`、`_schema` 的生产直接调用集中在以下三组；没有第四个隐藏的 JointReader 生成调用。

| 入口 | 当前路径 | 新编码应覆盖的范围 |
| --- | --- | --- |
| `_estimate`，797–800 | `_wire_data(data)` → `_system(wire)`，同时 `_schema(data)` → `Reasoner.estimate` | 所有通过该包装器的准入、修复和容量预测 |
| `read` 生成循环，1999–2003 | `_wire_data(current)` → `_system(wire)`，同时 `_schema(current)` → `Reasoner.request` | `joint_read`、`semantic_compose`、`audit_joint`，及三种 `_repair`；普通局部修复和 durable recovery 均在此 |
| `_repair_terminal`，1821–1824 | `_wire_data(repair)` → `_system(wire)`，同时 `_schema(repair)`，随后覆写 required → `Reasoner.request(operation+'_repair')` | 终端一致性专用修复；需保留完整 expected typed value、slots=[] 和原始来源 |

`_system`（1106–1138）从实际 wire 选择现有解码、阶段、审计、义务和终端指令。若新变换把旧 known table 解码为对象列表，`known_observation_columns` 消失，旧表解码指令也应自然消失；source columns 和 whole-value route IDs 等仍存在的编码必须继续保留各自指令。

**应用状态不能仅由字段存在推断。** 原型在原输入已有 `shared_history_texts`、`grounded_subquestion_parts` 或 row `value_ref` 时原样返回。未来调用者若只判断 `shared_history_texts in wire` 就追加新解码指令，会把保留字段碰撞误认为成功变换。应由变换返回可信的 applied 状态/编码元数据，并在三个入口共用同一个准备函数；该状态留在调用层，不混入规范事实或错误地发送为来源字段。保持现有 `_wire_data` 的字典返回接口也可以，但新增准备层必须明确传递实际应用状态。

## 3. 预测、修复、交接与真实生成的一致性

| 容量/控制入口 | 是否经过 `_estimate` | 必须保留的边界 |
| --- | --- | --- |
| `_fits`（802） | 是：base 及普通 repair envelope | 旧义务/槽位修复开销完整保留；只变编码，不减少输出或调用预留 |
| `_fresh_window_fits`（814） | 是：先 `_fits`，再 whole-review forecast | 未知初稿空间仍单独保留；字节节约不能自行判定 token 可放下 |
| `_whole_review_forecast`（846） | 自身仅构造规范预测数据，调用者送 `_estimate` | 同一 shared-text 变换可参与计数，不得将预测失败事项当作真实恢复授权 |
| `_adaptive_fresh_cap`（1005） | 是：forecast、base，及实际 cap 的重新计数 | 仅首个合格 history 请求使用 cap；真正 repair 仍用完整输出预留，结构 floor 不变 |
| `_fitting_prefix`（1051） | 通过现有准入链 | 候选必须按实际编码重新核算；继续允许编码大小非单调，不将 byte 判定当 token 单调性 |
| `_repair_fits`（1039） | 是：实际规范 repair payload | 完整失败草稿、来源及权限计数；不沿用首次窗口的过期计数 |
| `_handoff_failures`（1676 起），常规 checks（1774） | 是：新 probe 的 `_payload` → `probe._fits` | nonterminal compose、semantic terminal、audit mandatory 闭包均获得相同编码；仍禁止删反证/既有 unread |

`read` 在发送前用 current 的规范 source_spans 构造 visible map（1997），在规范数据上做恢复权限检查。新编码只能影响输入表示，不能使 canonical sources、unread ownership、failed-batch recovery eligibility 或身份检查改读引用表。

## 4. 两个重要绕过，以及其他 Reasoner 调用

### 4.1 joint_reading.py:1793 不是漏打包的普通 reader

`_handoff_failures` 的这一分支直接调用：

```python
system, data, schema = controller.terminal_format_request(certificate)
count = self.e.reasoner.estimate('semantic_compose', system, data, schema)
```

触发要求 ready certificate、有公开选项、没有唯一与证书输出完全相同的选项，并且没有既有 reader semantic inputs/result。它检查的是**计算型符号终端的独立格式化请求**。对应生成在 `ResidualController.terminal_format`（residual_control.py:480–518），实际调用为 516 行 `Reasoner.json('semantic_compose', system, data, validate, schema, reserve_repairs=0)`。

该 envelope 由 `terminal_format_request`（461–478）统一构造，字段是 certificate、semantic_result、original_source_spans、public_output_question、public_options、output_identity；没有 JointReader 的 parent/known/query 协议。此路径真实生成会绕过 `_wire_data`，目前是合理的协议边界。新原型不要强行套用；若未来专门优化它，必须同时修改此 envelope 的准入与生成，并覆盖 `Reasoner.json` 的修复重建。共享 operation 名不等于共享输入结构。

PersonaMem 的 semantic response-selection 通常走 reader 路径；这不构成删除通用符号格式化路径的依据。

### 4.2 `_fresh_structure_floor` 是只计数的输出模板

joint_reading.py:986–1002 通过 `Reasoner._payload(operation, '', {})` 建壳，再替换成一个 assistant message，内容为 `_fresh_structure_response` 的完整、保留状态的 typed response；最后调用 `_count_payload(operation+'_structure', payload)`。它既不经过 `_wire_data`，也不发送生成请求。

**不能把输入引用编码套到该 assistant skeleton。** 模型仍须输出完整值；若因为输入共享就降低输出结构 floor，会错误接纳实际容纳不了完整输出的初始 cap。

### 4.3 其他生产调用保持原协议

`Reasoner.json`（reasoning.py:213 起）不会回到 JointReader；它深拷贝原数据并附加 validation_feedback，经自己的 estimate/request 做有界修复。planner（engine.py:123、runner.py:257/260）、map（evidence_mapping.py:154/379）、select（engine.py:519、final_selection.py:298）、row recovery（row_recovery.py:79）各有独立协议。新 shared-text 编码不应挂在通用 `Reasoner._payload` 或按 joint operation 字符串全局启用。

## 5. 已有 terminal-only schema 差异与建议小修

当前 `_repair_terminal` 在 1816 行先用 `_repair_fits` 计数；后者调用普通 `_schema(repair)`，此时 required 通常仅为 slots。1823 行发送前才改成 `['slots','semantic_answer','final_prediction']`。plain/json_object 模式会把 schema 串接进 system，因而两次计数的实际消息不同；真实 `Reasoner.request` 会再计数和 preflight，故不会绕过最终容量门，但早期准入可能接受一个最终不能发送的请求，也可能先消耗一次 json repair 额度。

此差异直接由 `_schema` 的初始 required（270–276、620）、`_repair_fits`（1039–1042）与 `_repair_terminal`（1816–1824）的实际串联实现证明。本次未执行新的离线请求或测试。root 已扫描当时 R16 实际归档，`r16_terminal_repair_schema_admission_review.json` 的 `rows=[]`，未找到已发送的 terminal_repair 请求。因此它是静态确认的既有差异及后续修复候选，**不能归因为 R16 已发生失败，也不能报告已测得的实际 token 差或运行损失**。自然运行结束前不改源码。

建议未来独立小修：将 terminal_repair 的三个 required 字段统一放进 `_schema`，删除 1823 行的发送入口覆盖，使 `_repair_fits` 与实际发送使用同一 schema。不要借这个修复扩展 schema 到输入引用类型。

已核对 `tests/test_v4_mandatory_contract_review.py:228–244`：`terminal_only` 分支只要求不增加 audit_verdict，与增加上述三个 required 字段兼容；history 分支要求 properties 仅 slots，需继续保持。`read` 的 `_repair_terminal` 调用受 `not audit and (semantic or terminal_output)` 条件约束（2313），个人 payload 在该路径的 phase 为 response_selection（`_payload`:566–578），所以真实路径不会混成 history 或 audit。

稳妥的 schema 改法需明确不支持的混合输入：history_evidence+terminal_repair 或 audit_instruction+terminal_repair 不应静默取消 history/audit 的既有契约。可在构造/校验层拒绝矛盾阶段；普通 audit 仍必须 required audit_verdict，普通 history 仍仅 slots。测试同时覆盖这些边界，而不是全局用一个 required 列表覆盖所有阶段。

## 6. 实际请求计数与 cache 身份

- `Reasoner.estimate`（105–108）与 `request`（129–146）都调用同一 `_payload`。真正 system（包含新解码指令）、user JSON、输出 schema 和实际 cap 必须进入该层；不能在 estimate 之后才添加共享表或指令。
- `Transport.count_reasoning_tokens`（transport.py:74）和 `get`（116 起）都经过 `prepare_request`，对最终适配 wire 计数。最终限制仍是 input + max_tokens + 256 + 8 <= 16384。
- **生成 cache**：`request_identity`（47–54）包括 unit、URL、完整实际 payload、适用算法版本/评分上下文；`get`（139–145）据此求 digest 并严格比对。消息或输出 cap 变化会产生新生成身份，不能复用旧 wire 结果冒充新输入结果。相同新 wire 的回放仍逐次扣逻辑预算并验证 token usage（147–156）。
- **计数 cache**：`DeploymentTokenCounter.count`（token_counting.py:226–280）的 key 是 endpoint、mode 与 tokenizer 请求的 model/messages/add_generation_prompt。新 system 或 user 文本会产生新 key；仅 max_tokens 改变不会改变输入计数 key，这是有意排除生成参数。每次返回仍更新完整 `tokenization_wire_sha256`，真实生成上下文检查仍加上当次 max_tokens。不要把生成 cache 和计数 cache 的 key 规则混写。
- 编码应确定性：相同规范数据及应用状态重复生成的字节/消息相同；不通过随机 alias、动态指令或依赖外部状态的表序制造缓存漂移。

## 7. 最小有意义的回归证据（未来实施，本文未执行）

1. **三条实际入口一致**：对三种普通 operation 及三种 repair，捕获经过 Reasoner/prepare_request 的真实消息；断言 `_estimate` 与实际 `request` 对相同规范 data/schema/cap 的 wire 完全相同，新解码指令只出现一次。包括真正 `read` 局部修复、durable recovery 和 terminal-only repair，不只直接调用 pack。
2. **准入链覆盖**：同一长 parent+known+query fixture 经过 `_fits`、fresh forecast、adaptive cap、actual repair、mandatory handoff；捕获每次 counter 输入，证明全用相同编码准备层，保留普通 repair envelope、未知初稿预留及 actual repair 全额输出。用离线可控 counter 测恰好边界和一单位溢出，断言溢出不发送生成。
3. **canonical 与 schema 不变**：独立逆变换后精确恢复规范文本/类型/次序/来源/反证/parent versions/failed permission；canonical identity 和原 data 不变；schema 不出现 value_ref/text_ref，含引用的模型输出仍被拒绝。旧 known table 应先一层解码，再解析 shared text，最后还原 whole-value route ID 引用；嵌套 literal `{'shared': ...}` 不递归解释。
4. **回退/碰撞**：无收益、无 eligible parent、原 reserved 字段、预存 value_ref、坏 known table 均保留整个旧 wire，且不追加新解码指令。存在旧 source columns/whole-value refs/failed reviews 时，其他所需指令仍保留；新候选展开旧 known table 后不残留过期 table 指令。
5. **完整输出 floor**：输入共享前后 assistant skeleton 仍含完整 typed value，未用引用；不得因为 byte 节约把 cap 降到完整输出 floor 以下。适配 cap 的实际生成请求及其后续 repair cap 分别验证。
6. **terminal schema 小修**：扩展 `test_v4_mandatory_contract_review.py` 的 terminal_only 检查到三个 required 字段；捕获 `_repair_fits` 与发送完整 schema/message 相等，并测容量边缘时不先扣 json repair。普通 history、audit/repair 以及非个人终端保留原契约；测试矛盾阶段拒绝或显式边界。
7. **旁路与 cache**：符号 formatter 的直接 estimate 和 `Reasoner.json` 初次/修复输入保持原协议；planner 不受影响。新旧 system/user 的生成与计数 key 不同；同一编码重放 key 相同且仍扣预算；仅 max_tokens 改变时生成 key 改变、计数 key 可相同，但完整 wire hash 和上下文总量使用当次 cap。

已有测试可复用的支架包括 `test_joint_wire_serialization.py`、`test_v4_whole_review_wire_review.py`、`test_v4_personal_wire.py`、`test_v4_adaptive_initial_cap.py`、`test_v4_joint_reading.py`、`test_v4_mandatory_contract_review.py` 与 `test_deployment_tokenization_integration.py`。测试 double 必须认识新输入表示；不能因为 fixture 解码不完整而误报状态丢失，也不能把 decoder 测试通过当作模型理解证明。

## 8. 证据边界

外部原型纯函数的 38 个测试及字节 roundtrip 只支持结构与确定性，不证明真实 token 节约、可容纳性、模型正确解码、完成率或准确率提升。root 的归档实际 wire token 测量属于独立证据；即使测量显示变小，也需要未来集成后、冻结源码下的真实模型验证。本文不改 gate、预算、实验或部署，不声称新原型已发布可用。
