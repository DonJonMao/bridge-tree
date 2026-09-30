# Evidence BridgeTree v3：修改与验证记录

日期：2026-09-30。代码实现、离线与真实服务开发验证已完成，交付核对见文末。方法设计见 [v3 方案](evidence_bridge_v3_plan.md)，操作见 [运行文档](evidence_bridge_runbook.md)，验证设计见 [验证计划](evidence_bridge_v3_validation_plan.md)。历史 v2 的 879 项通过记录不作为 v3 验证结果。

## 修改范围与依据

9 月 30 日实际 v2 导出显示：在五个此前报告的 normal 组新增错误中，四个案例的明确相关个人历史已经进入初始候选，却被 query-only 需求与 mapper 判为无关，最终没有进入 reader。包括两个 0 映射、空选集案例。painting 题的历史原因需求实际存在，mapper 仍漏掉直接支持原文。romance 题还存在可见历史与 gold 时段解释歧义，不能把所有新增错误机械归因同一种机制。

v3 默认开启：

- `raw_memory_review: true`：dense 预算可行的原始记忆有独立复核与可选资格，不依赖先有成功需求映射；由模型选择，不强制把 dense 全部原文加入最终 reader。
- `allow_unassessed_coverage: true`：选集 ID、来源可见性、reader 预算等硬约束已合法而覆盖行修复耗尽时，允许透明保留未评估覆盖状态。不能把推断改标明示、把跨需求引用改成合法支持，或伪造 `covered`。

规划/映射提示明确个性化依据；当前搜索设置、24 次 evidence 调用上限和 8192 reader 输入预算保持原配置。原文复核、覆盖未评估继续执行均属于方法行为变更，以 v3 身份运行；它们不是纯接口兼容修复。代码与正式实现文档已核对。

## 离线验证

| 检查 | 当前证据与范围 |
|---|---|
| 实际 v2 导出离线回放 | 2026-09-30：冻结旧语义状态重建 73 个 normal 任务的 v3 payload，73/73 dense 原文基线完整可见、原文/角色完全匹配、输入均在预算内。31 个旧失败的 75 次原始 select 响应重验；不生成新答案。完整记录见下文 |
| 核心语义状态、来源与调用预算 | recovery 29 项、v3 selection 23 项、正式 executor + 本地 HTTP 集成 6 项、成本 9 项、diagnostics 6 项、离线 replay fixture 3 项均通过；都包含于下述全套结果。验证原文进入真实 reader context、保守归一化、坏引用仍拒绝、服务故障不被降级吞掉、调用预留与上限、恢复/日志/汇总一致、成功 resume 不新增模型调用 |
| 运维 start/status/stop/resume | 2026-09-30：`tests/test_evidence_bridge_operations.py` 11 项通过。默认 v3 目录及显式自定义目录都实际启动 detached monitor/临时 fake worker，验证停止、续跑、日志和失败探测拦截；不调用模型 |
| 全套 pytest | `.venv/bin/python -m pytest`：981 passed in 36.97s。记录 `outputs/diagnostics/evidence_v3_full_pytest_final.log`。此前全测发现的 3 项失败已确认是旧测试未适配 bool 配置与选择调用预留，修正条件后完整重跑通过 |
| Ruff、compileall、bash -n、diff check | 21 个修改/新增 src/scripts/tests Python 文件逐条对照 HEAD：新增 Ruff 问题 0；11 个既有问题原样存在于 dependency_experiment 与 diagnostic_observability，不宣称全仓库 lint 无问题。compileall、三份运行/打包 shell 的 bash -n、git diff --check 均通过，记录 `outputs/diagnostics/evidence_v3_static_checks.json` |
| 固定数据 589 题/3 方法/1767 任务、0 模型预检 | 2026-09-30 通过：官方固定 32k / revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`，589 题，dense/activation/evidence_bridge 共 1767 任务全部 pending；`model_calls=0`、`inference_complete=false`、`optimizer_steps=0`、`weights_updated=false`。命令及 identity 见 `outputs/diagnostics/evidence_v3_preflight.json` |
| 新包成员与源码一致、无私有文件、解包预检 | 首次 v3 构包逐个核对 220 个成员，全部字节与工作区相同；无凭据/私有配置/缓存/虚拟环境/旧输出/软链接。解包后的 import 确认来自解包目录，source hash 与工作区同为 `7b08ab55da1c9ce0d000424a82ff54d48492e0ad28d62f33d074b663bb1e530f`；解包后再次数据预检为 589 题/1767 任务/0 模型调用。最终仅补齐本文验收记录后重新构包并复核成员 |

正式执行路径与回归已确认：raw-memory 复核输入含原始记忆与权威角色/观测顺序；mapped/unmapped 不被当成 relevant/irrelevant 真值；选择输入截断不会给未暴露 ID 合法引用资格；覆盖修复耗尽保留 unassessed，不能引入假的语义结论；新增请求和 token 成本进入任务日志。protocol normal 与 semantic sufficiency 仍须分开解读。

## 实际导出的离线回放结果

命令：

```bash
PYTHONPATH=src .venv/bin/python scripts/replay_evidence_v3.py --run-dir outputs/diagnostics/evidence_v2_20260930_logs/run --output-dir outputs/diagnostics/evidence_v3_replay
```

记录：`outputs/diagnostics/evidence_v3_replay/replay_report.json`。输入任务池来自本次真实 v2 导出，而非历史 9 月 22 日旧方法日志。工具在本地重新构建 payload 和运行验证器；backend 禁止调用，新增模型调用及答案均为 0。

- 73 个 normal 成功任务：全部同题 dense 预算可行原文进入 v3 的 raw review 可见集合；完整原文及权威角色逐字/逐字段相同，73 个新选择 payload 均在预算内。它证明这些候选不再因 mapper 无映射而对 selector 隐藏，**不证明真实 selector 一定选入或 reader 一定答对**。
- 31 个原终止错误、75 次原始选择/修复响应：有 18 个任务的最后记录响应现在能通过 v3 校验；其余坏引用等继续被拒。75 次响应中观察到 84 次合法覆盖行由 explicit 保守降格为 inference，可能包含同题重复修复，不能当作 84 个成功任务。
- 重放仍拒绝了跨需求引用、最终选集外引用、不可见 ID、单条 partial 冒充充分支持、空 partial、非法 kind；原服务明确截断输出仍判无效。报告只统计验证状态，不宣称 18 题在真实新运行中已恢复成功。
- 全部旧失败响应中的原全量 repair 反事实重建有 11 例超过预算，紧凑输入均在 16384 估算预算内；它们包含先前逐条审计确认的 9 个 repair 预算案例，那 9 例紧凑输入为 6907–15884 tokens。额外 2 例经过其它截断/修复路径，只能称潜在修复输入溢出，不能都当作已证明的原终止原因。输入可发送也不等于模型修复会成功。
- 所有 104 个目标任务均完成回放，无跳过任务。结果只含 ID、hash、路径和计数，不将完整源文本或部署凭据复制到新报告。

## 真实服务与实验边界

真实 planner 服务探测已通过，1 次调用、约 4.8 秒。固定的绘画课、flashcards、图书推荐三道开发题通过正式 executor 完成 dense/evidence_bridge 共 6 个任务：6 成功、0 终止失败、0 待运行，进程退出码 0。原始产物位于 `outputs/diagnostics/evidence_v3_live_smoke/formal_run`，精简记录见 [开发烟测结果](../reports/2026-09-30-dense-evidence-audit/v3_development_smoke.json)。所有选中记忆的完整原文均核对实际 serialized_context，全部 reader 在预算内且每题只调用一次；3 个 v3 的全部 dense baseline 原文均在 raw review 中完整可见，调用计数逐层一致，全部请求估算输入及总调用均在既定上限内。

| 预先固定的开发题 | dense | v3 | v3 原文条数 | reader 输入估算 tokens | evidence 调用 | 完成类型 |
|---|---|---|---:|---:|---:|---|
| 绘画课 `17273334` | 正确 | 正确 | 6 | 2477 | 13 | truncated |
| flashcards `dbbd6663` | 正确 | 错误 | 8 | 3458 | 21 | truncated_and_partially_mapped |
| 图书推荐 `40d94e80` | 正确 | 正确 | 7 | 2939 | 20 | truncated_and_partially_mapped |

三题全部关键历史均进入 v3 reader；本开发子集 dense 3/3、v3 2/3，**没有证明 v3 整体效果优于 dense**。三题的最终选中记忆本次都有映射，状态均为 mapped_only，不能将结果因果归为未映射原文通道；该通道的独立信息流由离线和正式 HTTP 集成回归验证，真实语义收益还需单独消融。覆盖最终全部通过校验，无 coverage_unassessed 实例；该降级分支已由有界恢复与正式 executor 集成测试验证，不能称已在这三题真实触发。

烟测冻结 source hash 为 `2d611cf7d4e1e100de4186e211175759428bda69a69aa8271cc464de531863cb`。运行中源码树随后调整了未评估覆盖行的省略计数、repair 日志的 schema token 估算及离线/终端汇总/打包脚本；该进程已加载的核心方法行为没有改变，烟测的冻结 source hash 不等于最终交付 source hash `7b08ab55da1c9ce0d000424a82ff54d48492e0ad28d62f33d074b663bb1e530f`，二者不能混称完全相同版本。最终树由全套测试及随后针对包脚本的 11 项运维回归验证。

已完成绘画课题：dense 与 v3 均答对。v3 保留关键原文 m00039，reader 实际收到该完整原文；选中 6 条、reader 输入估算 2477 tokens、证据调用 13 次，各层计数与 requests 数一致。首次 selection 出现两行跨需求引用，紧凑 repair 实际输入 2044 tokens，合法修复为未覆盖，而非伪造引用。覆盖类型另有 explicit→inference 保守规范化。最终为 `truncated`（ledger 输入预算省略），不是未截断 normal。部分覆盖解释仍有跨活动类比等语义不确定性，因此它证明本例的关键原文路径与恢复跑通，不能将全部 mapping/covered 当作外部验证的事实。

已完成 flashcards 题：dense 答对，v3 仍答错。v3 已将 m00036 的“表层记忆、缺少深度”原因映射为用户明示支持，并把完整 m00036 放入最终 reader；这证明原先的准入损失被纠正，**也证明恢复关键原文不足以保证本题答对**。最终选中 8 条、reader 输入估算 3458 tokens、证据调用 21 次，计数一致；29 条候选中 25 条全文映射完成，剩余 28 个 source unit 明确记为不可用，完成类型为 `truncated_and_partially_mapped`。一次无引用的 partial 覆盖错误通过 1991 tokens 的紧凑 repair 修复。没有根据这次答错增加模型重试或修改预先固定的开发题范围，后续仍须通过配对干预区分选集内容、上下文干扰和 reader 波动。

逐字核对发现这 8 条是 dense 12 条的严格子集，直接区分选项的 m00026→m00036→m00093→m00094 历史链完整、顺序相同；本次失败是证据在场仍把具体原因选错，不能继续归为 m00036 漏入。它在本次已有有效映射（`mapped_only`），因此也不能把改善仅归因于未映射原文通道。详见 [flashcards 剩余问题诊断](../reports/2026-09-30-dense-evidence-audit/v3_flashcards_remaining_issue.md)。本轮不临时改变相同 reader 的契约来追求开发题命中。

图书推荐题已正确保留 m00003/m00031 的阅读口味，33 条候选中 28 条全文映射完成，剩余 43 个 unit 记为不可用。一次 mapping schema 错误经有限恢复处理；最终选择通过，2 行 explicit 声明被保守降为 inference。没有因为历史未直接提供完整推荐书单而再次形成空选集。

本次开发题使用单独目录，保留题号/方法/调用与失败、完整模型请求响应和 reader 原始上下文。实际开发子集不混入全量运行统计，也未因答错临时增加重试额度。已审计七题属于开发材料，不作为未见确认集。完整 589 题新运行的结果仍需配对分析以及成本、未评估覆盖、空上下文等分层检查。

本次开发 run 仅执行 dense 与 evidence_bridge，后者没有 activation 先行评分产生的暖缓存；因此跨 v2/v3 的速度结论还需要统一方法顺序、缓存与服务负载后测量。调用数、实际请求与输入 token 估算单独保留，耗时不能直接换算成货币费用。

## 版本与交付隔离

- 当前默认状态目录：`outputs/background-evidence-bridge-v3`。
- 当前默认运行根目录：`outputs/evidence-bridge-v3`。
- 当前默认缓存：`outputs/cache-evidence-bridge-v3`。
- 新包目标：`dist/evidence-bridge-v3-server/bridge-tree-evidence-v3.tar.gz`，附 `.sha256` 与 `package_manifest.json`；源文件和解包预检已完成，文档定稿后再更新最终校验值。
- v1/v2 已分发压缩包与校验值保留，不覆盖；旧服务器项目与输出保留。v3 必须新 run，不能 resume 已冻结的 v2。
- JOB 仍为 `evidence_bridge`，管理命令不变：`bash scripts/run_evidence_bridge.sh {status|log|summary|export|stop|resume}`。
- 旧 PDF 仅作 v1 机制背景，v3 当前行为由本轮方案、实现契约及运行文档规定，不重写历史实验结论。

Git 最终提交与远端推送验证：待填写。服务器操作步骤不会冒充已替用户停止/启动了远程进程。
