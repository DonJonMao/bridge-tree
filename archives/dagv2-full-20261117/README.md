# DAGv2 全量源码归档（2026-11-17）

分支：`archive/dagv2-full-20261117`。五个项目的完整源码、数据和恢复资料已保存于本分支；全部归档对象已从 GitHub 取回并校验摘要。

五个目录按原名称直接放在本分支根目录：

| 原目录 | 普通文件 | 原始逻辑字节 |
| --- | ---: | ---: |
| dagv2_analysis | 13666 | 11400235193 |
| dagv2_deploy | 4082 | 7490767777 |
| dagv2-personamem-v4 | 12846 | 3409374714 |
| dagv2-prefeval-v4-fix3 | 436 | 698741107 |
| dagv2-webwalker-v4 | 2279 | 3173830170 |
| 合计 | 33309 | 26172948961 |

范围包括未提交修改、被忽略文件、隐藏文件、原 Git 历史、数据、结果、依赖、原有压缩包、空目录、319个符号链接和跨目录硬链接。Bridge Tree 原 main 的文件保持原样。

## 文件保存方式

普通源码和文件可以直接浏览。大于或等于48 MiB的普通文件拆成最多32 MiB的块，原文件旁有 `.parts.json` 指引。块放在 `.dagv2-archive/parts/`，恢复顺序及完整文件摘要见本目录 `restore-index.json`。

凭据、密码哈希配置、含凭据的源码原件、含凭据的旧源码包、独立 Git 历史包、Finder 元数据最新副本和所有原 `.git` 元数据采用 AES-256-GCM 分块认证加密，块放在 `.dagv2-archive/vault/`。相关项目源码提供脱敏公开副本；原件可用密钥完整恢复。四个触发平台误报的第三方依赖文件也按原件加密保存。原 Git 历史会在恢复时回到各自目录。

逐文件 SHA-256、权限、所有者、纳秒修改时间、空目录、链接关系和 macOS 扩展属性也已加密保存。加密使用随机独立nonce，密码以Scrypt（n=32768,r=8,p=1）派生256位密钥。密码和私有上传计划不会上传到GitHub。

## 恢复完整目录

恢复密钥单独保存在所有者原机器的 `~/Documents/GitHub-backup-keys/bridge-tree-dagv2-20261117.key`。请另存该文件；公开仓库不包含恢复密码。

已克隆本分支时，在仓库根目录运行（建议使用macOS以恢复原始扩展属性）：

```bash
python3 -m pip install cryptography
python3 archives/dagv2-full-20261117/restore_source_archive.py   --repo-root . --target . --restore   --password-file /安全位置/bridge-tree-dagv2-20261117.key
```

该命令拼接大文件、解密私有原件、恢复原 `.git`、修复硬链接，核对每个原文件SHA-256，然后恢复权限、时间和扩展属性。它会在验证后清理本归档生成的 `.parts.json` / `.encrypted.json`；如果这些指引被用户改动，会拒绝删除并报错。

也可只下载本目录的 `restore_source_archive.py`，无需克隆全部数据；先从本分支提交记录取得一个完整40位提交SHA，再从该提交直接恢复：

```bash
python3 restore_source_archive.py   --repo-root . --target /Users/mao/projects   --restore --from-remote --commit 完整40位提交SHA   --password-file /安全位置/bridge-tree-dagv2-20261117.key
```

原绝对符号链接按原样保存，恢复到 `/Users/mao/projects` 可保留其语义。换位置后可用同目录 `recovery_helper.py` 的显式链接迁移功能。虚拟环境解释器链接指向目录外的 Homebrew Python 3.11；解释器本体属于外部依赖，换机器时需安装。

## 校验

恢复后使用相同参数将 `--restore` 替换成 `--verify-only`，可核对文件、权限、时间、扩展属性及链接。换机器导致uid/gid不同时，可显式加 `--ignore-owner`。

只验证GitHub内容而不写入本地目录：

```bash
python3 restore_source_archive.py --repo-root .   --verify-remote --commit 完整40位提交SHA   --password-file /安全位置/bridge-tree-dagv2-20261117.key
```

原始加密清单的SHA-256：`8a438a586043fd3fe3e4b4cee8fa293babc48a4dbd3a66f90918a35703bbbb72`。

已使用恢复工具逐文件校验最新快照的33,309个文件、26,172,948,961字节，全部一致。每个归档对象均从全新的空Git仓库独立取回，核对SHA-256、Git对象摘要和长度；最终分支另行核对全部路径、模式、对象和大小。原目录仅在全部远端验证及严格的本地逐文件、链接和扩展属性复验通过后清理。
