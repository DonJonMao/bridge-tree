# DAGBT 清理：实验结果与诊断保留清单

日期：2026-10-27。只读扫描全部13个 `dagv2*` 代码/部署目录；`dagv2_analysis`、`output`仅作现存保留副本的只读参照。本任务未移动、删除或修改原文件，也未运行实验。路径记录为清理前快照；父任务后续移动应以其迁移manifest补充新位置。

## 可以据此执行的保留边界

- 保留三个当前代码目录：`dagv2-personamem-v4`、`dagv2-prefeval-v4-fix3`、`dagv2-webwalker-v4`，其中已有outputs/results原样保留。
- 旧目录所有`outputs/`、`results/`应先连同目录结构迁出；不要只保留scores/summary，原始requests、ledger、events、失败快照、preflight、manifest均属结果证据。
- `dagv2/scripts/`四个实验tar.gz先全部保留；其中两个包含尚未找到等价保留副本的真实结果。另两个已证明结果内容有副本，是否删整包还取决于配置和原路径映射是否一并保留。
- `dagv2/tmp/results_analysis_20261008/`有5份独特分析文件；为避免丢研究说明，建议保守保留整个`dagv2/tmp/`（约173 MB），不把其文献缓存当效果实验。
- 部署目录内validation、current_validation、validation_evidence、real_smoke、local_repair各候选轨迹和root reports应独立保存。可以去重重复payload，但不要连同部署目录整体丢弃。

扫描共得到 **17,961个候选文件**，含20份归档；对文件和1,463个归档内结果/报告成员计算SHA256。对PersonaMem历史890个gzip raw rows额外验证了解压后payload hash。完整逐文件清单见`results_inventory.json`，保留操作输入见`results_preserve_manifest.json`。

## 所有 outputs / results 目录（清理前路径）

| 路径 | 文件数 | 大小 | 动作 |
|---|---:|---:|---|
| `dagv2/outputs/` | 9876 | 5351.811 MB | 完整迁移保留 |
| `dagv2/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-personamem-a48/outputs/` | 5 | 0.049 MB | 完整迁移保留 |
| `dagv2-personamem-a48/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-personamem-v4/outputs/` | 4684 | 2661.597 MB | 原地保留 |
| `dagv2-personamem-v4/results/` | 4 | 0.004 MB | 原地保留 |
| `dagv2-personamem-v4-reconcile/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-prefeval-v4/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-prefeval-v4-fix/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-prefeval-v4-fix2/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-prefeval-v4-fix3/results/` | 4 | 0.004 MB | 原地保留 |
| `dagv2-residual-f4/outputs/` | 25 | 0.788 MB | 完整迁移保留 |
| `dagv2-residual-f4/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-support-review/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-webwalker/results/` | 4 | 0.004 MB | 完整迁移保留 |
| `dagv2-webwalker-v4/outputs/` | 1 | 0.000 MB | 原地保留 |
| `dagv2-webwalker-v4/results/` | 4 | 0.004 MB | 原地保留 |

`results/`每套只有4份Markdown；其12个目录副本均可按SHA256映射到保留版相同文件。它们是旧Qwen/NV结果与METHOD_CARD，不能因结果旧就丢失，也不能因文件名相同就跳过hash检查。

## dagv2/scripts 四个实验归档

| 归档 | 压缩大小 | 结果成员数 | 结果payload大小 | 与受保护/保留区覆盖 |
|---|---:|---:|---:|---|
| `personamem_v3_1_diagnostics.tar.gz` | 924.140 MB | 892 | 11324.262 MB | 全部覆盖；890条通过gzip解压payload比对 |
| `dagv2_a48_v2_smoke_debug.tar.gz` | 150.719 MB | 258 | 705.349 MB | 全部覆盖；0条通过gzip解压payload比对 |
| `dagv2_a48_v3_smoke_debug.tar.gz` | 46.580 MB | 123 | 449.813 MB | 4份未找到保留区同hash副本 |
| `dagv2_results_20261008_025515.tar.gz` | 0.398 MB | 8 | 1.330 MB | 7份未找到保留区同hash副本 |

- `personamem_v3_1_diagnostics.tar.gz`：892成员全部属于结果；890条raw JSON分别与`dagv2_analysis/personamem_v3_1_full_20261013/compressed_rows/.../*.json.gz`的解压内容完全相同，manifest/progress也有保留副本。可做内容去重；不是整个tar.gz与gzip文件字节相同。
- `dagv2_a48_v2_smoke_debug.tar.gz`：258个结果成员均在`dagv2_analysis`找到逐字节副本，另有1个config成员未作为结果统计。整包去除前需保留该配置与原路径manifest。
- `dagv2_a48_v3_smoke_debug.tar.gz`：123个结果成员中有4份scores/summary尚未在保留区发现同hash；必须保留这些版本。
- `dagv2_results_20261008_025515.tar.gz`：8个结果/报告成员中7份尚未在保留区发现同hash，含answers与run事件；必须保留。

未覆盖成员逐项如下：

| 归档 | 必须保留成员 | 大小 |
|---|---|---:|
| `dagv2_a48_v3_smoke_debug.tar.gz` | `personamem_a48_v3_smoke/personamem/dagbt_residual_memory_v1/scores.json` | 14,085 B |
| `dagv2_a48_v3_smoke_debug.tar.gz` | `personamem_a48_v3_smoke/personamem/original/scores.json` | 15,885 B |
| `dagv2_a48_v3_smoke_debug.tar.gz` | `personamem_a48_v3_smoke/personamem/summary.json` | 62,776 B |
| `dagv2_a48_v3_smoke_debug.tar.gz` | `personamem_a48_v3_smoke/summary.json` | 66,676 B |
| `dagv2_results_20261008_025515.tar.gz` | `run/manifest.json` | 148,052 B |
| `dagv2_results_20261008_025515.tar.gz` | `answers.jsonl` | 865,838 B |
| `dagv2_results_20261008_025515.tar.gz` | `run/progress.json` | 208 B |
| `dagv2_results_20261008_025515.tar.gz` | `run/pid.json` | 544 B |
| `dagv2_results_20261008_025515.tar.gz` | `run/events.jsonl` | 262,135 B |
| `dagv2_results_20261008_025515.tar.gz` | `run/launcher.log` | 40,960 B |
| `dagv2_results_20261008_025515.tar.gz` | `report.json` | 3,291 B |

## 部署包中结果/身份材料

15份部署tar.gz的原始包hash均单独记录。已识别结果成员大多有包外相同副本，但这些副本往往仍在待清理的`dagv2_deploy`自身，尚不能当作已迁入受保护保留区。删除包内重复payload前必须保存对应外部validation/docs/manifest。

以下两项只在归档内发现，必须额外取出或保留原包：

| 归档 | 成员 | SHA256 |
|---|---|---|
| `dagv2_deploy/20261014_webwalker_v4_experiment/dagbt_webwalker_v4_experiment.tar.gz` | `dagbt_webwalker_v4_experiment/bundle_manifest.json` | `b6d3e820da7d9aa50c6d47d20a3a4dca4f4844c813bcc637930f3d07a29f9c53` |
| `dagv2_deploy/20261014_personamem_v4_experiment/dagv2_personamem_v4_experiment.tar.gz` | `dagv2/DEPLOYMENT.json` | `bc36a19ff11fc316f1cfb7a26daa0f8960f041b79659e02a3c02e284fb6b77d9` |

全部部署归档的结果覆盖表：

| 归档 | 结果/报告成员 | 尚无包外文件同hash的成员 | 尚未在受保护区/三个保留代码区覆盖 |
|---|---:|---:|---:|
| `dagv2_deploy/20261015_webwalker_v4_access_v4_experiment/release/dagbt_webwalker_v4_access_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261021_prefeval_v4_fix1_experiment/dagv2_prefeval_v4_fix1.tar.gz` | 46 | 0 | 2 |
| `dagv2_deploy/20261014_personamem_v4_experiment/dagv2_personamem_v4_experiment.tar.gz` | 44 | 1 | 3 |
| `dagv2_deploy/20261016_webwalker_v4_access_v13_experiment/candidate/dagbt_webwalker_v4_access_v13_experiment.tar.gz` | 3 | 0 | 1 |
| `dagv2_deploy/20261016_webwalker_v4_access_v13_experiment/release/dagbt_webwalker_v4_access_v13_experiment.tar.gz` | 4 | 0 | 2 |
| `dagv2_deploy/20261020_prefeval_v4_experiment/dagv2_prefeval_v4_experiment.tar.gz` | 46 | 0 | 5 |
| `dagv2_deploy/20261014_webwalker_v4_experiment/dagbt_webwalker_v4_experiment.tar.gz` | 4 | 1 | 4 |
| `dagv2_deploy/20261015_webwalker_v4_access_v3_experiment/release/dagbt_webwalker_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261015_webwalker_v4_access_experiment/dagbt_webwalker_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261015_webwalker_v4_access_experiment/stopped_gate_release/dagbt_webwalker_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261016_dual_benchmark_v4/release_v2/dagbt_benchmarks_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261016_dual_benchmark_v4/release_v3/dagbt_benchmarks_v4_experiment.tar.gz` | 4 | 0 | 2 |
| `dagv2_deploy/20261016_dual_benchmark_v4/release/dagbt_benchmarks_v4_experiment.tar.gz` | 4 | 0 | 4 |
| `dagv2_deploy/20261016_dual_benchmark_v4/release_webwalker_v2/dagbt_webwalker_v4_v2_experiment.tar.gz` | 3 | 0 | 3 |
| `dagv2_deploy/20261015_webwalker_v4_access_v2_experiment/release/dagbt_webwalker_v4_experiment.tar.gz` | 4 | 0 | 4 |

大型dual_benchmark三个约2.126 GB归档主要携带dataset/payload；不能将其体积误当新增实验结果。各版validation/README可能不同，不是整个包逐字节相同。保留版本manifest与诊断后才可在源码/数据payload层做去重。`dagv2-webwalker-v4/webwalker_interim_score_patch.tar.gz`只有评分脚本与checksum，没有实验结果；该目录本来即保留。

## 散落的不可静默丢弃材料

- `dagv2-personamem-a48/outputs/planner_fix_live_check_20261011/`五个文件均没有在保留区找到同hash，属于真实planner probe证据。
- `dagv2-residual-f4/outputs/residual_memory_v1/`25个文件含多个synthetic/ablation版本和smoke metadata；保留并标为机械验证，不冒充数据集效果实验。
- 旧PrefEval初版`README_PREFEVAL_V4.md`、`DEPLOYMENT.json`、`VALIDATION_PREFEVAL_V4.json`各有特定版本；fix1/fix2候选结果文件已找到保留版同hash副本。仍需保留版本到文件hash映射。
- 独特协议文本：`dagv2-support-review/docs/{PAIRED_RUNNER.md,SUPPORT_REVIEW_V4.md,PERSONAMEM_RESTART_20261011.md}`；`dagv2-residual-f4/docs/PAIRED_RUNNER.md`；`dagv2-webwalker/docs/WEBWALKER_UPLOAD.md`。建议由源码历史包或单独docs归档保留。
- `dagv2/outputs/verification/*`大量是scripted/pytest/fixture产物；全部列入保留，不能写作正式模型实验。`bt_prefix_cache_20261009/real_smoke_first10_20261009`与`local_terminal_v1/smoke_3plus3_v2`包含较大真实服务运行证据。
- `dagv2_deploy/20261016_webwalker_v4_local_repair/`约446 MB，多轮候选和失败轨迹不同，不能只留final_validation而丢旧失败。

## 去重规则与操作限制

- 共找到1,786个跨文件/归档成员的精确SHA256重复组；不能把组数直接换算为可删除空间（组中可含tar成员，保留逻辑路径仍需开销）。
- **可去重内容**：原results四文件的重复副本；有逐文件hash映射的完全相同raw requests/reports；已验证890条gzip payload与原归档raw rows的内容副本。物理去重可以采用对象存储或硬链接，但原run目录逻辑路径与manifest必须可重建。
- **不能据此去重**：同名summary但hash不同；同指标但原始请求/模型/版本不同；不同压缩形式仅尺寸接近；只剩final结果而丢失败/重试；只保留源码而未保留原始数据/配置hash。
- 清点不授权删除。应先把保留目录原样迁入归档目标、核对每文件hash与数量，再由父任务决定移除旧源码/重复payload。本任务没有移动或删除任何文件。

## 文件与范围说明

- `results_inventory.json`：主机器清单，逐文件SHA256、归档成员SHA256、原始路径、受保护副本位置与重复组。
- `results_preserve_manifest.json`：应保留目录、散落文件、两个归档内独特metadata，以及有精确副本的候选路径。
- `results_inventory.files.json`、`results_inventory.archives.json`是第一轮中间产物；归档root-wrapper和gzip payload的补充只以主JSON为准。
- 标准code/data/config/vendor/test路径不作为散落结果扫描；其中嵌套outputs/results仍纳入。配置/数据/源码的完整保留由父任务的源码与数据manifest覆盖。研发文档按保守策略纳入，非每一文件都代表正式实验。
- 受保护区比较按候选大小/内容hash进行；没有修改`dagv2_analysis`和`output`。新迁入cleanup归档的路径不属于此清理前快照。
