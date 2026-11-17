# R20 review-wire：按完整实际输入 token 选择表示的只读设计审查

审查对象：冻结 RELEASE `/Users/mao/projects/dagv2-personamem-v4`，commit `6c046374008ce2e45f817d6bc9876b3ab927ab18`。本轮只读源码与已生成的实际计数报告，没有修改 source/config/run，没有运行测试、tokenizer、generation 或 embedding，没有读取标签或评分。本文是设计建议，未实施。

## 1. 结论与已知证据

**当前按字节采用 review 编码，确实可能把原本符合容量的请求推到上限之外。** 当前独立实际测量的两个已发送 R19 repair 请求都满足 codec 的净 98-byte 收益条件，却各增加 9 个真实输入 tokens。若某个一般请求编码前距上限不足这次增加量，采用新表示后会被已有真实计数准入拒绝。现有 guard 因而仍防止超限发送，但“无损且字节更少”并不保证原请求的可执行性不回退。

| 已保存请求 | 旧输入 tokens | 新输入 tokens | 原预留下旧/新总量 |
| --- | ---: | ---: | ---: |
| joint_read_repair / 7 | 11229 | 11238 | 15589 / 15598 |
| joint_read_repair / 8 | 10911 | 10920 | 15271 / 15280 |

以上两条旧请求本来就在容量内，增加后也仍在容量内。它们不证明后续 77-source 候选是否可执行，也不解释 R20 首题失败；本审查没有构造该未发送候选，不能把这两个计数外推为解决或未解决某个 367-token 缺口。

**最小通用设计：保留“新 review 层之前的完整表示”作为基线，只在新增 review 候选的完整实际输入计数严格更小时采用它；相等或更大时保留基线。** 字节规则只用于廉价地产生候选，不再授权最终选择。该保证针对新增 review 层；既有 history/source/table 的字节选择不在这个最小变更中，不能因此声称相对完全未打包原文也全局最优。

## 2. 当前所计所发路径与全部接入点

| 位置 | 当前作用 | 设计要求 |
| --- | --- | --- |
| `joint_reading.py:1129` `_prepare_wire(data)` | 纯函数式地执行旧 packing、history、review，并按各层 applied 拼 system；目前最终 review 只看字节 | 保留纯候选构造边界，提供 baseline 与 review candidate 各自的完整 wire/system |
| `joint_reading.py:1143` `_estimate(operation,data,output_token_cap=...)` | 用 `_prepare_wire`、canonical `_schema(data)` 调 Reasoner.estimate | 使用同一实际计数选择器，返回被选表示的 count |
| `joint_reading.py:2192–2194` `_repair_terminal` 请求点 | 对 `operation+'_repair'`、完整 terminal-only schema、默认输出上限发起修复；前面已有 `_repair_fits` 与付费 reserve | 与 estimate 使用相同 selector、schema 与 cap；不改变 reserve 时机 |
| `joint_reading.py:2433–2440` 主 read/repair 请求点 | 计算 `request_operation`；仅符合条件的首次新读带 `initial_cap`；其他读/repair/audit使用默认 cap | 必须先确定真实 request_operation 与 cap_options，再选表示；不能拿原 operation/default cap 的结果给实际 repair/capped request 用 |
| `joint_reading.py:583` `_request_with_exposure` | 上述两点统一进入这里，先记录原始 source exposure/unread，然后 `reasoner.request`；line 587 是唯一直接调用 Reasoner.request 的位置 | 实际请求的选择计数应放在此 wrapper 的 exposure 记录之后，既有 request 前 |
| `reasoning.py:70` `_payload` | 实际 JSON 序列化、plain 模式 schema 系统后缀、输出 cap 与 reasoning marker | 候选必须使用此方法生成，不能手拼另一套 JSON/schema 消息 |
| `reasoning.py:110` `_count_payload` → `transport.py:71` | `prepare_request` 完成 model/provider 适配后，通过该 Transport 的 DeploymentTokenCounter | selector 复用此链，不新建 counter，不另算正文或 regex |
| `reasoning.py:129` request | 再生成 payload、完整计数、_preflight，然后递增 sequence、进入 transport | 保留最终计数和准入，不用 selector 的缓存数字绕过 |
| `transport.py:103` get | 对最终 wire 再计数、核对完整输入+输出+margin，再缓存/发送；后续核对 provider prompt_tokens | 全部保留，不在 transport 二次改变已经选择的表示 |

`_fits`、`_fresh_window_fits`、`_adaptive_fresh_cap`、`_repair_fits` 和引用它们的 prefix/handoff 预测均通过 `_estimate` 继承同一个选择。`_fresh_structure_floor`（line 1332）测的是独立 assistant 响应模板，不是 reader input review 表示；不要对它套这个 codec，也不改它的准入含义。

## 3. 建议的最小结构：纯候选 + 一个计数选择器

以下是概念接口，不指定最终 API 名称，也不要求新 framework。

### 3.1 纯候选构造

1. `base_wire, history_applied = pack_history(_wire_data(canonical_data))`。
2. 为 base 构造实际 system：`_system(base_wire)` 加且仅加本次 `history_applied` 授权的 instruction。
3. `candidate_wire, review_applied = pack_review(base_wire)`；若 False，只有 baseline。
4. 若 True，为 candidate 构造其完整 system：`_system(candidate_wire)` 加保留的 history instruction，再加本次 review instruction。
5. canonical `_schema(data)` 在本次选择中只生成一次并独立复制；两个候选使用同一 schema、operation、response_format、max_tokens/cap、provider 参数。原 canonical、FactState、raw、sources、角色和权限不参与表示修改。

这里不能把原本有 `shared_review_texts` 的 payload 当作 applied，也不能把基线的 history instruction 删掉。新层 inverse 必须恢复这个 base wire，按完整 unsorted、type-sensitive JSON 校验。instruction 放在 Reasoner 的 schema 后缀之前，与实际 Reader 链一致。

### 3.2 完整计数及确定性选择

对各候选使用当前 `Reasoner._payload(operation,system,wire,schema,output_token_cap=cap)`，然后 `Reasoner._count_payload(operation,payload)`。这个路径在生产中经过实际 adapter，再计数完整 messages 与 chat template；包括完整 system、所有解码说明、schema、完整 user wire 和 generation prompt。

仅有一个候选时沿用其正常计数。两个候选时先取得 baseline 与 candidate 的有效实际计数，再比较：

```text
selected = candidate if actual_candidate_count < actual_baseline_count else baseline
```

相等时固定选择 baseline，避免增加无收益的引用解释负担。这个规则不引用题号、source 数、失败原因或容量缺口。两个候选的输出预留及其他预留相同，所以最小输入 count 同时是不更大的完整准入总量。

**比较本身不能对每个候选分别执行 `_preflight` 后遇基线超限就退出。** 基线输入仍可被 tokenizer 合法计数而无法生成，candidate 可能更小；应先完成选择，再让已有正常准入核验被选表示。若两者均超限，仍走原超限失败；不删来源、raw、反证或反馈，不扩大 context，不缩小 output cap 以“帮 codec 成功”。

建议 selector 返回独立的所选 `wire/system/schema` 和 accounting/count（可附完整 payload 摘要及选择原因）。estimate 读取其中 count；request 使用同一所选 tuple 调现有 Reasoner.request。最后的 Reasoner 与 Transport 计数仍执行，通常命中现有 counter cache。

### 3.3 实际请求上的错误与 exposure 顺序必须保留

当前 `_prepare_wire` 不触网，而 `_request_with_exposure` 在进入 Reasoner 的实际计数前已经记录 conservative attempted exposure/unread；即使 tokenizer 失败，也会被 wrapper 标记 failed/not_sent 并保留相关未读义务。

**不能直接把网络计数塞进原 `_prepare_wire` 后保持现有两调用点不动。** 那样会在 `_record_source_exposure` 之前失败，绕开 wrapper 的失败记录，改变 canonical 未读状态。最小接线建议是：

- `_estimate` 调计数选择器，但它仍然只是预测，不制造 exposure。
- 实际两请求点保留 canonical schema/cap/operation 的决定及现有 repair reserve 顺序；把纯候选或 canonical data 交给 `_request_with_exposure`。
- wrapper 先执行现有 `_record_source_exposure` 和 sequence 快照，在既有 try 内做同一个计数选择，再调用原 Reasoner.request。所有异常仍经现有 except/finally 处理，`sequence` 在真正 request preflight 之前不增加。
- 不能因候选测量而修改 `last_response`、`requests`、durable seen sources/signatures、frozen rows、repair_inputs、initial-cap identity 或 completed/pending 状态。

这样可把生产变更限定在 JointReader 的纯候选/selector、_estimate、wrapper 与两请求调用点，无需修改 Reasoner/Transport/DeploymentTokenCounter 的协议及失败机制。是否新建小的 Prepared 类型属于实现选择；关键是两候选/选择结果不可与 canonical 共享可变对象。

## 4. 实际计数能力与失败策略

- 只有计数明确为 actual（当前部署链 `token_count_is_estimate is False`，且完整支持当前 wire）才允许证明 candidate 不增加 tokens。不能用 regex 或字节差为新表示背书。
- 对本来就没有 opt-in deployment counter 的 legacy/offline配置，保守选择 baseline，按其既有机制估算/运行；明确此时没有给出真实 token 的比较保证。为测试注入 actual fake counter 应由测试显式建立，不在生产偷偷降级。
- 已配置 deployment counting 却缺 shared counter、tokenizer 断连、HTTP/形状/计数错误、context 配置不匹配等，沿用当前错误传播；不要捕获后当成 0、退回 regex、改称 InputOverflow/ProtocolError，或循环尝试不同表示以隐藏服务故障。
- 即使 baseline 已成功计数，candidate 计数失败也不能宣称完成了非增保证并静默继续；最小方案传播原失败，维持 fail-closed 原则。若未来希望“可选优化失败则继续已确认基线”，那是独立的故障策略变更，需明确审查，不能混入本次最小修正。
- 当前生产 counter 的既有有限相同请求 retry 策略原样保留。本次前述独立诊断设置的一次尝试只属于诊断对象，不能迁入运行配置。

两个候选意味着潜在更多 tokenizer 请求和服务故障机会。保持失败类别/策略不变不等于运行时失败概率或延时完全不变，不能作这种承诺。

## 5. 身份、缓存与预算

**不必先增加第二份持久“表示选择缓存”。** 当前 DeploymentTokenCounter 已有每个 transport/run 的 512 项成功计数 LRU，key 包含 endpoint、mode、model、完整 messages、`add_generation_prompt=True`；user 是已序列化的字符串，因此原 dict 顺序、精确空白/转义和 schema/instruction 内容均参与键。

- selector、Reasoner.request、Transport.get 必须复用同一生产 counter；重复估计/发送即可命中相同 payload 的计数。
- counter 输入 count cache 有意不含 max_tokens 等采样字段，因为服务 tokenize 请求只用 messages；每次返回仍更新完整 wire 的 `tokenization_wire_sha256`。selector 必须按实际 cap 重建 payload，不能把这个 token cache 的实现细节误作允许更改 output cap 的理由。
- 保持现有 `_selection_data_identity`（line 1381）的 canonical、保序 JSON 身份，保持 query/repair/semantic material identities 不变。传输 response cache 继续由实际 adapter 后 wire 决定，baseline 与 candidate 应是不同请求身份，不能共用模型响应。
- 不以排序后的 canonical-data digest 单独缓存选择，因为它不能表示原序列化字典顺序、实际 schema、system、operation 及 cap。若确需额外选择缓存，须是 run 内有界缓存且以两份完整实际 payload 和配置/endpoint/counter身份为键；本轮最小方案没有必要。
- estimate 与最终 request 若实际数据/权限/cap已变化，必须重建并重新选择；不能借先前预测结果给变化后的 wire 放行。最终选定tuple必须原样进入 Reasoner，且既有最终count/preflight/transport budget校验保留，防止所计所发错位。
- 候选计数仍只记 `tokenization_count` 成本事件，不 reserve LLM/ANN/reader/repair，不制造 model request、completion或semantic progress。repair/LLM实付规则、wall timeout、audit reserve、context/output/margin/safety 上限完全不变。

## 6. 风险及应测试边界（本轮未执行）

1. **真实 token 与字节方向相反**：字节通过而 candidate token 大于 baseline、相等、严格更少；前两者固定 baseline。可用独立 fake deployment count，不依赖实现内部重复公式。
2. **容量边界**：baseline可适配/candidate不可；baseline不可/candidate可；两者均不可；相同 output+margin+safety 下，选择后只通过原 guard，不提前因baseline超限丢弃可适配候选。
3. **三条统一路径**：_estimate、普通 read/repair/audit 的真实wrapper、terminal-only repair；检查完整最终messages与被计数候选一致，两实际调用点无遗漏。operation 包括全部六个 compact JSON joint operation，schema包含完整终端字段/slots=[]契约。
4. **真实 cap**：首次 fresh-history cap、repair回默认cap、durable recovery、audit reserve=0；两候选的输出cap及schema相同，实际所发cap与计算cap一致；既有结构floor/forecast规则不变。
5. **两个 codec 的独立状态**：history only、review only、both、neither；history碰撞但review可用；review碰撞只baseline；预存保留字段不激活说明；丢弃review候选不能留下review instruction或refs。
6. **exact inverse与不可变性**：所有已审路径、raw invalid_response、旧表、全部源/反证/metadata/type/order不变；所选tuple与canonical不alias；不自动解码模型输出refs。
7. **缓存边界**：第一次两候选计数、第二次相同estimate/request实际cache命中；改变schema、system、字段顺序、source文本、model/endpoint、cap时形成正确身份；LRU淘汰后的重新计数不复用陈旧选择；不持久复用counter结果。
8. **计数失败**：baseline失败、candidate失败、结果非actual、部署tokenizer不可达/非法结果；不生成、不额外reserve模型预算、不regex fallback、不扩大重试；wrapper已有attempted/unread及not_sent/sequence语义保持。
9. **state与预算**：source exposure放在与旧路径相同位置；被拒候选不改变FactState/repair_inputs、review_allowed、owner、frozen/pending、cap identity、收费顺序；新增成本仅是实测tokenizer事件。
10. **最终防线**：Reasoner与Transport仍计数实际所发wire，usage.prompt_tokens mismatch仍拒绝；不能因“selector已经测过”删掉这两个校验。

表示选择每次有候选最多额外一份tokenizer计数，prefix search/forecast可放大该开销；512项LRU可能淘汰。先复用当前缓存和确定性候选，不为省诊断成本跳过exact计数，也不借此重写prefix选择、历史义务或预算政策。没有token净收益时优先baseline本身已经避免增加模型解码负担；有token收益仍不证明生成理解更好。

## 7. 只读身份与限制

| 文件/证据 | SHA256 |
| --- | --- |
| `dagbt/joint_reading.py` | `47290d56d15a7e2b5998254ccb89f08e0eca53f784ae1c0a5b6d65e11c5c07a4` |
| `dagbt/reasoning.py` | `52e1d03bc8848f66be4fb3d20928765e0df34e5317f695d1d8b3bec18b4895da` |
| `dagbt/transport.py` | `9c974dd54e6f68243d29039b8e6c86567b9bc6c0ec91dec0e47659877e7189ee` |
| `dagbt/token_counting.py` | `752158005dd27ee16707fcd21ce4675ad4b2371165c0ac2f57cf65ea135868ab` |
| `dagbt/review_wire.py` | `d7d9174ea9f0b319f6fc994adce866d2ad494f83b5316382511d52dcfd8e75fb` |
| `dagbt/model_runtime.py` | `16635cbc3d8d2d4c9b20e894b04b5cf0f90dec6f10cb924cd1906d7c067e317b` |
| `configs/personamem-v4.json` | `6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05` |
| `r20_review_wire_actual_token_comparison.json` | `9c9e12c919415b9168cd7ec9e1ad2d9e83d9ba7e9028d22c396007568ca4ea17` |

这是可实施边界与测试建议，不是已完成实现或效果证明。其目标是避免新增review表示造成可避免的输入token回退；不承诺原本超限的必要闭包会适配，不承诺无语义失败，也不据此推断算法准确率。
