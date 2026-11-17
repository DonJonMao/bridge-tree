# R21 已推广并启动：独立只读 metadata 复核

**结论：当前四份外部文件、R20 收尾与 R21 推广/启动凭据一致；未发现中途 KeyError 导致的字段丢失或当前状态残留。没有把运行中写成模型通过、正式包已存在或发布完成。**

本次只读核对 `validation_candidate.json`、`modeling_checklist.json`、两份 candidate/release MD、三份 root receipts、Git 身份、R20 canonical rows 的状态字段和 R21 frozen manifest，并用 `ps` 确认既有 PID。未调用模型/tokenizer、未重复测试、未写源码或运行、未停止/重启、未打包/清理，未读取 labels/scores。

- **R20 真实收尾**：两 arm 各 14 个 row ID 精确覆盖固定题组；original=14 ok，residual=9 ok + 5 unresolved_or_exhausted。当前 progress 与 root gate receipt 完全相同：complete_with_failures、failed_arm_tasks=5、writer=false；实际 gate exit=1、passed=false，source=6c。未重跑 gate、改动旧 rows 或把失败消掉。
- **推广与源码**：RELEASE、RECONCILE 当前均为 clean `e6677081cdfb33c01db3aaa274a497168f314f78`；joint SHA 均为 `263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`。prelaunch receipt 记录 319 tested bytes/Git blobs、两树、105 runtime、config、固定14/public/data、旧 manifest/progress/28 rows 保持和新目录启动前不存在。本次独立再核 105 runtime 文件字节均与 candidate/新 manifest 相同；未重复 root 的全 319 blob 审计。
- **R21 真实启动**：PID/PGID 39485 在 `ps` 中为 live，命令精确使用 RELEASE config、`outputs/v4_validation_r21`、personamem、original+residual_v2、固定 IDs 文件。实际 manifest SHA 为 `825246ce7a081c6cb18be29acb56eed01247d2b10968d1a4597953b0f62c4601`，与 launch receipt、两份 JSON 一致；source/config/14 IDs/public question digest/data manifest digest 对应 prelaunch 绑定。
- **当前字段**：五份当前 model-smoke 对象完全相同，source=e667、running、PID39485、passed=false；两份 previous R20 对象完全相同，source=6c、自然失败收尾。主 source_root 已为 RELEASE，runtime_matches_release=true，release_ready=false；38 requirements 仍只是 offline passed / model gate pending。两份 MD 已改为推广/启动完成，命令仅继续 status、自然结束后 check 及条件交付，明确不可重复 smoke。
- **KeyError 恢复核验**：对比 `before_r21_launch_*`，两 JSON 均未丢失顶层 key，只新增 promotion_evidence；38 items、runtime hash map、selector 历史对象及 historical limits 均保留。checklist 在备份中本来就没有 completed_revision，当前也未虚构；其 completed_frozen_schema_revision 与 candidate 对应对象完全相同，并正确记录 running_r21_on_frozen_source。
- **历史边界**：剩余 isolated/not_started 字样只位于明确绑定 e02 的历史 selector 或历史 frontier 记录，不是当前 e667/R21 声明；6c 只表示上一版及 R20 历史。没有当前仍隔离、R21 未启动或 RELEASE 仍6c 的陈述。安装字段仍 executed=false，正式包/审批/清理仍 pending。

审查读取时的当前文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| validation_candidate.json | `a42cf6b75c1b4053981c1cb9f62e4798e0fd6b1ead44c67eacf2527f5908a1a0` |
| modeling_checklist.json | `696e535d421da7c3b4cf535628b88e3a50ab6958e77859de8d934245ce062e57` |
| requirement_audit_candidate.md | `4564a675e17814f496514cf9d2a8a0731802c5380d2790b08d0dc3f485a68f31` |
| release_commands.md | `58662257377661546a3ea9c1eb38b1936cdbb729a071fa883efc8d67a471bf10` |
| r20_root_closed_gate_receipt.json | `a21627dd9e43d994c36eb646de4363dfb48edf09b574aa2de1697566308e7dcf` |
| r21_prelaunch_e667.json | `b6df0f7614bf1593fdc0f1462837953e517ce4ed87a908dc39fccab53a696add` |
| r21_root_launch_receipt.json | `777e4e9da294c2b940fce8e9ae8b80844081f0598506d1cc4cc234ce1829039d` |

后续仅按现有流程让 R21 固定14自然完成并执行真实严格 gate；本报告不预测结果或授予模型/发布通过状态。
