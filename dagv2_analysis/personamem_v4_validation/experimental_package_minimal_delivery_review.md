# 冻结 e667 实验包的最小交付路径

**可直接交付诚实标为实验用途的可复现包，不必等待 14/14 模型全成功。现有安装器无需修改；旧正式发布门槛不能靠伪造 release_ready 绕过。** 本结论遵从用户最新“算法能测试即可”的范围，保持 RELEASE/RECONCILE 与运行中的 R21 源码冻结。

本次仅阅读四份指定脚本及 wrapper 接口；未改 repo、打包、安装、调用服务、运行测试或清理。

| 组件 | 实际字段依赖 | 实验包结论 |
| --- | --- | --- |
| `build_personamem_v4.py` | clean commit；`validation.release_ready is True`；`validation.source_commit==HEAD`；Git blob、私密值扫描、逐文件 hash 与归档 round-trip | 不能原样接收诚实 false 的实验 metadata；用外部实验 packager，保留源码/凭据/字节检查，只使用明确实验身份。 |
| `install_personamem_v4.py` | DEPLOYMENT.files 完整逐文件 size/hash；必须包含 config/original_manifest；资产/config/index/本地凭据校验 | **没有要求 release_ready=true**，也没有要求模型成功。维持现有 manifest/files 格式即可原样安装。release_name 仅用于返回展示。 |
| `verify_final_archive_install.py` | package files/hash/真实 commit；validation 与 DEPLOYMENT 内副本一致；硬要求 `release_ready is True` | 旧脚本属于正式发布验收，不能直接称实验包通过它。若复用，做外部实验身份适配，保留相同 tar 字节/安装核查，输出独立实验安装 receipt。 |
| `execute_reviewed_cleanup.py` | 正式安装 receipt schema、九项通过标志、原包及checksum不变；再次硬要求 manifest.validation.release_ready=true | 实验包不满足旧正式清理门槛。无需为“算法能测试”改造或执行此脚本；旧包清理不应成为本次交付前提。 |

建议 root 采用这条短路径：

1. 从 clean e667 的 Git blobs 生成独立实验 tar 和 SHA256，继续排除 `.local.json`、向量、outputs、缓存、嵌套归档，并扫描已知私密值。保留原 319 个来源文件，附同名 `VALIDATION_PERSONAMEM_V4.json`、`DEPLOYMENT.json`；后者 `files` 对所有包内文件逐项记 hash，不包含自身。
2. metadata 使用 `package_kind: experiment`（同时放入 manifest 和 validation）、`release_name: personamem-v4-experiment`、真实 e667 source_commit、`release_ready:false`。诚实记录 offline 2381 passed；上一版 R20 source=6c、original 14 ok、residual 9 ok/5 unresolved；本版 R21 source=e667、running、passed=false。这些是打包时快照，不是准确率或模型通过结论。
3. 对**最终这个 tar**核对 checksum、manifest/source blobs，然后在独立临时目录用原 installer 做一次实际离线安装，确认资产/index/凭据准备及 wrapper status/help 可用。安装 receipt 明确 schema/用途为实验包安装验证，`passed` 只表示安装检查实际通过，`release_ready` 继续 false。不需为交付重复整套算法测试或等固定14全成功。已有验包器如复用，应仅允许明确实验身份+false，绝不能先把 false 改 true。
4. 同时交付简短运行说明：安装后用现有通用 runner 开始新输出目录的实验，状态/诊断照常记录失败。R21 可以在冻结源码下继续自然运行，后续结果另补，不回填打包时的事实。

一个实际入口细节：包内 `scripts/personamem_v4.py full` 仍先执行严格 `check_smoke`，不能把它作为这次“可测试算法”的唯一入口。无需改冻结 wrapper，使用现成的通用命令：

```bash
"$DAGBT_PYTHON" -m dagbt.runner launch \
  --config configs/personamem-v4.json \
  --datasets personamem \
  --arms original dagbt_residual_memory_v2 \
  --output outputs/personamem_v4_experiment_full
```

该命令从实验包 `dagv2` 目录运行；不传 limit/question IDs 即为全量。固定预算、算法内部来源/结果验证与失败计数保持原样，只是不把 14/14 smoke 当成用户开展实验的前提。若用户想先小测，可对通用 runner 使用明确的小 limit 和不同 output，失败如实查看，不伪称全量验收。

运行说明宜作为 tar 外的并列交付文件，避免再改源码。若 root 选择放入 `dagv2` 根，必须在 DEPLOYMENT.files 登记为 generated artifact；否则原 installer 会因 `Unmanifested release artifact` 拒绝。严谨但冗长的既有正式发布/清理说明无需继续阻塞实验包交付。
