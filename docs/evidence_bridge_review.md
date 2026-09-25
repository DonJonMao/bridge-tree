# Evidence BridgeTree 源码对照审查与验证记录

日期：2026-09-23。验收对象为 [实现契约](evidence_bridge_implementation.md) 的 R1-R13。审查采用源码阅读、搜索与证据模块交叉检查、正式 executor 的本地服务替身测试，以及真实 detached 进程/打包/解包演练。这里的“通过”指实现与契约一致，**不表示新版方法已经取得真实模型准确率提升**。

## 1. 逐项对照

| 要求 | 实际实现与审查结论 | 代表性验证 |
|---|---|---|
| R1 正式接入 | `dependency_experiment.py` 中 `evidence_bridge` 分支顺序执行 plan、真实初始召回、新 search、全文 map/set selection、ContextPlan 和原 reader。默认 YAML 含 dense/activation/evidence_bridge，配置严格校验且进入身份 hash。 | `test_evidence_integration.py::test_new_config_is_active_strict_and_hashed`；`test_full_runner_evidence_path_persists_live_events_and_resumes_without_calls` |
| R2 信息边界 | plan 只取 query；map/select 只取 query、可见 records、候选和冻结需求；gap 序列化原 query+需求。feasibility callback 仅回传可行性、预算数字、hash。reader 返回后才评估 gold。数据/任务身份可能包含标签 hash，未作为检索输入。 | 正式 runner 的私有 options 哨兵仅出现在 reader；`test_frozen_query_only_plan_all_candidates_and_reader_callback_does_not_leak_options`；源码检查 `clients.complete_messages` 与 `retrieve_missing` |
| R3 双预算调度 | 搜索 ANN 绝对 cap 排除 gap 预留；覆盖/中期集合预留；workspace 保留 proposal、分组和 cursor。ANN 耗尽仍执行已取工作；无可替代目标才放宽连续片限制，日志可见。 | 搜索测试 `explicit_root_coverage`、`pause_resumes`、`set_reserve`、`each_promised_coverage_root`、`fairness`；80 组不同预算/评分参数检查全局及每片不变量 |
| R4 四项与 pair | 继续复用原四项评分与题内唯一集合计费。完整 quartet 预检不足不制造 A；物理部分失败另存已成功得分。pair 在两个 singleton 后交错，不被正 singleton 关闭。缓存仍计逻辑额度，零新集合仍有测量片上限。 | `pair_is_measured_after_positive_singleton`、`atomic_quartet_budget`、`warm_persistent_scores`、`zero_new_set_measurements` |
| R5 留存与转向 | A 与 M_after 分开；正 A、正 M_after 才 retain；负目标 bounded speculation；PG 更优可 pivot，实际去掉旧 target；同一 pivot 总额度约束外部根晋升，路径及状态防循环。 | `positive_activation_with_negative_target`、`pivot_limits_and_cycle_detection`、`speculative_state_and_path_depth` |
| R6 完整归档 | P/Pe/PG/PGe 的实际完整非空集合入 bundle，不取决于 A；公开 `measured_sets_snapshot()` 保全早期物理 batch 成功值。缺项只标 incomplete。最终证据选择面对所有已发现原始候选，不仅正后继。 | `all_four_measured_sets_archive`、`mid_quartet_physical_failure`；executor 候选合并源码 |
| R7 全文与出处 | 每候选全文分片并校验首尾连续覆盖；不切掉长文本尾部。真实 source_segments 由原 message role 构建；quote 必须为实际输入子串并验证 offset。角色未知/重复引用跨角色保留歧义；推断和原话分别存。 | `complete_long_candidate`、`source_segments_preserve`、`legacy_role_markers`、`repeated_quote_across_speakers`、`mapping_contract_failures` |
| R8 可修订集合 | 整体选择不走旧 R 正边际门槛，允许删除/替换；覆盖引用须属于最终选中的记忆。多 partial 联合覆盖只允许至少两项证据的 inference。全文 ledger 超限明确失败，不 top-k 切表；reader 超限做有界整体修订。 | `feedback_maps_new_ids_and_whole_selection_removes_previous_memory`、`actual_context_budget`、`selection_cannot_cite_evidence_from_removed_memory`、`joint_partial_evidence`、`complete_ledger_over_budget` |
| R9 必要缺口反馈 | 至少一项必要需求；仅未覆盖必要需求触发 gap。ANN 与搜索共用原总计数，最多 2 次，排除已见 ID，新 ID 先映射再选择。可选项缺失不持续耗费预算。 | 集成 `gap_probes_use_same_ann_budget`；证据 `optional_gaps`、`plan_with_only_optional`、`unknown_feedback_id`、`unresolved_empty_context` |
| R10 日志与失败 | live 立即落盘、完整 evidence_live 原子快照、task_snapshot 结案重放，按 task/attempt 关联。预算/动作/target/quote/coverage/费用保全。pivot_count 仅计 queued；删除只计 accepted；当前汇总只读 authoritative outcomes。异常保留原始响应，中断终态实时刷新。 | 集成测试覆盖正常、JSON 失败、reader 失败、中断、时间元数据、修复调用计数；search 模块文件测试；operations retry-safe 汇总测试 |
| R11 回归与限制 | 正式 executor 本地端到端成功并验证续跑零调用；完整测试套件与新增模块 Ruff、compileall、diff 检查。没有远端用户模型调用或性能数字。 | 本地原始证据 `outputs/evidence_revision_validation/pytest_full.txt`；验证命令见下一节 |
| R12 后台与打包 | 独立 state/job；start/status/log/module-log/summary/stop/resume；resume 冻结 exact run、配置和部署覆盖。包包括固定数据、源码、文档与 PDF，排除凭据和运行状态。 | operations 的真实 detached monitor+临时 worker 生命周期；实际 589 题数据预检；实际 tar 解包预检与文件一致性核验（最终证据见下节） |
| R13 文档与 PDF | PDF 区分观测、实现问题、机制问题、论文原方法和本轮适配；新方法无真实模型结果。版面逐页渲染检查；本文件将每项契约映射到源码/测试，并记录限制。 | `output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf`；`docs/evidence_bridge_revision_report.md`；PDF QA 记录 |

上表的测试短名均可在对应的 [search tests](../tests/test_evidence_search.py)、[selection tests](../tests/test_evidence_selection.py)、[integration tests](../tests/test_evidence_integration.py)、[operations tests](../tests/test_evidence_bridge_operations.py) 中检索完整函数名。

## 2. 审查中发现并修正的边界

1. **首次事件不能等任务结束才落盘。** 新方法绑定运行时 observer，并逐证据事件保存完整快照；中断后补最终 stop，避免快照留在 planning_error/not_started。
2. **失败后计费不能沿用 reader 前快照。** 当前 outcome 采用最终 adapter 实际调用数，evidence 与 reader 分开；reader 报错仍计其真实一次调用，证据步骤和已选集合保留。
3. **代理动作不能冒充实际动作。** pivot 尝试/入队/拒绝分别统计；只有 accepted 集合变更计删除。新根、晋升根、pivot、speculation、retain 与恢复工作片都有准确 action。
4. **安全 allowlist 不能抹掉机制信息。** 补齐 evidence 各操作及 repair 计数、时间及来源字段、token estimate 标记与必要需求终态。搜索事件在 80 组预算场景与失败/空池场景中共检查 9,027 条，无字段或值误删；后续 action 修正另有全部类型的真实运行测试。
5. **保留多证据推断能力。** 未将“必须有单条完整 support”简化成硬限制；多条 partial 可在明确 inference 下联合支持，并检查不同证据和最终集合出处。
6. **必要性必须有实际作用。** 计划禁止全为 optional；feedback 只处理尚未覆盖的 necessary 需求，optional 缺失保留在报告而不消耗 gap。
7. **全新服务器安装前也须能查状态。** 管理入口直接加载仅依赖标准库的后台管理器，避免 package initializer 提前 import numpy/PyYAML；增加 Python `-S` 隔离 site-packages 的实际启动测试。

没有用 mock 分支替代正式方法：测试中的服务替身只替换 embedding/reranker/chat 网络端点，executor、检索、搜索、映射校验、整体选择、持久化和恢复都走实际实现。原 activation 保留旧选择行为用于复现，因此完整已测集合修复体现在新方法，不宣称所有 legacy baseline 都已改成新算法。

## 3. 可重复验证与交付证据

```bash
.venv/bin/python -m pytest -o addopts='' -q
.venv/bin/python -m ruff check src/bridgetree/evidence_*.py \
  tests/test_evidence_*.py scripts/evidence_bridge_control.py \
  scripts/package_evidence_bridge.py scripts/summarize_evidence_bridge.py
.venv/bin/python -m compileall -q src/bridgetree
git diff --check
bash scripts/package_evidence_bridge.sh
```

Ruff 针对本轮新模块与脚本；不以批量重排旧 executor 源码作为方法验收。旧配置、search/scoring、clients、PersonaMem、runner、observer、parser、运维相关回归包含于全套测试。

最终机器验证记录保存在本机 `outputs/evidence_revision_validation/` 与 `outputs/operations_validation/`。运行输出本身不进入部署包，包内保留本审查结论；文件清单与压缩包 SHA-256 在 `dist/evidence-bridge-server/package_manifest.json` 和同目录校验文件中。数据预检验证固定 revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`、589 题、3 方法/1767 任务与 0 模型调用。

实际解包预检已通过：`outputs/operations_validation/unpacked_preflight.json` 记录 589 题、1767 个待执行任务、3 种方法与 0 模型调用。`package_rehearsal_check.json` 核验文档、固定数据与 PDF 齐全，启动脚本有执行权限，凭据/缓存/旧 outputs/软链接被排除。最终包在文档冻结后重建并逐成员比对当前源码，校验结果保存为同目录 `package_final_check.json`。

PDF 共 12 页全部逐页视觉核验通过，主审另抽查第 4、9、12 页。详见 [PDF 核验记录](evidence_bridge_pdf_qa.md)，其中记录最终 PDF SHA-256。冻结后的全套测试结果为 **641 passed in 24.45s**（exit 0）；新增方法/运维模块 Ruff、compileall 和 git diff --check 全部通过。没有跳过用例或真实服务调用。

## 4. 已知限制与下一轮日志的解释

- 本次没有远端真实模型推理、准确率评估或效率实验。后台生命周期在当前 macOS 环境实际启动 detached 进程；Linux bootstrap 通过脚本测试与可移植源码/解包预检，尚未在用户 Linux 服务器执行真实服务任务。
- 本方法是受近两年论文启发的局部组合与适配。未复制 SETR 蒸馏训练，也未实现 AB/BG-MCTS 原论文完整奖励后验或理论保证；这是明示的研究设计，不声称复现原论文效果。
- 引用 exact match、角色与集合一致性可以由代码验证；“support”“历史阶段”“joint inference”语义仍由冻结 LLM 判断。日志的 covered 不能当作 gold recall、答案充分性或因果贡献。
- 原 query relevance 仍用于搜索；代表根多样性、正 M_after 或 pivot 成功入队都不保证答案收益。允许有界试探不等于遍历全部组合，参数约束与停止原因明确记录。
- LLM 输入 token 使用确定性估算，物理 tokenizer 容量不是本轮保证。全表/全文超限明确失败，没有为追求成功率暗中丢候选；embedding/reranker 既有物理超长专项继续按用户要求暂缓。
- 正常异常和可处理信号保存终态。SIGKILL/机器断电只能保留之前已落盘事件，恢复从任务边界重跑；不声称搜索 frontier 精确续算。
- 历史报告中的开发题已见；相同 reader payload 的随机差异、重复选项及解析问题限制检索收益归因。后续比较需同时读原标签结果、成功覆盖、模块动作与新增推理费用。
