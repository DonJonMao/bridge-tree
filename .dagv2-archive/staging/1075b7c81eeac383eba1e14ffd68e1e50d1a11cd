# R19 规划协议对齐：独立对抗审查

**结论：在冻结的 RECONCILE 候选源码上，独立 42 例全部通过；未发现本次改动误拒通用单节点 retrieval 或个人 typed/deterministic 中间计划。真实草稿与累计错误只进入个人规划修复，原局部/共享预算与完整请求预检保持生效。**

## 范围与归属

- 基线与 RELEASE 提交均为 `800c51763ea3a2bfcad459b4413d41c6432db52e`。
- 独立拥有且唯一修改的代码文件：`/Users/mao/projects/dagv2-personamem-v4-reconcile/tests/test_v4_planner_contract_alignment_review.py`。
- 生产源码由 reader_v4/root 修改；本审查未改生产源码、旧测试、RELEASE、实验运行或预算配置，未 commit。
- 所有计划、回复和伪造错误均为合成数据；使用真实 Engine/Reasoner 与离线响应注入，无模型服务、远端 tokenizer、真实题目或标签/评分读取。

## 800c 基线与最终结果

先在生产源码未改动的 800c 上执行首批 8 个对抗断言，**8 个均按预期失败**：个人输出契约 3 例、单节点非法计划 3 例、compose 零父 schema 1 例、修复缺少前次实际草稿/累计错误 1 例。对应基线源码 hashes 与测试 hash 存在 `r19_planner_alignment_baseline.json`。这证明旧 schema/反馈缺口可以通过合成任务稳定复现，不依赖第 14 题正文。

完成接口协调并扩展后，最终执行：

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_planner_contract_alignment_review.py
42 passed in 1.39s
```

没有运行 full suite，也没有重复 root 已完成的 Reader 测试组。一次中间运行的嵌套原输入测试 fixture 没有把该对象送入真实初始 request，新 helper 正确拒绝；修正 fixture 使 request 与原始输入一致后，最终通过。未因该测试放宽生产校验。

## 独立覆盖及结果

| 范围 | 对抗/兼容证据 |
| --- | --- |
| schema 与本地合同 | 个人非 semantic/text/semantic 契约、单节点形状、零父 compose、非 var 终端表达式及 rule_binding 被 schema 排除；plain/json_object/json_schema 三种实际 wire 均使用同一对齐 schema。 |
| 合法计划自由度 | 通用单节点 retrieval 实际 Engine 可用；个人 number/record/set/bool/entity 中间变量无需 text marker；numeric + record + deterministic record 组合实际可用；1/3/5 个独立历史任务、非拓扑存储顺序均可规范化进入计划。变量名不必等于任务 ID。 |
| 原输入与所有权 | 构造 schema 不污染 legacy/generic schema；计划/调用输入不变；嵌套同名 planner_repair/validation_errors 仍只作为原输入数据；返回后修改 payload 或旧累计列表不污染下一次结果。 |
| 真实错误来源 | 真实 Engine 两次失败保留先后错误、failure_category、repair_index，并附最后一次实际 raw draft 与 call_index；模型自己写入的伪造错误不能进入控制器错误列表；畸形非 JSON 原文逐字保留。 |
| 旧响应与重放 | builder 拒绝创建前 last_response、脱离 requests[-1] 的复制记录、伪造 error/category、跳跃/布尔 repair_index、同一记录重复用于两次修复；下一次 Engine.plan 不继承上一次错误列表。 |
| 预算 | 默认最多 2 次本地修复；0/1/已耗尽共享 repair 预算均按实际剩余额停止；不扩大 ledger limits；共享 LLM 审计预留保持；无通过规划前的 ANN 调用。 |
| 完整请求预检 | 超长错误草稿通过实际 Reasoner 组包、计数和 preflight 路径后被拒绝，只支付已有 1 次 LLM，不预扣 JSON repair、不截断草稿、不发第二次请求。此项使用测试配置的离线计数，不声称验证远端 tokenizer。 |
| 非个人行为 | 通用 planner 两次修复仍只发送 original_input + 最近 validation_feedback；没有新增 planner_repair，也没有改变其原有修复预算。 |

## 生产静态审查

- `local_terminal.planner_contract` 的 compose 非空显式 parents 条件对应本地原守卫，后者本来就在 placeholder 展开前拒绝空 parents；因此未收窄一个原本合法的仅靠 placeholder 的 compose。
- 个人 schema 仅镜像已有固定合同。终端 ID/变量绑定、精确原始话语、依赖闭包等动态关系仍由既有 validator 判断，不能宣称 schema 已独自证明计划完整合法。
- `personal_repair_builder` 只通过 Engine 的个人分支启用。它要求当前、连续、未复用的实际 invalid planner 记录；error/category 从记录取值，原输入对照真实第一请求并冻结；累计次数受原本本地限制约束。
- 通用 `Reasoner.json` 未改；其 repair reservation、LLM 预算与序列化完整 payload 的 preflight 继续负责准入。传入历史错误没有产生新重试循环或额外预算。

## 对 root 的 Reader 小改只读复核

已阅读 `joint_reading.py` diff 与 `tests/test_v4_reader_schema_alignment.py`，未新增 Reader 测试，未重复运行其组。

1. 非空 `resolved_obligation_ids` 要求 `unresolved` 为空，精确镜像原解除义务的必要条件；省略/空列表保留保守路径。`resolved_failed_batch_ids` 没有套用该条件，因此修好格式但仍有真实语义缺口的 partial/unresolved 仍可表示。
2. frozen ID 的 `not/enum` 排除位于对应 requested variable 的 observation 分支，只从当前明确 offer 生成；同名 ID 在其他变量、普通 known routes 或未冻结的失败草稿不因此被排除。原 observation ID 类型与其他条件通过 schema 组合继续生效。
3. whole-value 失败组在原实现中先解除局部冻结，再进入对应修复；新增文字限定“当前已验证且仍冻结的行”，未覆盖这条既有显式例外。
4. `if/then/allOf/not/enum` 都是标准 JSON Schema 组合，Reader 原 schema 已使用这些关键字，未发现标准层面不兼容。未调用远端服务验证供应商结构解码子集；当前 plain 模式仍依赖本地守卫，不能把 schema 对齐当作供应商强制解码保证。

未发现本次 Reader 小改误收窄上述合法合同。其 9 例与关联 51 例通过结果由 root 提供，本独立报告只背书静态审查，不把这些计数计入我的 42 例。

## 冻结身份与限制

| 文件 | SHA256 |
| --- | --- |
| dagbt/residual_plan.py | `f146da849bbbd207f2527ee4bd2b0a20c871e316c55d6d64bf81e7717359626b` |
| dagbt/local_terminal.py | `f585a6a38dfdcdafe2dd5e458fdf333ff2f687ad2aa6bff2881cafed83c9bac4` |
| dagbt/engine.py | `1cbdd158e676eacefcbc1036c97779ff9143f67df29d0c2a775e7719c417573d` |
| dagbt/joint_reading.py | `3f049d9a01f77c518fdf14e3883e2b535fd0d379281d83927952cff862b2d344` |
| dagbt/reasoning.py（未改） | `52e1d03bc8848f66be4fb3d20928765e0df34e5317f695d1d8b3bec18b4895da` |
| tests/test_v4_planner_contract_alignment_review.py | `52a60bae5072fa2d60143d32839d254302228b4f52d3ed19c8e1d255067657a9` |
| tests/test_v4_reader_schema_alignment.py | `7a5a55f1556645d58aecf74a5845f6613f2576f9058b9780e7441fe0527da02d` |

完整回执见 `r19_planner_alignment_independent_receipt.json`。测试证明协议、预算及确定性兼容行为；不证明模型一定生成合规计划，不证明 R19 实验通过或准确率提高，也不授权部署、运行、清除义务或放宽 guard。
