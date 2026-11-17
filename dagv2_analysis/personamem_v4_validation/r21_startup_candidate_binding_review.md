# e667 / R21 启动准备绑定：只读独立复核

首轮结论：**源码、Full26、计划中的固定 14 题/config/budget/output 主绑定一致，没有已推广、模型已通过或正式包已存在的虚假声明。发现三处历史 metadata 未同步，以及一处启动命令缺项；它们不构成算法/配置漂移，但应在把文件作为当前执行清单前纠正。**

范围仅外部 `validation_candidate.json`、`modeling_checklist.json`、`requirement_audit_candidate.md`、`release_commands.md`，及 RECONCILE e667 与 Full26 receipt/log 的绑定。未读 labels/scores、未修改这些输入或源码、未运行/重复测试、未调用模型/tokenizer、未推广或打包。R20 运行状态采用被审文件中的时间点记录，不把本审查冒充新的 live 检查。

## 已确认的主绑定

- RECONCILE HEAD `e6677081cdfb33c01db3aaa274a497168f314f78`，tree `b332badbd2bbe8a97ad3a6e1ca8729a46308342c`，clean。
- 两份 JSON 当前主 `source_commit/source_root` 一致指向 e667 / RECONCILE；`release_ready=false`。当前 model_smoke/candidate_model_smoke 对象完全相同：R21、not_started、passed=false、live_writer=false、14 题、`configs/personamem-v4.json`、labels_used_for_selection=false、accuracy_conclusion_established=false。
- `offline_tests` 两份 JSON 一致：2381 passed、69 warnings、71.18s、exit=0、319 source files。Full26 日志最终行及实际 SHA 与 candidate/receipt 均相符；receipt source_before/source_after 相等，319 个路径集合与 e667 完整树相等。
- 本次按 `runner.frozen_sources` 静态等价规则独立枚举 **105 项 runtime sources**；逐项 SHA 与 candidate 及 Full26 before map 完全相符。未重复读取 319 项中的标签/结果内容，也未把该子集核对夸大为独立重做 root 的全提交 blob 审计。
- 38 个 checklist items 都绑定 e667/Full26，状态统一为 offline_regression_passed_real_model_gate_pending；其 regression 路径都存在于当前提交。requirement audit 的 38 项和主状态一致。
- `runtime_matches_release=false` 正确表达尚未推广。当前不可拿此 candidate 直接做最终 source approval；推广及真实 gate 后需由 root 按实际事实更新并再核查。

## 固定题组、预算与未来路径

| 项目 | 核查结果 |
| --- | --- |
| 题组 | `configs/personamem-v4-smoke-ids.json` 中 PersonaMem 14 个唯一 ID；文件 SHA 与 Full26 receipt 一致。未来 smoke wrapper 固定使用该文件，不传 limit 或失败重试。 |
| 方法 | wrapper 使用固定 `original` 与 `dagbt_residual_memory_v2` 两 arm；没有新方法名或替代 baseline。 |
| config | `configs/personamem-v4.json` SHA `6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05`，与 candidate 和 Full26 一致。 |
| 调用预算 | ANN 36、LLM 24、reader 0、set_score 0、JSON repairs 6、每请求 repairs 2。 |
| 容量 | context 16384、input_margin 256；既有默认 reasoning_output_tokens 4096、reserved_audit_calls 1 未改。 |
| 超时/重试 | question_timeout 3600s、worker_startup 300s、max_question_attempts 1；未来命令无覆盖预算。 |
| output | 两份 JSON 与命令变量均为 `outputs/v4_validation_r21`，不复用 R20。此审查未探测未来 RELEASE output 目录是否已存在；仍须由实际启动前检查确认新目录。 |
| 正式包 | release_commands 的 tar 只是 future parameter，并明确尚未 build/install；未称该路径已有可交付正式包。 |

固定 IDs 文件 SHA：`bd572f41ee8a61436a71db5187b95f87d742a5f37d28b763aa417ffc92e36da0`。未改变题组、读 gold 或按结果筛题。

## 首轮发现（保留，不覆盖历史）

1. **checklist 当前限制栏残留旧版本。** `current_evidence_limits[0]` 和 `limits[0]` 仍写“2194 / all315 / isolated 6c04637”，与当前 source_commit=e667、Full26=2381/319 不一致。旧事实可进入历史字段，当前栏应描述 e667，且继续保留模型/正式包未通过的限制。
2. **latest_model_evidence 不是已有最新 checkpoint。** 该字段仍是 R20 首题快照（1 个 original ok、1 个 residual unresolved）；同文件 live_release_model_smoke/previous_model_smoke 已更新为第 9 题 checkpoint。passed 仍为 false，没有虚报模型成功，但“latest”命名产生歧义，应统一当前快照或明确旧对象为历史。root 后续 live 状态继续推进，不要求把本文时间点当最新。
3. **两份 JSON 中 selector 的 next_review 残留旧授权状态。** `isolated_tested_selector_revision.next_review` 仍写 “no schema patch authorized yet”，而同文件 completed_frozen_schema_revision 已记录授权后的 e667 完成。可保留为 selector 当时的历史记录并明确历史属性，或更新为已由 e667 完成；不能让其看起来仍是当前授权结论。
4. **release_commands 缺具体 R21 smoke/check 行。** 当前只设置未来参数并以文字要求先推广、核源码/config/data、检查新 output；随后的执行块从 source approval 开始。参数正确，但还不是完整的可复制启动清单。应在明确 R20 自然结束并保留失败 gate、再完成推广和绑定的条件下，列出 wrapper `smoke` 与之后 `check`，均显式使用同一 config 和 R21 output；不能提前执行，也不能用 check 取代实际完成状态。

root 已收到以上发现并表示将更新外部文件；本初版不修改输入、不预判改动结果。后续只对实际修订做增量复核。

## 本轮证据文件身份

| 文件 | SHA-256 |
| --- | --- |
| validation_candidate.json | `0cc9a509e88ba894ac237f419a5207e9e43147b252faf4aad2f56090cec5ecd1` |
| modeling_checklist.json | `5b262d7e7081d89bfa70a8c365717ea76e97d5d9e4dffac8702aa9734ba4f308` |
| requirement_audit_candidate.md | `cbf5d4068c1c0686cc81e3be6dd4bbeb64da638fd1b72ec840ad015010023fba` |
| release_commands.md | `482a50a01fdbdece4cd482e6b8893ef10e05c565c5f6b4774824b195e4299461` |
| Full26 receipt | `edd7c4934a47210fe8f2f033670555d0c9406da314ae149d046ee777e865f2ab` |
| Full26 log | `4fed28a000d689c880bb8efa283f7085d47385a923f370849b82866662660c42` |

R20 自然收尾后的实际 failed gate、e667 推广、R21 fresh run、严格模型通过、源码审批、准确 tar 安装及清理仍是后续独立步骤。本报告只确认准备材料的一致性边界，不授予任何后续 gate 的通过状态。

## root 修订后的增量复核

已实际重读 root 修改后的两个 JSON 和 release_commands，并与 `before_r21_consistency_*` 备份比较。两份备份的 SHA 与上表首轮输入精确相同；首版报告 SHA 为 `684f7f3a3b86ab235d6c8efeeb19c7fb7c9ef64f16653a3b1013caf391ae6b3c`。首轮发现完整保留于上文，不因问题已修复而抹除。

四项发现现均已处理：

1. 当前限制栏改为 e667 / 2381 / 319，明确 R21 尚未开始、模型行为未验证，保留实际 token 选择/F/R 补丁不能保证 semantic 恢复的限制。
2. 五份当前 R20 snapshot 对象现在完全相同，指向 `r20_root_metadata_consistency_checkpoint.json`：source=6c、running_with_failures、passed=false；原始时间点为 original 11 ok，residual 6 ok + 4 unresolved，第 11 题 residual 正在生成。此处只是检查文件间一致，未额外探测 live 进程。
3. 两份 selector 对象的旧字段已改名 `historical_next_review_at_e02`；不再把当时尚未授权 schema patch 的记录当当前结论。
4. 命令文档已增加 R20 收尾后的 status/check，并明确先保留其失败 gate 再推广；随后条件化列出 R21 smoke/status、等待全部 14 题自然结束、再 check。三个新 R21 操作均指向同一绝对 RELEASE/R21 output，smoke/check 显式使用同一绝对 config；没有 limit、budget override、retry 或提前 build。文档明确这些是分步条件操作，不能一键顺序执行所有 gate。

修订前后 candidate 的 source_commit/source_root/source_hashes/config_sha256/offline_tests/model_smoke/release_ready 完全未变；checklist 的源码、38 items、offline tests、candidate smoke 与 release flag 完全未变。RECONCILE 再核仍 e667 clean，joint SHA 仍 `263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`。

修订后文件身份：

| 文件 | SHA-256 |
| --- | --- |
| validation_candidate.json | `7ecbcb2798e4b1dfb140e583b0c4ea60b4831a8bbe86ce775d19ac9d8f513ccb` |
| modeling_checklist.json | `b5928f8b77f1b3bd2dd6e8c0d31da2d52ffd7b0e03cf930a348b8143e6899c66` |
| requirement_audit_candidate.md（未改） | `cbf5d4068c1c0686cc81e3be6dd4bbeb64da638fd1b72ec840ad015010023fba` |
| release_commands.md | `cd178ad46b520c6538d2537dac3fef7cee060d7f822a7081ba9d6be618a7246b` |

**增量复核无剩余准备材料一致性阻塞。** 这不表示现在可立即启动：必须先满足文档中的 R20 自然收尾、实际失败 gate 保留、独立推广绑定与新 output 不存在等条件。后续推广后要按真实事实更新 runtime_matches_release 与运行状态，不能以本报告替代实时核对、模型 gate 或发布审批。
