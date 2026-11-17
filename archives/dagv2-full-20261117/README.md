# DAGv2 全量加密归档（2026-11-17）

本目录属于 `DonJonMao/bridge-tree` 的 `archive/dagv2-full-20261117` 分支。主分支原有文件保留。

当前状态：备份上传及恢复验证进行中。只有完成远端验证的源目录才会清理。

归档范围为下列五个目录的全部内容，包括未提交修改、被忽略文件、隐藏文件、`.git` 历史、数据、结果、依赖、原有压缩包、空目录和符号链接：

| 源目录 | 普通文件数 | 逻辑字节数 |
| --- | ---: | ---: |
| dagv2_analysis | 13664 | 11400218801 |
| dagv2_deploy | 4082 | 7490767777 |
| dagv2-personamem-v4 | 12846 | 3409374714 |
| dagv2-prefeval-v4-fix3 | 436 | 698741107 |
| dagv2-webwalker-v4 | 2279 | 3173830170 |
| 合计 | 33307 | 26172932569 |

因仓库公开且原目录含访问配置，使用标准 restic v2 仓库加密和去重。`repository/` 中的文件是加密数据及仓库元数据，恢复密码不在 GitHub 中。

## 恢复

安装 restic 0.19.1 或更新版本，然后克隆本分支：

```bash
git clone --single-branch --branch archive/dagv2-full-20261117 https://github.com/DonJonMao/bridge-tree.git bridge-tree-archive
cd bridge-tree-archive/archives/dagv2-full-20261117
restic -r repository --password-file /安全位置/bridge-tree-dagv2-20261117.key snapshots
```

每个源目录有独立 snapshot，并以目录名作为 tag。将五个快照依次恢复到同一目标目录：

```bash
for name in dagv2_analysis dagv2_deploy dagv2-personamem-v4 dagv2-prefeval-v4-fix3 dagv2-webwalker-v4; do
  restic -r repository --password-file /安全位置/bridge-tree-dagv2-20261117.key restore latest --tag "$name" --target /恢复目标/projects
done
```

恢复后 `/恢复目标/projects/` 内应出现五个原目录。源符号链接按原样保存，其中内部绝对链接要求恢复到原路径 `/Users/mao/projects`，或在迁移时显式重定位。Python 虚拟环境的解释器链接指向目录外的 Homebrew Python 3.11；解释器本体不属于这五个源目录，换机后需重新安装。

三个向量文件各在多个源目录间共享硬链接。分次 restore 后可通过加密保存的原始清单重建跨目录硬链接；文件内容均独立完整保存。

完整原始逐文件 SHA-256、权限、纳秒修改时间及链接清单另存于 `verification-manifest` 标签的加密快照：

```bash
restic -r repository --password-file /安全位置/bridge-tree-dagv2-20261117.key dump latest --tag verification-manifest /source-manifest.jsonl > source-manifest.jsonl
restic -r repository --password-file /安全位置/bridge-tree-dagv2-20261117.key check --read-data
```

原始清单 SHA-256：`c16f0222affc55d87ba935cdbbef6b2ac2d841ed8d2d659412dd7aad57c62837`。

密码文件初始单独保存于原机器的 `~/Documents/GitHub-backup-keys/bridge-tree-dagv2-20261117.key`，需由所有者妥善保管。此文件不在待清理的五个目录中，也不会上传至本仓库。
