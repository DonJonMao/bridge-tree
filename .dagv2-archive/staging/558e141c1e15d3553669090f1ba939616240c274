# PersonaMem v4 release execution checklist

Candidate e6677081cdfb33c01db3aaa274a497168f314f78 passed all 2381 offline tests; all 319 worktree files and commit blobs match. R20 naturally closed with five failed arm tasks and an actual failed strict gate. RELEASE has been fast-forwarded to e667 and R21 is live (PID 39485). No source approval, official archive build, final installation or deletion has occurred.

Completed startup evidence: r20_root_closed_gate_receipt.json, r21_prelaunch_e667.json and r21_root_launch_receipt.json. These bind the natural R20 closure, clean e667 promotion, 319 tested files, 105 runtime files, unchanged config/fixed14/public data, absent new output before launch, and the actual R21 writer. Launch is complete; do not run smoke again for this output. The parameters below are retained for status, later strict gate and conditional delivery.

```bash
export DAGBT_PYTHON=/Users/mao/projects/dagv2/.venv/bin/python
DAGBT_RELEASE_REPO=/Users/mao/projects/dagv2-personamem-v4
DAGBT_RELEASE_VALIDATION=/Users/mao/projects/dagv2_analysis/personamem_v4_validation
DAGBT_RELEASE_SMOKE=outputs/v4_validation_r21
DAGBT_RELEASE_SOURCE=e6677081cdfb33c01db3aaa274a497168f314f78
DAGBT_RELEASE_TEST_LOG="$DAGBT_RELEASE_VALIDATION/full_tests_26_frozen_ids_schema.txt"
```

The source must remain frozen while R21 runs. Poll the existing output; do not stop/restart on ordinary failures or reuse it for a new run:

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_REPO/scripts/personamem_v4.py" status \
  --output "$DAGBT_RELEASE_REPO/$DAGBT_RELEASE_SMOKE"
```

Let all 14 questions finish naturally. After the writer stops, execute this strict check on the same source/config/output. A failure must be retained and investigated; it does not permit approval or building:

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_REPO/scripts/personamem_v4.py" check \
  --config "$DAGBT_RELEASE_REPO/configs/personamem-v4.json" \
  --output "$DAGBT_RELEASE_REPO/$DAGBT_RELEASE_SMOKE"
```

Only after the actual strict fixed14 gate passes may the following source-approval, build, exact-archive installation and reviewed-cleanup commands execute. The final source must be clean and match its complete offline receipt and successful model manifest; never substitute stale/dummy approval or alter a failing run.

```bash
DAGBT_RELEASE_TAR=/Users/mao/projects/dagv2_deploy/20261013_personamem_v4/dagv2_personamem_v4.tar.gz
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/prepare_source_approval.py" \
  --root "$DAGBT_RELEASE_REPO" \
  --candidate "$DAGBT_RELEASE_VALIDATION/validation_candidate.json" \
  --full-test-log "$DAGBT_RELEASE_TEST_LOG" \
  --smoke-output "$DAGBT_RELEASE_SMOKE" \
  --config configs/personamem-v4.json \
  --expected-commit "$DAGBT_RELEASE_SOURCE" \
  --output "$DAGBT_RELEASE_VALIDATION/source_approval_final.json"
"$DAGBT_PYTHON" "$DAGBT_RELEASE_REPO/scripts/build_personamem_v4.py" \
  --output "$DAGBT_RELEASE_TAR" \
  --validation-file "$DAGBT_RELEASE_VALIDATION/source_approval_final.json" \
  --private-credentials "$DAGBT_RELEASE_REPO/configs/credentials.local.json"
```

建包器动态枚举Git提交，检查每项blob并扫描凭据；新增文档/测试不可遗漏。凭据仅以私有文件路径交给扫描器，不打印或打进包。源码审批只证明允许建包，尚不证明该tar安装成功。

## 准确tar安装验收与授权清理

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/verify_final_archive_install.py" \
  --archive "$DAGBT_RELEASE_TAR" \
  --output "$DAGBT_RELEASE_VALIDATION/final_archive_installation.json" \
  --base /Users/mao/projects/dagv2-personamem-a48 \
  --source-repo "$DAGBT_RELEASE_REPO" \
  --python "$DAGBT_PYTHON" \
  --expected-commit "$DAGBT_RELEASE_SOURCE" \
  --private-credentials "$DAGBT_RELEASE_REPO/configs/credentials.local.json"
```

验证同一个最终tar及相邻sha256、提交blob、两次幂等隔离安装、57项冻结资产、三个向量独立inode、0600本地凭据、实际inspect_index及wrapper状态/help；不调用网络。临时目录/凭据移除，旧base和共享索引的内容/权限/mtime/inode不变。安装记录的passed必须为true。不得为嵌入安装回执重建另一个未验收tar。

cleanup review锁定SHA256：`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`。先实际核对dry-run，再执行已经授权的精确清理：

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/execute_reviewed_cleanup.py" \
  --review "$DAGBT_RELEASE_VALIDATION/cleanup_review.json" \
  --install-receipt "$DAGBT_RELEASE_VALIDATION/final_archive_installation.json" \
  --output "$DAGBT_RELEASE_VALIDATION/cleanup_dry_run_final.json"
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/execute_reviewed_cleanup.py" \
  --review "$DAGBT_RELEASE_VALIDATION/cleanup_review.json" \
  --install-receipt "$DAGBT_RELEASE_VALIDATION/final_archive_installation.json" \
  --output "$DAGBT_RELEASE_VALIDATION/cleanup_execution_final.json" \
  --execute
```

保留14份metadata，再删除清单内14个旧归档/校验文件及3个staging根。保留唯一的旧实验诊断包、源码工作树、日志及无关Downloads包；禁止通配清理。若有新文件或哈希变化，停止并核查实际变化，不绕过核对。最终对交付tar/hash/安装/清理逐项验收后才声明完成。



Historical R20/6c evidence: all 28 rows are retained after natural completion; original 14 ok, residual 9 ok and 5 unresolved, strict gate exit 1, no tokenizer failure. Two saved old requests had a +9-token review representation regression; e667 now selects review only on a strict actual-token reduction. The first failed R20 case used no sharing codec, so that issue is not its demonstrated cause. Fourteen historical metadata files (276682 bytes) were copied and independently verified. No archive, staging root, unique diagnostic or source worktree has been deleted; the final-archive installation gate remains mandatory.
