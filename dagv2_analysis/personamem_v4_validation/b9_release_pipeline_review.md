# b9 发布链条增量兼容性复核

结论：**未发现 b9 新增的发布链条阻塞或命令参数不匹配。** 本文仅为静态兼容性审查，不是源码审批、真实模型通过、建包、安装或清理完成记录。

审查对象：`b9e28a7faa8d419f9f1283574fa095399919c243`，相对 R15 源码 `50d1ba0b2edb623384e51ac42ea12b36e5b69229` 的新增变化。审查时 release 工作树干净；当前 candidate 指向 b9、R16 固定 14 题和 1772 条离线通过，仍为 `release_ready=false`。

## 1. 增量与动态文件集合

- b9 增量为 12 个文件：README、两个运行模块及九个测试文件，其中四个新增测试文件。build/install/CLI/wrapper、正式 config、固定 smoke IDs 和 `original_manifest.json` 与 50d 完全同 Git blob。
- b9 有 **298 个提交 blob，共 76,085,814 字节**。全部为 `100644`/`100755` 普通 blob；没有触发建包器禁止的路径、扩展名或生成 metadata 重名条件。
- `build_personamem_v4.py` 和 `verify_final_archive_install.py` 都从指定提交的 `git ls-tree -rz` 动态枚举文件，并逐项读取/比较 Git blob；没有 281 或 298 个文件的固定假设。
- 预计包内源码 298 项，加 `VALIDATION_PERSONAMEM_V4.json`、`DEPLOYMENT.json` 两项为 300 项。源码体积明显低于安装验收器的 10,000 成员/1 GiB 总体积上限；实际生成后的包仍必须接受其完整检查，审批 metadata 不是本次构造或验收的对象。
- 历史新增的 `dagbt/personal_wire.py` 位于上述动态集合中；本次新增测试也全部被动态纳入，不需要更新安装文件 allowlist。`runner.frozen_sources()` 递归覆盖 `dagbt/` 与 `vendor/`，因此 reader/control/wire 运行身份仍被 smoke gate 绑定。README、测试、builder/installer 的完整身份由最终 Git 提交和 tar blob 验收补足，不能只靠运行模块 hash。

## 2. 57 冻结文件、3 个独立向量与凭据

- 冻结 manifest 仍为 **57 项**，与 50d 同 blob。其中 54 项在提交集合中；仅以下三个 `.npy` 不在提交包中，恰好匹配安装器的 `VECTOR` 正则：
  - `data/2wikimultihopqa/index/passage_vectors.npy`
  - `data/hotpotqa/index/passage_vectors.npy`
  - `data/musique/index/passage_vectors.npy`
- 安装器从 base 将向量 **copy 到临时 staging，再链接 staging 文件到目标**，不会链接 base inode；外部验收器仍检查第一次复制 3 项、第二次 0 项，并逐一核验目标与 base inode 不同。新增运行模块/测试没有改变这一集合或行为。
- installer 允许的源码集合取自 tar manifest；新增测试不会触发 `ensure_unlisted_sources_absent()`。额外允许的本地项仍仅为冻结数据、`DEPLOYMENT.json` 和明确的本地 credential 路径等既有边界。
- builder 禁止提交 `.local.json`，并在最终执行时对所有源码和生成 metadata 做已知凭据精确扫描；验收器也扫描实际 tar、子进程输出及 receipt。installer 不接受凭据路径出现在 release manifest，迁移文件保持 0600。
- 本次**没有打开凭据文件、读取密钥、执行秘密扫描或迁移凭据**；这里只确认相关机制及文件集合没有因 b9 变化而失配。是否实际无凭据泄漏必须由最终 tar 的既有扫描与隔离安装验收证明。

## 3. 当前文档命令与 CLI 参数

审查了 `release_commands.md` 的命令，参数均与当前 AST 中的 `add_argument` 声明匹配：

| 工具 | 文档使用的参数/动作 | 结论 |
| --- | --- | --- |
| `personamem_v4.sh` | `smoke/status/check --output` | wrapper 切换到自身 release 根目录，转发给现有 CLI；相对 R16 output 路径有效 |
| `prepare_source_approval.py` | `--root --candidate --full-test-log --smoke-output --config --expected-commit --output` | 全部存在；config/output 按 source root 解析 |
| `build_personamem_v4.py` | `--output --validation-file --private-credentials` | 全部存在；读取整个干净提交并要求精确 source approval |
| `verify_final_archive_install.py` | `--archive --output --base --source-repo --python --expected-commit --private-credentials` | 全部存在；内部 wrapper `install --base` 与 installer 一致 |
| `execute_reviewed_cleanup.py` | `--review --install-receipt --output [--execute]` | 全部存在；无 `--execute` 为仅复核/新 receipt |

`prepare_source_approval.py` 动态核验 candidate 的 pytest 数量、warnings、耗时和真实日志末行，不硬编码旧测试数量；1772 条通过不会因数量增长被拒。它仍要求两个方法、固定 14 题/28 行、精确当前源码/config，以及正式 production gate 通过。

安装 receipt 的 schema/字段与 cleanup 门槛一致：安装成功用 `passed=true`，安装记录自身 `release_ready=false` 不构成冲突；cleanup 验证包内源码审批为 true，并绑定当前 tar、SHA256 与 source commit。b9 未改变这些接口。

cleanup 的旧包/旧 staging allowlist 没有引用新源码文件或固定源码文件数。当前锁定 review SHA256 仍为：
`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`。
文档中新的正式包路径不在旧包 allowlist 或三个旧 staging 根中。

## 4. 证据绑定与未执行项

本次静态读取版本的 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `scripts/build_personamem_v4.py` | `32114ee5a7e33726998691b5ff843eb58646ad8492b26c57198ca7ed15515ce5` |
| `scripts/install_personamem_v4.py` | `439a1ace87629dc0ff13d7da00e3e0be44dcc2464bbbc2d5f3375800a6d5f27b` |
| `scripts/personamem_v4.py` | `6296c944edf76f838fc83f300f9c024f79442612cc5b8d6077965933e6142e44` |
| `scripts/personamem_v4.sh` | `5338596bd0fa91284c05261f393edcca62fb7fade071e786ccc5a271cb8af013` |
| `prepare_source_approval.py` | `fdc13e9fdf56549b46c58e6f512b2c5aeece3db27c74a336765fa251fa6e4041` |
| `verify_final_archive_install.py` | `c89fbd9fb6711d4811eac6d9a985963e4fb29b9c15a05c52198eb75255afda1a` |
| `execute_reviewed_cleanup.py` | `1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a` |
| `release_commands.md` | `503115c138e97c73bd515fff48dd0c17a0d085828ac8a1ac9c728023f8043a49` |

只运行 Git/文件元数据检查、公开脚本静态读取与 AST 解析。没有重跑测试、启动模型、读取标签/凭据、创建包、解包安装、修改源码或执行删除；唯一新增文件是本外部报告。真实 smoke、正式源码审批、最终包及其隔离双安装、清理等门槛仍按既有严格链条执行，不能以本审查替代。
