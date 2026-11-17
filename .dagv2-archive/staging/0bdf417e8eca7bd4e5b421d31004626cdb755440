# 800c517 / R18 当前元数据独立核对

结论：指定四份当前元数据未发现阻断性不一致；本回执不是源码审批、整轮模型通过、安装验收或准确率结论。

- RELEASE 与 RECONCILE 均为干净提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`。两份 JSON 的当前源码、Full22、R18 和未通过 gate 状态相符；旧提交、Full21 和旧运行仅出现在明确的历史字段或历史说明中。
- Full22 的实际命令为 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`；日志尾部确为 1938 passed、69 warnings、111.93 秒，回执 exit_code=0，日志 SHA256 与两份当前 JSON 一致。原回执真实记录 RECONCILE/base 8dac32b，306 项 source_before/source_after 一致；该历史执行身份不能改写为在 800c517 上重新执行过测试。源码字节与最终提交的绑定沿用已完成的 `r18_release_pipeline_preflight_800c517.md` 核对。
- checklist 正好 32 个唯一要求，全部状态为 `offline_regression_passed_real_model_gate_pending`，全部绑定 800c517 和 Full22 回执。143 处 implementation/regressions/current_test_evidence 引用（49 个唯一文件）均存在；需求审查 Markdown 的 32 项回归映射逐项等于 JSON。正文列出的当前证据、历史存档和执行脚本均存在。
- 候选的 104 个运行源码 SHA256 均匹配 RELEASE，也与 R18 manifest 完全一致。公开配置 SHA256 为 `6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05`；R18 manifest SHA256 为 `3212fc49bc9ecdb49d44ff05c8c8f182e2a55ae442d1cec40a35bfd4b74253c4`，均核对相符。运行两臂为 original / dagbt_residual_memory_v2，14 个 ID 与 configs/personamem-v4-smoke-ids.json 完全相同。
- 只读 ps 确认 PID 10667 仍是 R18 runner。读取 progress 时 question_index=3（0-based），对应第 4/14 题 residual generating，updated_unix=1791923679.381526。当前 JSON 内 question_index=1（0-based），对应第 2 题 original 的 progress，是 updated_unix=1791923477.407292 的较早快照；运行推进造成快照落后，不构成 whole-run gate 状态错误。需求审查已明确实时进度以 runner/r18_structural_monitor.json 为准。若把 JSON 当作实时面板，应保留其时间戳语义，不能把该旧题号当最新进度。
- release_commands 的参数链匹配实际运行：RELEASE root、800c517 完整提交、Full22 日志、outputs/v4_validation_r18、configs/personamem-v4.json；candidate → 独立 source_approval_final.json → builder → 同一最终 tar 的隔离安装验证 → dry-run 后授权清理。脚本 argparse 接口接受文中所有旗标；wrapper 自行切换 RELEASE root，因而相对输出路径不依赖调用者 cwd。没有再次 launch 或复用旧 R17 审批的命令。Python、base、公开配置和私有凭据路径存在；未打开凭据内容。
- cleanup_review.json 的 SHA256 与命令文档锁定值 `f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84` 相符。指定 source_approval_final.json、最终 tar 及 sha256、final_archive_installation.json、cleanup_dry_run_final.json、cleanup_execution_final.json 均尚不存在；文档正确把它们描述为未来输出。核对只证明这些指定正式产物尚未生成，不将此前 helper 检查误报为正式安装验收。
- 标签边界表述准确：代理不以标签/评分选题、调参或做结构验收；runner.py 的 score_all 先要求所有数据集/方法均 terminal，然后才载入 evaluation_only.json，正常 run 在生成循环结束后自动调用评分。不能把此边界写成“整个 runner 永不读标签”，也不能把自动评分误称为模型结构 gate 已通过。

本次仅进行了文件/Git/进程的只读核对，并新增本外部回执；未运行测试、模型、网络请求、审批器、建包、安装、清理，也未修改现有四份元数据或源码。没有读取标签文件、结果评分或干预 R18。R18 全轮未通过，release_ready 仍为 false。

## 核对文件 SHA256

- `validation_candidate.json`：`0e1a2765a70184f77f4a27d80a3f3d820add873c561274b71d42efdf61f3d992`
- `modeling_checklist.json`：`91167132d73fecbf702d8b48effe9e770dc50332c12810907babec6a91a26e17`
- `requirement_audit_candidate.md`：`f9ca4f104e315d9e39a5cfcf584e0c1c460fd235aa5771933d398e397b246a55`
- `release_commands.md`：`0034ce5e6e15d6d13365295e84c66821e77352bdfd75051403fa6a32f5c178d2`

核对记录时间：2026-10-13T20:36:29.935871+00:00
