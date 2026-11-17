# DAGBT 历史实验与清理归档

日期：2026-10-27。当前代码入口见 [DAGBT_FINAL.md](../../DAGBT_FINAL.md)。

## 本次保留和删除

保留 `dagv2-personamem-v4`、`dagv2-prefeval-v4-fix3`、`dagv2-webwalker-v4` 三条任务线。已移除 9 个旧代码目录和 34 个重复部署解包目录；仅删除这 43 个列明目录，没有删除整个部署记录目录。

删除阶段文件系统可用空间增加 **9.43 GB（8.78 GiB）**。该数字来自删除前后实际空间读数，不将硬链接重复计入。

## 实验记录位置

| 原位置 | 现位置 |
|---|---|
| `dagv2/outputs/` | [results/dagv2/outputs/](results/dagv2/outputs/) |
| `dagv2/results/` | [results/dagv2/results/](results/dagv2/results/) |
| 其他已移除旧版本的 `outputs/`、`results/` | `results/<原目录名>/outputs/`、`results/<原目录名>/results/` |
| 旧 `dagv2/scripts/` 中 4 个实验 tar.gz | [artifacts/dagv2/scripts/](artifacts/dagv2/scripts/) |
| 旧 `dagv2/tmp/` | [research/dagv2_tmp/](research/dagv2_tmp/) |
| 3 个部署安装目录中的运行状态文件 | [results/deployment/](results/deployment/) |
| 旧版本独有的数据和索引缓存 | [assets/old_data/](assets/old_data/) |

三条最终任务线中原有的输出、结果保持原位置。`../../dagv2_deploy/` 中 15 个原始发布包及校验文件保持原位置，所有未列入删除清单的验证、smoke、失败诊断、报告、补丁等文件继续保留。

每个实验目录保留原有逻辑树，包括 requests、ledger、events、失败快照、配置、manifest 和得分。历史文件内容中的旧绝对路径保持原样；迁移关系由清单记录。实际文件系统软链接已按新位置重写，原目标同时记入清单。机械验证、合成测试、失败运行和正式实验继续保留各自原标签。

## 代码追溯

- [history/dagv2_all_refs.bundle](history/dagv2_all_refs.bundle)：原共享仓库的全部 Git 引用及提交历史。
- [history/](history/)：各版本工作区补丁、旧 Git 指针及 bundle 校验记录。
- [source_snapshots/](source_snapshots/)：9 个旧版本的源码压缩快照；[deployment/](source_snapshots/deployment/) 包含 34 个部署源码快照，包括候选修复代码。
- 源码快照不包含数据、实验输出、虚拟环境和浏览器依赖；它们已单独迁移、映射或由原部署包覆盖。源码恢复时结合 `migration.json` 中的 `data`、`moves` 映射。
- PersonaMem 和 WebWalker 最终目录已经改为独立 Git 仓库；WebWalker 原有未提交修改和新增文件均保留。PrefEval 最终目录保留原有交付文件形式。

在新的空目录恢复 Git 历史的示例：

```bash
git clone /Users/mao/projects/dagv2_analysis/cleanup_20261027/history/dagv2_all_refs.bundle /path/to/new/history-checkout
```

该命令恢复提交历史；未提交版本另见源码快照和工作区补丁。

## 核对证据

- [migration.json](manifests/migration.json)：逐项迁移、数据文件的 SHA256 与保留副本、软链接修正、43 个已删除目录和空间读数。
- [experiment_file_coverage.json](manifests/experiment_file_coverage.json)：17,961 个实验及报告文件的原路径、保留位置或源码包成员、SHA256。
- [source_file_coverage.json](manifests/source_file_coverage.json)：旧源码逐文件与快照成员核对。
- [final_source_verification.json](manifests/final_source_verification.json)：三个最终版本代码内容、两个 Git 仓库的 HEAD、未提交差异及完整性校验。
- [symlink_verification.json](manifests/symlink_verification.json)：316 个保留软链接，无悬空、无待删除目标引用。
- [git_deploy_review.md](manifests/git_deploy_review.md)、[results_inventory.md](manifests/results_inventory.md)：清理前只读审查报告；其中原路径须结合迁移清单阅读。
- [deploy_archive_inventory.json](manifests/deploy_archive_inventory.json)、[deploy_data_coverage.json](manifests/deploy_data_coverage.json)：15 个原发布包校验以及 34 个解包目录的数据保留覆盖。

离线现有测试共 239 项通过：PersonaMem 98 项、PrefEval 40 项、WebWalker 101 项。测试记录见 [validation.json](manifests/validation.json)。本次整理没有重跑模型基准实验。
