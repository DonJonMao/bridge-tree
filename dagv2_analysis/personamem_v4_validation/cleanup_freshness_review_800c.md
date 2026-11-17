# 清理计划当前有效性核对

核对时间（UTC）：2026-10-13T20:36:21.108378+00:00

**结论：原锁定范围仍与当前文件相符；未执行清理，真实新发布 gate 尚未在本次核对中满足或代验。**

## 锁定身份

- review SHA256：`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`；与指定锁定值一致：True。
- plan SHA256：`88df5e5e4ac01850750ac4321514ef7eae00846bf587d0577778ce2025a2fa4e`；与 review 的 bytes/hash 一致：True。
- 清理脚本 SHA256：`1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a`。只静态阅读，未导入或运行，包括 dry run。
- 脚本只允许固定 14 文件与 3 staging 根；执行前校验新包安装收据、包/校验和及 DEPLOYMENT 的 source_commit/release_ready，14 份 metadata 全复制并校验后才删除，再逐文件重验并写执行收据。
- gate 参数必须使用这次最终正式包的真实通过收据。脚本未锁定 R18/800c 为唯一 source_commit，本报告也未检验当前 R18 或授权使用旧收据代替新 gate。

## 14 个归档/校验和（相对 /Users/mao/projects）

| 文件 | 当前 size/SHA/canonical |
| --- | --- |
| `dagv2_deploy/20261011/dagv2_bt_deploy_20261011_personamem_v4.tar.gz` | 全部一致 |
| `dagv2_deploy/20261011/dagv2_bt_deploy_20261011_personamem_v4.tar.gz.sha256` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d/dagv2_bt_deploy_20261011_personamem_a48.tar.gz` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d/dagv2_bt_deploy_20261011_personamem_a48.tar.gz.sha256` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d_v2/dagv2_personamem_a48_v2_patch.tar.gz` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d_v2/dagv2_personamem_a48_v2_patch.tar.gz.sha256` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d_v3/dagv2_personamem_a48_v3_patch.tar.gz` | 全部一致 |
| `dagv2_deploy/20261011_a48dc8d_v3/dagv2_personamem_a48_v3_patch.tar.gz.sha256` | 全部一致 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/dagv2_personamem_a48_v3_1_patch.tar.gz.sha256` | 全部一致 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/dagv2_personamem_a48_v3_1_patch.tar.gz` | 全部一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_patch.tar.gz` | 全部一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_1_patch.tar.gz.sha256` | 全部一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_patch.tar.gz.sha256` | 全部一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_1_patch.tar.gz` | 全部一致 |

合计 881,590,899 bytes；精确集合与 plan 一致：True。

## 3 个 staging 与 14 份保留 metadata

| staging（dagv2_deploy 下） | 实际/清单文件 | 当前文件与 Git payload | 必须先保留 |
| --- | ---: | --- | --- |
| `20261011_a48dc8d_v2/patch` | 9/9 | 一致 | `patch.json`, `payload/DEPLOYMENT.json`, `README.md`, `apply_patch.py` |
| `20261011_a48dc8d_v3/patch` | 24/24 | 一致 | `patch.json`, `payload/DEPLOYMENT.json`, `README.md`, `apply_patch.py`, `install_and_smoke.sh` |
| `20261012_a48dc8d_v3_1/patch` | 18/18 | 一致 | `patch.json`, `payload/DEPLOYMENT.json`, `README.md`, `apply_patch.py`, `install_and_smoke.sh` |

合计 51 个 staging 文件、33 个可重建 Git payload、14 份 metadata（276,682 bytes）、2 份外部已有相同验证记录、2 个已列明缓存文件。当前已在 historical_deployments 中校验通过的保留副本：0/14；不得省略正式执行时的复制/重验。
清单外 12 份既有验证/说明文件仍存在且大小匹配：True（旧清单未提供这些文件的 hash，不声称内容逐字未变）。

## 保护范围与新归档

- `/Users/mao/projects/dagv2/scripts/personamem_v3_1_diagnostics.tar.gz`：存在，924,139,875 bytes，清理范围外。
- `/Users/mao/projects/dagv2/scripts/dagv2_results_20261008_025515.tar.gz`：存在，397,869 bytes，清理范围外。
- `/Users/mao/projects/dagv2/scripts/dagv2_a48_v2_smoke_debug.tar.gz`：存在，150,719,323 bytes，清理范围外。
- `/Users/mao/projects/dagv2/scripts/dagv2_a48_v3_smoke_debug.tar.gz`：存在，46,580,122 bytes，清理范围外。
- `/Users/mao/Downloads/dagbt_webwalker_a5_v1.tar.gz`：存在，637,097 bytes，清理范围外。
- `/Users/mao/Downloads/dagbt_webwalker_a5_v1.tar.gz.sha256`：存在，95 bytes，清理范围外。
- `/Users/mao/Downloads/evidence_logs_start_20260927_034132_625737_20260930_030305_3729264.tar.gz`：存在，295,192,359 bytes，清理范围外。
- `/Users/mao/Downloads/evidence_logs_start_20260927_034132_625737_20260930_030305_3729264.tar.gz.sha256`：存在，140 bytes，清理范围外。
- 在上述 projects 归档文件名扫描范围内，`personamem_v3_1_diagnostics.tar.gz` 仅发现 1 份；大小 924,139,875 bytes（881.33 MiB）。仅检查元数据，不解包或读标签/分数。
- 四个源工作树均存在且无目录删除命中；`dagv2/scripts` 仅列明的 4 个旧补丁归档/校验和属于已审定例外，源码及实验输出/日志不在删除集合。RELEASE、RECONCILE、R18 运行未被读取或修改。
- staging 精确文件集合没有新增日志；执行脚本逐项删除而非通配清扫，任何后续新文件都会使精确集合检查或 rmdir 失败。
- 当前未发现新增的清单外 DAGV2 deploy/patch tar。其他工程及 Downloads 的无关包一律未判为无用，不扩大删除范围。

本次仅读取清单、脚本、归档/暂存文件 hash、历史 Git blob 和文件元数据；未运行测试/网络/模型/清理，不读取标签或分数。唯一新增输出是本外部 freshness report。
