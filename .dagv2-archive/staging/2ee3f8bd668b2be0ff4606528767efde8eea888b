# R19 0cc2cc7 发布流水线只读预检

**结论：未发现当前 312 文件来源树与既有打包、安装验收、清理流水线的兼容性 blocker；无需修改发布代码。** 这不是源码审批、smoke 通过、正式包安装或清理回执。R19 正在由 root 独立处理，本核查没有读取其预测、标签或分数，也没有介入运行。

## 当前来源与 Full23 的绑定

- 提交：`0cc2cc78498bcd215252fb8e82d2168868a71b3f`。
- Git tree：`ef6fa107340a6721add01923e78bbec36cfc233f`。
- RELEASE、RECONCILE 核查时均为该 HEAD，`git status --porcelain --untracked-files=normal` 均为空；发布 baseline `a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1` 是其祖先。
- 完整 `ls-tree` 有 **312 个 regular blob，76,322,355 bytes**，对象模式及路径全部满足 build 规则；无受禁的本地凭据、向量、嵌套归档、outputs、derived 或生成发布 metadata 路径。
- Full23 receipt 的 before/after 两个 312 项 hash map 相等，文件集合与该提交完整树相等。对其中 **304 个非标签、非 results 文件**逐项核对：提交 blob 的 SHA256、两个工作区文件及 Full23 before/after 记录均一致。四个 `evaluation_only.json` 和四个 `results/` 文件仅核对树/已有记录身份与 clean 状态，**没有读取这些文件内容，不声称本轮对其做了内容重验**。
- `runner.frozen_sources()` 的静态等价枚举得到 **104 项**，本轮逐项 hash 与 candidate.source_hashes 完全相同；未导入/运行 runner。
- Full23 日志末行为 `2020 passed, 69 warnings in 109.93s (0:01:49)`；log SHA 与 candidate、receipt 相符。实际命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests` 满足审批器的 whole-suite 命令规则；全部 **92 个** pytest 默认命名测试文件均位于 `tests/`。
- receipt 的 base_commit 仍为测试当时的 `800c517...`，这是原始执行来历；本次 blob/字节核对建立最终提交联系，不改写 receipt。candidate 当前 `source_commit=0cc2cc7...`、`release_ready=false`，符合未审批候选状态。

相对 800c517，新增的是一份 handoff policy 文档与五个测试文件；其余改动是 README 及四个生产文件。新增文件自动进入提交树与正式包，不依赖手工文件数白名单。

## 打包与安装接口

`build_personamem_v4.py` 从 clean HEAD 的完整 `git ls-tree` 读取提交 blob，生成完整 manifest 并逐项 round-trip 验证。本次预计 **314 个 tar 成员：312 个来源文件 + VALIDATION_PERSONAMEM_V4.json + DEPLOYMENT.json**。没有固定 303、306 或 312 文件数的限制。

`verify_final_archive_install.py` 也动态枚举指定提交的完整树，要求 tar 来源集合及每个 blob 字节完全相符。314 成员远低于 10,000 成员上限，约 76 MB 来源也远低于 1 GiB 上限；最终 tar 连同生成 metadata 仍必须实际通过原有检查，本报告未生成归档。

installer 根据 manifest 验证每个随包文件，并保持 **57 项固定资产：54 项随包、3 个既有多跳数据集向量复用**。`original_manifest.json`、public config、固定 smoke IDs、资源索引代码、installer 及 wrapper 均未改变，因此 R19 planner/schema/handoff 改动没有改变向量路径、索引兼容性、私密凭据 0600 规则或安装幂等接口。

新 `joint_support_handoff_deferred` 是运行事件，不是新增安装资产或 reader snapshot schema。打包不包含 outputs；installer 不解析该事件；原 smoke gate 继续要求固定 14 题两 arm、当前源码/config/数据身份、28 个 canonical 合法成功答案、residual 真实 semantic terminal 与完整 audit。不能用 advisory、离线测试或本报告替代该 gate。

## 已冻结流水线身份

以下 Git blob 均与 `800c51763ea3a2bfcad459b4413d41c6432db52e` 相同：

| 文件 | Git blob |
| --- | --- |
| `scripts/build_personamem_v4.py` | `d6d28eb4f6822edb587ec1cd9ee27911e8c831b3` |
| `scripts/install_personamem_v4.py` | `96146aec76634828a7f80d9140bf242d43cdd607` |
| `scripts/personamem_v4.py` | `74e8d3d452a9acff4de999443dd044e300a7c694` |
| `scripts/personamem_v4.sh` | `ba9c1bfd7f01033c17a11056841cb21c0e595178` |
| `configs/personamem-v4.json` | `2a374955d2da4c6c305bb27c26879693a9910039` |
| `configs/personamem-v4-smoke-ids.json` | `8084037424c1325fe041c171c05dc538564070e4` |
| `original_manifest.json` | `c4be5f53dfa5ab6495438c95c17bee1938ce8419` |
| `dagbt/runner.py` | `f25afc6ccba7f8940674ecb0fbb0698f47c66150` |
| `dagbt/resources.py` | `b000ba23d695ce9a36785ef7db8b02713c7de8e0` |

外部脚本亦与上一轮记录的 SHA256 完全相同：

- `prepare_source_approval.py`：`84d59d9c0f6b7fd6b3efc4bef7810a7219da0f7c282a5c52cf16248d7c8b596d`。
- `verify_final_archive_install.py`：`c89fbd9fb6711d4811eac6d9a985963e4fb29b9c15a05c52198eb75255afda1a`。
- `execute_reviewed_cleanup.py`：`1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a`。

没有执行或导入这些脚本及其辅助函数，包括 approval prepare、build、install、verify、cleanup dry-run。

## 清理兼容性与执行边界

cleanup review 的锁定 SHA 仍是 `f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`，cleanup plan 为 `88df5e5e4ac01850750ac4321514ef7eae00846bf587d0577778ce2025a2fa4e`。执行代码固定 14 个旧归档/校验文件和 3 个旧 staging 根；新源码工作树、当前运行输出与新正式包不在删除集合。

review 中的历史 `reviewed_release_source_commit` 不是运行 gate 的固定版本要求。实际 gate 核查新包安装收据的 passed/完整验证标志、tar/hash、DEPLOYMENT 与 validation 的同一真实 source_commit；因此可绑定新的 0cc2cc7 正式包，无需为换提交改清理白名单。

正式执行仍要求先保留并验证 14 份 metadata，再逐项重验旧归档和 staging；全部来源/保留副本/安装收据身份持续吻合才删除。任何新增 staging 文件或 hash 改变都会拒绝。**本次核查只验证脚本/清单身份和机制，没有重做旧归档及 staging payload 的 freshness 检查**；应在真正新包安装通过后运行既有 dry-run，不能将旧 freshness 报告或本报告当作执行回执。

## 证据及未完成 gate

- Full23 log SHA256：`41179fccef061102574cbc1ec6b3b4ea1260121e9488e55646de365633f19cae`。
- Full23 receipt SHA256：`978c14afa8252ee31866ff93fcf4e4bbd3986b2120b2a0abe707bc5dbb999c57`。
- public config SHA256：`6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05`。

本次没有发现需要更改发布流水线的 blocker。R19 实际 smoke、源码审批、准确最终 tar 的双次隔离安装验收及后续清理仍是各自独立 gate，由 root 在真实条件满足后执行；本报告不提前授予任何通过状态，不作准确率结论。唯一新增文件是本外部报告。
