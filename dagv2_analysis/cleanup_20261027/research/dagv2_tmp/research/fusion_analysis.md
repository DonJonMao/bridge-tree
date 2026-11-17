# 新版 DAG+BT 源码与实验证据核对

核对日期：2026-10-01。核对范围为当前工作树 `dagbt/`、冻结 `vendor/bridgetree/` 的入口、融合文档和 `outputs/` 产物。本次只读分析，没有修改产品代码、调用模型或读取凭据。

## 可以成立的结论

新版是 `dagbt_fusion_reliability_v3`，并非只给老版加一个 BT 检索器。它同时更改候选发现、证据映射、节点可执行条件、来源闭包、审计、reader 中间链输入、选择复核、模型/向量与 PersonaMem 问题协议。把旧 `results/` 分数与任何新版服务器观察直接相减，不能归因于单个机制。

本地 **没有新版真实基准准确率汇总**。对当前 `outputs/` 的文件枚举发现 100 份 `summary.json`，全部位于 `outputs/verification/`；没有非验证目录的 summary。`outputs/hotpotqa/`、`outputs/2wikimultihopqa/`、`outputs/musique/` 为空。验证树有受控脚本模型、pytest 样本、历史解包副本，不能当成新版真实 F1/EM。用户关于“新版效果一般”的观察可作为研究动机，但目前工作树不能提供其具体低分或下降幅度。

旧分数是仓库的历史汇总报告，三套各 1000 题、Qwen3.8-27B-AWQ-INT4 + NV-Embed-v2。当前三套 `outputs/` 没有对应逐题结果，因此这里引用的是“仓库历史报告值”，没有重新评分验证：HotpotQA F1/EM=79.83/67.00；2Wiki=80.34/72.90；MuSiQue=64.66/54.50。参见 `results/METHOD_CARD.md:14–20`。

## 源码中的新版实际流程

1. `dagbt/engine.py:80–90` 仍以 q-only planner 生成初始步骤；将所有 sinks 作为必要终端、`terminal_mode=all`，冻结 requirements hash。初始最多 6 节点、细化最多 2，`dagbt/config.py:13–14`。
2. `engine.py:431–456` 在 v3 selection review 开启时先用原问题做一次 dense 检索；按完整 reader 可行性逐条构造 baseline，进入正常候选池并计 ANN。同池实验从固定列表构造 baseline。
3. `engine.py:117–125` 只有状态为 supported 的 planned parents 可接地；非 supported 父项阻塞下游。`engine.py:279–309` 执行搜索、映射、节点求解和必要时细化。
4. `dagbt/bridge.py:228–234,275–287`：BT 集合评分始终面向原始总问题，grounded 子问题仅改变候选发现。`bridge.py:303–307` 按剩余节点做 ANN 与 set-score 的 floor share，保留 gap 额度；`bridge.py:360–385` 实际使用完整冻结 `EvidenceBridgeSearcher` 或明确的 proxy-free 路线。`bridge.py:398–416` 保留全部实际 proposal batch 的候选并集。
5. `dagbt/evidence_mapping.py:74–94` 对发现全文建立至多 400 字符来源片段，每个 source/unit 使用 ID。`evidence_mapping.py:302–359` 在共享 LLM 配额和选择修复预留下分批映射；预算未完成不是无关证据。
6. `engine.py:182–250` resolver 给 answer、status、source/guard spans、actual used parents 与版本。`dagbt/support.py:125–132,181–185` 的 OR 是 **相同答案、相同适用 scope 的两套支持路线**，不保留两个竞争实体/答案假设。结构合格仍不证明语义蕴涵，`support.py:239`。
7. `engine.py:311–360` 独立条件/冲突审计；`engine.py:480–492` 受影响且可执行节点回查/重求解、再次审计。`support.py:244–278` 用父状态、版本、争议和失效状态计算 eligible。
8. `support.py:486–493,576–585` 枚举当前有限图的 AND/OR 支持，优先必要终端覆盖，其次可选终端，再少原文 token。没有终末答案概率或边际效用学习。完整枚举针对已发现、已编译图，不是召回最优或语义正确性证明，`support.py:618–626`。
9. v3 `engine.py:389–426` 将 DAG 闭包作为 proposal，随后交给 `FinalSelector`。`dagbt/final_selection.py:85–135` **先装完整 baseline 原文，再装映射 ledger/支持路线**。raw channel 仅包含 `baseline_ids`；新 BT 候选若零映射且不在 baseline，可能没有独立 raw 可见机会。选择器只能选 raw/ledger 中实际可见 ID，`final_selection.py:137–154`。
10. `final_selection.py:160–191` 检查 coverage 引用同节点、所选文档与完整支持路线。合法 header 固定后只有 coverage 修复，`final_selection.py:296–357`；默认耗尽恢复后可保留 `unassessed`，不形成 covered 证书。`final_selection.py:363–370` 对 5/10/20 实际选集重新计算证书。
11. `engine.py:362–379` 默认 raw-only reader；可选 `fusion_chain` 只注入实际选集内 eligible 闭包和精确 spans。`engine.py:381–387` 用实际模板加输出预留检查预算。`engine.py:497–523` 记录最终 reader 原文、结果与语义判断限制。

## 已经实现，不能作为从老版起步的新贡献

| 泛化的创新说法 | 当前新版已实现的对应物 | 更有空间的增量 |
|---|---|---|
| DAG+检索树/多跳桥接 | 原生 BT 多根、pair、pivot、speculation；`bridge.py:377–385` | 学习目标条件的桥接价值；以终末收益校准导航 |
| 证据条件接地、反证与回滚 | supported grounding、guard、冲突局部失效及重求解；`engine.py:117,311,480` | 多个竞争父实体保留、下游证据反向约束上游假设 |
| AND/OR 来源闭包 | actual parents、两种同结论路线、完整闭包枚举；`support.py:125,486` | OR 从“支持备选”升级为“答案假设备选”，分支一致性与预算剪枝 |
| 引文可追溯、证明证书 | 原文 ID/hash/offset、角色、版本、可见完整路线；`evidence_spans.py`、`support.py`、`evidence_views.py` | 独立语义验证器与可校准风险；当前 structural certificate 不证明 entailment |
| 动态计划 | 原文触发至多 2 个 refinement；`engine.py:252–275` | 问题语义约束下删掉伪需求、改错依赖、重新选择 terminal；需防漂移且独立验题 |
| 自适应检索/缺口反馈 | 两轮 unresolved 节点反馈、2 次 gap ANN、floor share；`engine.py:463–479`、`bridge.py:303–307` | 终末敏感度/不确定性估计后的预算分配与最优停止 |
| 原文兜底/整组选择复核 | dense baseline raw channel 与模型 whole-set review；`final_selection.py:85–135` | 选择 view 的信息价值调度，非 baseline 零映射候选进入原文机会 |
| 给 reader 带证据链 | 新版已有 `fusion_chain`、仅完整所选证据路线；`engine.py:366–378` | 测试链提示何时锚定错误答案、去实体的链结构、校准的链暴露门控 |
| 关闭相关性代理 | `fusion_proxy_free` 已提供需求轮转/ANN条件桥接；`docs/PROXY_FREE_CONTROL.md:8–32` | 不可把其效果声称为仅公式 A 的因果作用；需要细分调度机制实验 |

## 新旧比较的主要混杂因素

| 因素 | 老版历史方法 | 当前融合 v3 | 需要的控制 |
|---|---|---|---|
| 生成与 embedding | Qwen3.8-27B-AWQ-INT4/NV-Embed-v2；`results/METHOD_CARD.md:14` | DeepSeek-V4-Flash/Qwen3-Embedding-8B；`FUSION_README.md:37–39` | 同题两方法先用同模型、同向量。当前 paired original 不是历史旧模型成绩 |
| reranker | 没有 | Qwen3-Reranker-8B、真实集合评分 | 总 token/时延/请求匹配；等 ANN 不能代表等成本 |
| 节点判断 | 非空答案+勾来源为 resolved，自动带 planned parents | mapping→resolver→audit，actual support parents、多状态 | old+轻量checker 对照；验证语义门槛是否损失下游可执行率 |
| 候选宽度 | 原问题+未接地节点 top50 archive，接地节点全语料 top50，panel20 | 默认 initial_width12/proposal_width4，共36ANN、512set | 比发现 recall 与选择 recall；冻结候选池隔离选择效用 |
| reader | 所有 resolved 节点链，即使某来源未留在top20 | 默认纯原文；chain为独立消融 | raw / 全链 / 选集内证据链共享相同文档和模板预算 |
| 输入额度 | 旧真实 tokenizer；节点512、reader1024，旧检查未留输出 | context16384、证据output4096、margin256与估算；reader留1024 | 同tokenizer、同actual rendered输入；报告API usage |
| PersonaMem | original 当前保留问题+公开选项 | fusion 节点阶段 query-only、reader另接选项 | v3融合消融共享query-only；不要把选项协议差解释成BT效用 |
| 可靠性与缺失 | 旧摘要无当前真实逐题产物 | 修复/服务故障/未映射/可见裁剪 | 全任务失败计零与共同成功分开；报告全部尝试成本 |

文档已主动披露这些限制：`FUSION_README.md:43,66–77`、`docs/MODEL_ALIGNMENT.md:19–32`、`docs/FIDELITY_AUDIT.md:61–73`。`dagbt/runner.py:1141–1173` 确实输出 all-task、common-success、rescue/harm，因此后续拿到服务器日志后应复用这些权威统计。

## 可验证的退化机制假说（还不是实测归因）

1. **链收益被同时移除。** 旧卡记录终末解析后 87–99% 最终答案照抄链尾，2Wiki 99.4%，直出消融 F1=71.82/78.70/57.97（`results/METHOD_CARD.md:43–49`）。raw-only 默认删除了旧系统的主要答案通道。优先做同文档 raw/链/链校准控制，避免把这部分当成检索树退化。
2. **语义门槛产生级联停机。** `grounded` 要所有 planned parents supported，`engine.py:118–119`。映射/审计稍过保守可阻断下游，即使正确原文已发现。区分“父结论真的错”“检查漏判”“预算未看证据”“错误planned edge”。
3. **中间桥接对总问题低相关。** `_score_backend` 固定 original question，`bridge.py:278–286`；桥文可能只回答子目标，原总问 reranker 分数不足。测试以终末必要性/条件支持估计导航价值，不能把 reranker score 当因果效用。
4. **固定公平额度不等于价值最优。** `bridge.py:303–307`、`evidence_mapping.py:307–309` 分配仅依赖 remaining_nodes，忽略节点是关键瓶颈还是冗余分支。多跳长链/多文档会消耗 mapping 调用，让后节点预算不足。
5. **v3 原文优先挤出支持路线。** `final_selection.py:113–121` 先贪心装 baseline raw，再装 ledger；源证据完整路线原子留存是正确工程约束，但可见率与关键证据优先级仍需研究。不是所有 BT 零映射新候选都能获得 raw 复核。
6. **合法 DAG 未必语义对。** sinks 全部必要且 frozen，`engine.py:84–88`；细化只加节点，`engine.py:265–274`。planner 过拆解或误设必要子目标，后续即使结构证书完整也可能在解另一个问题。

## 推荐从老版起步的三项方法贡献

**第一项：证据条件的多假设父实体与逆向约束。** 对少数高歧义节点保留 K=2 的不同实体/答案及独立出处，子目标并行检索，发现不同下游证据后更新整条路径。与已有同结论 OR 明确区分：当前 `compile_graph` 会拒绝 alternative_conclusion_mismatch。保持老版全语料节点检索，避免全面引入新映射器；为假设设置明确预算、父版本和再接地成本。关键实验为错误父实体修复率、下游可达率、EM/F1与额外token；对照单假设、同结论OR、仅self-consistency。该贡献需要对近期 tree/search RAG 文献进一步查重。

**第二项：终末效用驱动的稀疏验证与预算。** 给老版保留廉价快速路径，只在影响终末答案的高风险节点、失败的子问题或相互矛盾来源上做验证/追加检索。预算由终末敏感度和可测的节点风险分配，而非平均fair share。至少设计等总成本对照：固定预算、按深度、按不确定性、按终末敏感度；报告成本—F1前沿，避免用更贵方法冒充更好策略。新版只做floor share、guard audit和token最小闭包，未实现终末效用学习。

**第三项：链暴露的证据校准。** 老版保留节点链有明确历史效益；建立“只给所选全文能支持的链”“不给终末实体只给关系骨架”“争议/低置信节点不暴露答案”三个门控，训练或校准 reader 何时服从链、何时回到原文。新版已有证据链工程，贡献不能写成首次 chain+spans，必须是可度量的答案锚定效应与门控策略。冻结同候选池/同原文选集，只变链暴露，量化 reader 背叛正确链、复制错误链、反事实替换敏感度和EM/F1；特例终末直接输出是必要基线。

结构修复与独立语义验证可作为第二阶段：对原问题语义条件做独立检查，允许删错需求/改依赖而不改用户问题；验证器与生成器使用不同模型/证据遮蔽以估计相关错误。简单“再叫同一LLM审一遍”已接近现有 audit，不能成为强新颖性声称。

## 真实产物与验证边界

- `outputs/verification/reliability_v3/live_smoke/smoke_report.json` 的真实服务虚构小样本：`status=failed`、`error_type=ServiceError`，首个 `map/2` 超时；模型字段为 DeepSeek-V4-Flash/Qwen3-Embedding-8B/Qwen3-Reranker-8B。4个人工记忆、不读公共数据或gold；ANN8/set32/feedback0，非默认全量。reader 未执行，不能据此判断reader选项泄露或准确率。
- `outputs/diagnostics/bt_v3_raw_view_replay_final_20260930/replay_report.json`：源独立BT的73个normal任务，10个零映射案例回放；baseline120条，raw可见91条，完整raw/metadata一致，全部payload在本地预算内；全部baseline可见案例0个；新model_calls=0、new_answers=0。证明的是来源可见性，不是新选择、DAG检索或答案提升。
- `docs/FUSION_RELIABILITY_V3.md:82–97` 记录 planner 探测通过与 Engine smoke 失败；`docs/FUSION_RELIABILITY_V3.md:109–119` 记录529项本地回归通过且最终树之后没有再调用真实服务。测试可靠性不能代替准确率。

后续最低实验顺序：先收集新版服务器同题权威结果与全部attempt成本；在同模型/同向量上复现old paired original；在冻结候选与选集上隔离reader链因素；再分别加入多假设、稀疏验证、终末预算，最终做交互与完整消融。不能在没有这些数据时断言BT造成下降，或许诺某建议会提高若干百分点。
