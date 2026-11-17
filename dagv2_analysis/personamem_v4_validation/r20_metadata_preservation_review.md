# R20 历史部署 metadata 保留：独立只读核对

核对时间（UTC）：2026-10-14T01:18:21.862292+00:00

**结论：14 份 metadata 的源文件、既定目标路径、大小和 SHA256 均独立核对一致，总计 276,682 bytes。原 14 个归档/校验和、3 个 staging 根及其 51 文件仍完整保留。已有清理脚本可验证并接受这些同 hash 的预先保留副本；最终 tar 安装 gate 仍为执行前必需条件，本次未触发或代验 gate。**

## 身份与 14 份副本

- 锁定 cleanup_review.json SHA256：`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`，与指定锁定值一致。
- r20_historical_metadata_preservation.json SHA256：`1a8c4de751e2a194ca064d76b80529e200e7917c15a94b9d87517c98c026aee4`。
- execute_reviewed_cleanup.py SHA256：`1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a`，与前次审查相同。
- 源/目标集合与 review 的 preserve_before_delete 及保存回执精确对应，无重复或遗漏。全部路径为规范绝对路径，无文件或祖先符号链接。
- 下表每项源为 `/Users/mao/projects/dagv2_deploy/<批次>/patch/<文件>`，目标为 `/Users/mao/projects/dagv2_analysis/personamem_v4_validation/historical_deployments/<批次>/<文件>`。目标由 review 的源相对路径独立推导，没有仅信任回执。

| 批次/文件 | 源=目标 bytes | 源=目标=review SHA256 |
| --- | ---: | --- |
| `20261011_a48dc8d_v2/patch.json` | 1121 | `63cd24670ebe9196ba615a4ed3b2dd36cd7ab1442fffda122bc7193cd8eafa33` |
| `20261011_a48dc8d_v2/payload/DEPLOYMENT.json` | 38056 | `9edb5b5abf27a8513ae51a82de5ece6dd9078769c77cebfd36d50dbce4b4c849` |
| `20261011_a48dc8d_v2/README.md` | 6321 | `bd8bc99f49b0be4a12abffb9c433fa8767113892f8bc17190ec0fbedf15af704` |
| `20261011_a48dc8d_v2/apply_patch.py` | 4757 | `89aa630459211dda0fa9efcb3395b154932cb920898f4f2e25062dc024b920fd` |
| `20261011_a48dc8d_v3/patch.json` | 2965 | `8ae4ada55a74c12b50b99da8186e1cbc2c471c42dbd6e09fbd011be3eaa3028c` |
| `20261011_a48dc8d_v3/payload/DEPLOYMENT.json` | 59848 | `59f51db1086ae9fdf521fd8050bc130d081b931414c08b1e5eabe0c6d7192909` |
| `20261011_a48dc8d_v3/README.md` | 8647 | `517ce42c8f683d8a91aabe3c1854758aec1523639f92f895fa85478bccd49df3` |
| `20261011_a48dc8d_v3/apply_patch.py` | 4777 | `56f76d4e5bf41e32a452dfc14d7394e2550bcf7505f3efb0b55a6302bf2b9fdb` |
| `20261011_a48dc8d_v3/install_and_smoke.sh` | 538 | `6508c99a1b736b32c1ad10a7d507b210188138a42e68aacb2f174b7f46a96347` |
| `20261012_a48dc8d_v3_1/patch.json` | 2009 | `e79ac2808de0eb5041fd0828a5e8ecf127b77c960d0f15ef90118d26916d1e99` |
| `20261012_a48dc8d_v3_1/payload/DEPLOYMENT.json` | 135585 | `d93701a9e43eca5250f9022b76f69f5505d93d0da59ecc9b213f0e944301ff33` |
| `20261012_a48dc8d_v3_1/README.md` | 6735 | `f6be3a6433c9b233e01e844d0dc9cf70346b85858f32b01a15fe0be3588ef85a` |
| `20261012_a48dc8d_v3_1/apply_patch.py` | 4783 | `27844c66856dc2e8e0f31bffbe0e1861c85c3dabbb052b64b92b06c9eef5476c` |
| `20261012_a48dc8d_v3_1/install_and_smoke.sh` | 540 | `b80e10df99024937d416ae85781d841354c6e546c67683a018796bab402de642` |

## 原件与保护对象仍在

- 14 个原归档/校验和均重新读取计算 SHA256，全部匹配锁定 review；合计 881,590,899 bytes。
- staging 精确文件集合和逐文件 size/hash 均匹配：v2 为 9/9，v3 为 24/24，v3.1 为 18/18，共 51 个原文件，无新增或缺失。
- `/Users/mao/projects/dagv2/scripts/personamem_v3_1_diagnostics.tar.gz` 存在，924,139,875 bytes，规范路径。仅做文件名/元数据检查，未读或解包内容。
- 在 dagv2_deploy 及以下四个工作树的 scripts 范围内，此 diagnostics 文件名只发现上述 1 份；不外推为全磁盘唯一。
- `/Users/mao/projects/dagv2`、`dagv2-personamem-a48`、`dagv2-personamem-v4`、`dagv2-personamem-v4-reconcile` 四目录及各自 .git 均存在，规范路径，均不在 staging 删除根内。这只确认保留，不声称源代码自上次审查后未发生获授权修改。

## 现有清理脚本的静态行为

已只读检查 perform/installation_gate/verify_file：

1. 首先校验锁定 review、固定 14 文件及 3 staging 范围；随后**必须先运行 installation_gate(args.install_receipt)**，与保留目标是否已经存在无关。
2. 每份 metadata 先验证源文件；按同一批次+相对路径推导目标。目标不存在才复制；目标已存在则跳过复制，但**无条件执行 verify_file(expected)**，检查目标规范路径、size 和 SHA256。当前 14 份副本满足这一步，已有文件不会被覆盖或默认为可信。
3. 全部 14 份确认后，脚本再次核对 installation gate、review、归档和 staging，才进入删除分支。metadata 提前保留没有移除或绕过任何这类条件。
4. installation gate 仍要求指定 schema 的完整通过安装收据、包 size/hash、对应 checksum、包内 DEPLOYMENT 的 source_commit/validation.source_commit 和 release_ready=True。当前 metadata 保存回执不是安装收据，不能代替 gate。
5. 脚本仍未把 source_commit 固定为某次 R20 正式发布；正式执行时仍须提供当前最终包的真实通过安装收据。本文没有选择、认可或执行任何安装收据。

本次未导入或运行清理脚本（含 dry run），未删除/移动/复制任何文件，未修改 script/review/source，未运行测试、服务、模型或 tokenizer，也未读取标签/评分。唯一新增输出是本报告。

