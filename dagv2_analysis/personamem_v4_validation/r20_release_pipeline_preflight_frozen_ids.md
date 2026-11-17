# R20 F/R 表达补丁：发布流水线增量只读预检

**未发现新 F/R 请求 metadata、新增两个测试与现有 build / source approval / final archive install / cleanup 接口的格式冲突。** 本报告是静态兼容性复核，不是源码批准、严格模型 smoke gate 通过、正式包安装通过或清理授权/执行回执。

仅核查相对 RELEASE `6c046374008ce2e45f817d6bc9876b3ab927ab18` 的增量及发布脚本绑定方式；没有导入/执行审批、构建、安装、验包、cleanup（包括 dry-run）、模型/tokenizer 服务或整套测试；未改 repo。没有读取 labels、scores、旧归档或 staging payload。

## 时点和源码身份

收到子任务时，RECONCILE HEAD 是 selector 版 `e02c8cc5349aca3222319927f05cf573a765c58c`；F/R 源码与 README 尚未 commit，新增两个测试未跟踪；Full26 为 root 持有的运行 session 86236。因此该时点 build 的 clean committed source 前置条件尚未成立，且不能引用旧 Full25 作为新源码验证。

只读审查期间，root 完成了测试与提交。结束前再次枚举所得：

- 当前 HEAD `e6677081cdfb33c01db3aaa274a497168f314f78`，tree `b332badbd2bbe8a97ad3a6e1ca8729a46308342c`，worktree clean。
- `dagbt/joint_reading.py` SHA-256 仍为已冻结的 `263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`。
- 动态完整树 **319 个 regular blob**，没有不支持的 mode/path、symlink 或待纳入的 untracked 文件。来源总大小为 **76,454,373 bytes**（仅文件 stat 聚合，未读取数据/标签内容）。
- 98 个默认 pytest 命名测试文件全部位于 `tests/`；新 `test_v4_frozen_ids_schema.py` 与 `test_v4_frozen_ids_schema_review.py` 自动属于全 tests 范围。
- Full26 receipt 此时记录 exit=0、source_unchanged=true，实际 command 为 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`；log SHA `4fed28a000d689c880bb8efa283f7085d47385a923f370849b82866662660c42`。本子任务仅检查命令格式及 receipt 状态，未重复 root 的全量测试/逐 blob 绑定审计，不自行授予 offline 或模型批准。

以上分别保留受派时“未 commit / Full26 running”和收尾时的真实观测，避免用旧时点覆盖 root 后续动作。

## 与 6c 的新差异

生产差异只有 `dagbt/joint_reading.py`：上一轮完整 wire token 选择修复，加上当前 F/R 禁重述字段、条件 prompt、按变量 schema；其余差异是 README 与测试（包含旧测试 transport fake 适配，以及新增选择器/独立审核/F/R 文件）。新增测试按提交完整树进入归档，不依赖固定文件数名单。

逐字核对以下工作树文件与 6c blob 一致：`scripts/build_personamem_v4.py`、`scripts/install_personamem_v4.py`、`scripts/personamem_v4.py`、`.sh` wrapper、`configs/personamem-v4.json`、`configs/personamem-v4-smoke-ids.json`、`original_manifest.json`、`dagbt/runner.py`、`dagbt/resources.py`。因此没有新增 deployment manifest、安装资产、index/向量兼容性、私密凭据路径或结果封装格式变更。

## 各接口增量结论

| 环节 | 新差异的兼容性结论 | 仍独立存在的实际 gate |
| --- | --- | --- |
| build | 动态 `git ls-tree` 读取 clean HEAD blob；319 个来源预期生成 **321 tar members**（另加 validation 与 deployment）。两个新测试路径均合法，无固定 317/319 上限。 | 正确 committed source、实际精确 source approval、真实私密值扫描及归档 round-trip；本轮未执行。 |
| source approval | 98 个 tests 均在 tests/，Full26 命令符合既有 whole-suite 命令语法；新生产字段由 `runner.frozen_sources()` 对 dagbt 文件的原有 hash 机制覆盖。 | candidate 精确 commit/source hashes、完整日志及当前源码的严格 14 题两 arm smoke；旧 6c run 的 source hashes 不能代替新源码。 |
| final archive install | 验包动态比较来源集合与对应 commit 的每个 blob；321 members、约 76 MB source 远低于 10,000 members / 1 GiB 安全界限。installer 按 manifest 校验所有包内文件，新 tests 无额外白名单需求。 | 最终准确 tar 的 hash/manifest/commit 比对、隔离离线安装两次及幂等性、资产/index 验证。未生成最终包或执行安装。 |
| cleanup | 三个外部脚本 hash 与此前审阅版本相同；cleanup 绑定新正式包通过的 installation receipt 及同一 source_commit，不固定 6c。新增 tests/source 不在既有旧归档与 staging 删除集合。 | 精确 passing install receipt、review hash、14 份 metadata 保留、逐项旧 payload freshness 及显式执行条件。未重做 freshness，也未执行 dry-run。 |

`repair_scope.frozen_observation_ids` 仅是运行时模型请求的 controller-owned 输入 metadata。它没有变更 `DEPLOYMENT.json`、validation、installer receipt、result row 或 cleanup plan 的 schema；outputs 不随包打入。F 只表达已有 runtime 的禁止重述，引用/解除仍由原 R 规则决定。打包和安装不需要解析此字段，strict smoke 仍然验证实际合法成功答案、semantic terminal 与完整 audit；schema 补丁或离线测试通过不会降低这些条件。

## 外部脚本固定身份与限制

- `prepare_source_approval.py` SHA-256 `84d59d9c0f6b7fd6b3efc4bef7810a7219da0f7c282a5c52cf16248d7c8b596d`
- `verify_final_archive_install.py` SHA-256 `c89fbd9fb6711d4811eac6d9a985963e4fb29b9c15a05c52198eb75255afda1a`
- `execute_reviewed_cleanup.py` SHA-256 `1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a`

这三份与既有预检记录相同，未重新审计无差异的整个实现或旧资源内容。发布流水线无需因为 F/R 增量新增格式迁移或调整固定数量；后续是否能发布，仍由 root 对当前真实源码/模型实验和最终包逐 gate 验证。本报告不声称已批准、已通过严格模型 gate 或准确率改善。
