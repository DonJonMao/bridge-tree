> 独立修订进行中：RELEASE保持6c04637/R20冻结；RECONCILE正在实现review候选的实际token非增选择。现有2194全套证据只适用于6c04637，不代表新修订已验收。

# PersonaMem v4 发布执行清单

## 当前状态

候选 `6c046374008ce2e45f817d6bc9876b3ab927ab18` 已完整离线2194通过并提交；RELEASE已fast-forward并核对全部315测试文件与105运行源码，旧R19失败输出保留。新候选尚未真实验证，release_ready=false。R19已自然结束27失败，实际严格gate退出1。两服务最新TCP及实际计数接口检查成功；R20已实际启动并确认writer PID26942。

## 当前运行与验收

源码提升、315测试字节和105运行源码、配置、固定14、公开数据核对均已执行。实际启动回执 `r20_root_launch_receipt.json` 确认writer PID26942与manifest绑定。保持源码冻结，让整轮自然结束；不要重复执行启动命令或借用旧轮次结果。

```bash
export DAGBT_PYTHON=/Users/mao/projects/dagv2/.venv/bin/python
DAGBT_RELEASE_REPO=/Users/mao/projects/dagv2-personamem-v4
DAGBT_RELEASE_VALIDATION=/Users/mao/projects/dagv2_analysis/personamem_v4_validation
DAGBT_RELEASE_SMOKE=outputs/v4_validation_r20
DAGBT_RELEASE_SOURCE=6c046374008ce2e45f817d6bc9876b3ab927ab18
DAGBT_RELEASE_TEST_LOG="$DAGBT_RELEASE_VALIDATION/full_tests_24_review_wire.txt"
```

源码和预启动记录见 `r20_prelaunch_6c04637.json`，实际运行见 `r20_root_launch_receipt.json`。自然结束后要求writer=false、state=complete、28合法成功行、14真实语义终端与新鲜完整审计、源码/配置/数据一致。失败不得通过删换题、加预算或改结果绕过。

## 通过后才允许建包

`DAGBT_RELEASE_SOURCE` 必须设成最后通过源码的完整提交；`DAGBT_RELEASE_TEST_LOG` 必须指向绑定该提交字节的真实全套日志。用候选实际记录填值，不能沿用历史轮次。审批器会重新核对clean HEAD、日志、运行及28行，不是直接把release_ready改true。

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


最新补充：R20已记录首题未解失败，仍让固定14题自然结束；当前不能批准发布。两个旧修复请求实测新review表示各增加9输入tokens，不能以字节减少宣称容量改善；首题实际未使用共享codec，不能混同归因。14份历史metadata已预先保全并独立核对（276682bytes），原归档/staging/诊断/source均未删除；最终tar安装gate保持。
