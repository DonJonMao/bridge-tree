# R16 第二题容量与义务契约复核

范围：只读 `b9e28a7faa8d419f9f1283574fa095399919c243` 源码及 R16 已保存输入请求、事件、结构化状态。题目 `f546a74f-54de-40d0-9d88-8b0e30467d7b`，attempt key `2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0`。没有读评测标签或 response.raw/model-output 文本，没有请求服务、运行测试、修改代码或干预实验。

运行目录：`/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r16/personamem/dagbt_residual_memory_v2/attempts/2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0/attempt-001`。

## 结论

本例不是剩余调用预算为零，也未重现按父来源所在 document 展开额外窗口的旧问题。两个直接瓶颈为：

1. 新 `current_attitude` 支持草案的真实下游必要来源并集为 **39 spans**。当前终端请求表示、SYSTEM、schema 和预留合计超过固定 16k，support 因此没有被纳入事实。
2. 失败记录按现行明确契约保存了此次读到的 **全部 80 spans**，随后的历史恢复必须再现整窗；8 个未读源组即使缩到已试的最小单组仍不能容纳。终端随后被相关 foreign unread 保护正确拒绝。

存在可证明的表示重复：三个当前历史整值均同时出现在接地 query、supported_parents 和 known_observations，重复超过一份的内容共 **6,418 UTF-8 bytes**。这支持研究无损传输共享，不证明具体 token 节省，更不证明共享后本题会完成。当前预测与实际 mandatory 路径使用相同构造器及容量算法；未发现本例的错误多算/错误扩源。

## 1. 必要下游闭包如何得到 39

初始 DAG 为三个无父输入 retrieval：`creative_history`、`getaway_prefs`、`current_attitude`；终端 `response` 是 compose，明确依赖这三个输入。

从已保存结构化来源集合计算：

| 集合 | 来源数 |
| --- | ---: |
| 当前 creative_history | 33 |
| 当前 getaway_prefs | 18 |
| 旧 current_attitude | 16 |
| 被拒的新 current_attitude 草案 | 29 |
| 三个旧事实的来源并集 | 37 |
| creative ∪ getaway ∪ 新 current 草案 | **39** |

新草案的 29 个引用包含旧 current 的全部 16 个引用；扣除其他两个父事实已包含的引用后，新草案只为终端并集增加 2 个来源。现存旧 creative/current 路线保留修订祖先关系，其来源均已包含在对应新路线中，没有把并集从 39 继续扩大。

因此，39 是当前已记录声明及来源契约导出的精确并集，不是 80 个本地阅读源，也不是所有映射 span 或所在文档全文。是否其中某些自然语言引用实际上不必要，不能由集合结构证明；本次没有进行语义删证或查标签。

证据：`fusion_snapshot.json` 的 `diagnostics.fact_state.sources/routes`、`joint_reading.failed_batch_reviews[0].failed[0].observation.source_ids`；第 12 次已保存输入请求 `f4d0aaa514888b4b04df17a057b357560dff5fdd0add9bfc11d84f2451814e22.json` 的 repair 条目。

## 2. handoff 预测与 mandatory 真实路径是否一致

`dagbt/joint_reading.py:1676` 的 `_handoff_failures` 建立拟接纳本批观测后的状态；为活跃受影响下游取本地输出变量与真实父绑定，再调用 `_payload(target, query, variables, [], semantic, audit=...)`。本例拟接纳后需要 response + 三个父变量。

真实 compose 路径位于 `dagbt/residual_control.py:639` 附近：compose 不再把父 source 转成 document 窗口；`read(... source_scope='mandatory_closure')` 加入相同的实际父变量，`_mandatory_scope_payload` 同样以 aliases=[] 构造 payload。`_payload` 用集合汇集 known routes、supported parents、现存义务等来源，按实际 source alias 去重，见 `dagbt/joint_reading.py:476`。

两条路径同用 `_fits`（约 804 行）：实际初次输入与每 requested slot 的结构化 repair envelope 各计算一次，取较大者，再加 **4096 + 256 + 8**。本例终端 handoff 没有套 history fresh-window 的第二个未知草案 4096 reserve。

事件 425/426 的输入计数是 12,817 / 13,046；439/440 是相同 wire hashes 的缓存重用。对应总量：

- 初次终端：12,817 + 4,096 + 256 + 8 = **17,177**，已经超限 793。
- 带结构化 repair envelope：13,046 + 4,096 + 256 + 8 = **17,406**，超限 1,022。

因此，仅删除保守 repair envelope 也不能让该初次终端适配 16k。相比之下，第一次 current 旧事实形成时，事件 337/338 是 11,664 / 11,893，对应较大总量 16,253，尚有 131 tokens 余量；后一次摘要增长、修订记录和两份新增来源使下游跨过边界。

限制：终端实际未被发送。预测身份是 synthetic handoff identity，实际执行身份不同；实际入口另检查 unread 所有权。初审确认当前必要 payload 的构造范围与计量算法一致；后续零服务复核已完整重建两个当时的预测 wire，并匹配历史 SHA256，见第6节。后续阅读可能改变义务及状态，handoff 也不保证未来一定可发送。

## 3. 全部 80 源恢复义务：刻意契约，还是必要 proof

本次最终保留的是一个结构、来源、summary revision 检查已经通过、随后被 handoff 容量拒绝的 support 草案。`evidence_obligations` 为零；失败项仅 `citation_capacity`。先前发生过截断，但完整修复后保留下来的失败记录不是未知解析失败。当前草案明确引用 29 个源；旧事实 16 个源是其子集，当前 retrieval 没有父输入。

80 的来源是 `_store_failed_reviews`（约 1453 行）统一把 data/current 两个 payload 的全部 visible source 取并集写入 `record.source_ids`，同时用于 `seen_source_ids`。随后 `_payload` 必须展示 `record.source_ids` 全集，`_failed_review_candidates`（1396 行）要求该全集在 visible 中。

这不是偶然引用扩展：`FAILED_BATCH_REVIEW_INSTRUCTION`（173 行）明确写着：

> failed_batch_reviews retain earlier FAILED reading drafts, their validation errors, and ALL original text.

`tests/test_v4_failed_batch_review.py:62` 也检查容量失败保存草案及全部原文。因而不能静默把 source_ids 从 80 改成 29，并声称只是恢复原契约。

但必须区分两个不同断言：

- **现行协议要求**恢复时可见全部 80 源，证据充分。
- **逻辑/理论必需**额外 51 个未被此草案引用的源都是此 proof 的前提，证据不足。它们是整次阅读窗口的保留义务，不是从已记录草案引用推导的必要前提。

capacity 修复已经允许模型给出足够但更短的 proof；`_failed_review_candidates` 对 citation_capacity 不强制新输出重新引用草案全部旧引用，却仍强制整次原文可见。这正是“展示范围”与“最终 proof 引用范围”的区别。

如果以后修订恢复协议，可讨论的严格边界仅是：完整可解析响应、局部观测均通过结构/范围/来源检查、剩余失败仅为 support 的 handoff 容量问题；不存在未定位的 unresolved、partial、未知解析问题、全值冲突、丢失草案或尚未覆盖的 counter。即便满足这些条件，也必须保留所有草案、修订祖先、真实父依赖、相关反证、其他既存义务和单独未读工作；原始 seen source 集仍要留作付费重试授权的历史。不能仅以29这个数字自动删源或关闭失败。

这属于需要明确版本、记录迁移及独立验证的协议变更，不是本次只读审查建议立即实施的补丁。更重要的是，缩小历史恢复 footprint 本身不会消除前一阶段 **39-source 终端已超限** 的事实。

对于 unresolved/partial 及 parse 未知失败，不可套用上述边界：slot.unresolved 没有逐条证据映射，当前 `_update_evidence_obligations`（约 1659 行）明确保留该次可见原文；解析未知时也无法证明哪些原文只与哪个完整合法草案相关。

## 4. 是否有当前合法步骤被误拒

本例未发现一个已经证明合法且可装入预算、却被错误拒绝的请求。

- 已用 LLM12/24、JSON4/6，仍有调用预算，但当前批次的有限修复额度已用于截断修复及容量草案修复，不能仅凭全局余量免费续修。
- 随后的新文本阅读须带回 failed record 的 80 原文。`_fitting_prefix` 在没有任何可接纳结果时检查剩余前缀；本例8组留下，存档最后测量中最小 input pair 为 12,355 / 12,445，总量至少 **16,805**。没有足够小的已测合法新源前缀。
- 带 failed_batch_reviews 的请求不使用 fresh unknown-draft adaptive cap；这符合当前“保留恢复输出 allowance”的策略。不能把降低输出上限认定为当前已获授权步骤。
- 用旧 current 直接终端可能有较小 footprint，但 current 仍有相关未读和保留失败。跳过这些义务发布不合法，foreign unread 拒绝不是误拒。
- 同一原文只换身份不授权失败恢复；额外 ANN 不会自动移除已强制携带的 80 个源。

仍未证明：零新增源的独立恢复视图能否装入16k、另一种合法 proof 能否更短、某种无损编码能否让本例完成。当前存档不能把这些反事实当作可用救援路径。

## 5. 有限的无损表示重复证据

另存 `r16_second_case_payload_structure.json`。通过当前 FactState/payload/packing 函数，在隔离内存中从已保存输入和结构状态重建拟接纳草案后的历史字段；禁用网络，不调用 reasoner/estimate。没有读取公共选项，所以不声称重建完整 terminal wire 或其 token 数。

打包后主要字段值的紧凑 JSON UTF-8 大小：

| 字段 | Bytes |
| --- | ---: |
| grounded_subquestion | 3,407 |
| supported_parents | 4,142 |
| known_observations | 10,079 |
| source_spans | 13,124 |
| source_documents | 2,986 |

三个当前历史整值长度分别为 1,142、657、1,410 bytes；每个都在 grounded query、supported_parents.value、known_observations.value 中完整出现三次。超过一份的纯值内容共 6,418 bytes。这里 `supported_task_outputs={}`，不存在该字段的额外重复。

known routes 共5条，当前 `known>=8` 的内部 cell 共享不会触发；现有共享也不跨 grounded query 与 supported_parents。旧路线、版本、来源和修订祖先有不同作用，不能把整条 old route 简单视作冗余删除。值的无损引用有进一步研究空间，但引用协议和解码说明也有成本，不能按字节比例推算 token 净收益或成功率。

本报告不改变 R16 的 gate、16k配置、完整14题运行或失败统计。

## 6. 后续：当时 handoff 两个完整 wire 已精确重建

外部脚本 `reconstruct_r16_second_handoff.py` 补齐了公共 options：仅从同题 original 方法的归档输入消息解析，并以 `format_question` 逐字回构验证，没有读取标签或 response 文本。其余内容来自上述保存状态及历史输入，再使用原始 b9 的 payload、schema 和 BridgeTree adaptation 函数构造；所有网络入口被禁用。

最终 `r16_second_case_handoff_reconstructed.json` 保存两份完整 wire、源文件hash及比较收据：

| Wire | 重建 SHA256 = 已存 tokenization_wire_sha256 | 历史输入计数 |
| --- | --- | ---: |
| semantic_compose | `b88390c36422cda4e8a35110c4ec89ae1eb107729068c82c5f0ae6587d38345b` | 12,817 |
| semantic_compose_repair | `e332405f543c46d5316d8cef9be153b633c3873febbae73769ab35f97a7535b5` | 13,046 |

两项精确匹配。它们是**当时拟接纳新支持草案后的下游预测**，不是最终已存失败80源状态下的可发送重试。重建没有新计数/生成调用，因此未来可在保持这些原wire不变的条件下，对外部无损编码做独立计数比较。
