# 800c517 发布衔接只读核对

**结论：未发现新来源清单或 frontier 快照字段与现有 build/install/approval/check 流程冲突；无需修改发布代码。** 核对提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`。RELEASE 与 RECONCILE 均为该提交且 clean，306 个提交 blob、两工作区文件、Full22 前后 source maps 逐文件一致。旧 303 文件报告 `r18_release_pipeline_preflight.md` 保留，不覆盖。

| 项目 | 核对结果 |
|---|---|
| 提交来源 | 306 regular blobs，76,249,949 bytes；均符合 build 路径/对象规则 |
| 预计最终 tar | 308 文件：306 来源 + 2 个生成元数据；未实际构建 |
| 新增来源（相对 8dac32b） | `docs/RESIDUAL_FRONTIER_POLICY_V2.md`、两个 discovery frontier 测试文件 |
| runtime inventory | 104 项，与当前 `validation_candidate.json.source_hashes` 完全相同 |
| pytest 默认文件清单 | 87 个，全部位于 `tests/` |
| 固定安装资产 | 57 项：54 项随包，3 个既有数据集向量继续复用 |

`build_personamem_v4.py` 以完整 `git ls-tree` 枚举提交 blob，动态生成 manifest 并逐项 round-trip 验证；`verify_final_archive_install.py` 动态比对 tar 与指定提交的完整树，不固定 303/306 数量。308 个预期文件及约 76 MB 来源明显低于其 10,000 文件/1 GiB 边界。installer 按 manifest 检查每个文件并维持原 57 资产、私密凭据、派生索引及幂等规则。build、installer、wrapper、public config、original manifest 与 8dac32b 的 Git blob 均未改变。

仅调用外部 approval 脚本的只读 `clean_commit`、`verify_test_command`/`verify_test_log` 辅助函数，**没有调用 `prepare()` 或 CLI approval**。实际 Full22 command `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests` 通过其 exact whole-suite/clean-source 检查；日志 hash 与 candidate 一致，终行准确为 `1938 passed, 69 warnings in 111.93s (0:01:51)`。Full22 receipt 的 RECONCILE/旧 base_commit 是真实测试来历；本次提交 blob/工作区逐字节核对建立到最终 800c517 的联系，不改写原 receipt。

新 `discovery_frontier`、`discovery_contexts`、`source_namespace`、exposure/promotion 字段属于运行态诊断/恢复记录；来源包不会打包 outputs。installer 不解析这些 reader 字段，`validate_result`/`check_smoke` 没有排斥额外 reader 字段的封闭 schema，也不要求纯 discovery frontier 清空。原 `status=ok`、合法选项、真实 semantic terminal、validation_complete、audit_complete、固定14题两arm及 source/config 一致性仍必须通过，未放宽失败判定。

R18 的实际完成结果仍是独立 gate。candidate 当前正确保持 `release_ready=false`；此只读报告不批准打包/发布。核对时 `release_commands.md` 仍含 R18“尚未启动”的阶段性旧语句，实际执行前应由 root 更新/标历史；它不影响上述代码契约。本次未改仓库，未进行实际 approval/build/install/cleanup、全套测试或模型/网络调用，只新增此报告。

证据 hash：

- Full22 log：`47852ce77cc6412a55319635d2822f16aeca2d18a1b4afbe88dd3703c67faba0`
- Full22 receipt：`2dcf4e4301cac00692a02c080f208665bc7994289f3fea40bc904c40a83ad897`
- public config：`6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05`
- 外部 `prepare_source_approval.py`：`84d59d9c0f6b7fd6b3efc4bef7810a7219da0f7c282a5c52cf16248d7c8b596d`
- 外部 `verify_final_archive_install.py`：`c89fbd9fb6711d4811eac6d9a985963e4fb29b9c15a05c52198eb75255afda1a`
