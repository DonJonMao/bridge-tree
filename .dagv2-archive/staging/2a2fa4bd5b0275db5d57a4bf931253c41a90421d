# PersonaMem v4 发布执行清单

本文件替代历史 bcbd/R17 命令；旧文件逐字节保存在
`release_commands_through_bcbd_r17.md`。以下是待执行流程，不是验收回执。

## 当前状态

- RELEASE 与 RECONCILE 均为干净提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`；306 来源字节与 Full22 完全一致。
- Full22：1938 passed、69 warnings、111.93秒；实际命令为 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`。
- R17 已自然结束且严格 gate 失败；其证据完整保留，不能作为当前验收。
- R18 已启动，PID10667，固定14题两方法，输出 `outputs/v4_validation_r18`。保持源码冻结，让整轮自然完成；不要再次 launch。
- 正式tar、准确tar安装验收及旧包清理均未执行。没有准确率提高结论。
- 代理不读标签/评分作选题、调参和结构验收；runner 在所有生成终止后自动评分。

## 当前运行观察与后续验收

以下只设置执行参数，不重新启动已运行的R18：

```bash
export DAGBT_PYTHON=/Users/mao/projects/dagv2/.venv/bin/python
DAGBT_RELEASE_REPO=/Users/mao/projects/dagv2-personamem-v4
DAGBT_RELEASE_VALIDATION=/Users/mao/projects/dagv2_analysis/personamem_v4_validation
DAGBT_RELEASE_SMOKE=outputs/v4_validation_r18
DAGBT_RELEASE_SOURCE=800c51763ea3a2bfcad459b4413d41c6432db52e
DAGBT_RELEASE_TEST_LOG="$DAGBT_RELEASE_VALIDATION/full_tests_22_discovery_restore.txt"
```

此次模型运行是独立新目录；runner不会从R17拷贝任务请求缓存。源码/配置/数据/14题身份已由 `r18_prelaunch_800c517.json` 核对。

只读观察与正式验收：

```bash
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" status --output "$DAGBT_RELEASE_SMOKE"
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/inspect_model_smoke.py" --root "$DAGBT_RELEASE_REPO" --output "$DAGBT_RELEASE_SMOKE"
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" check --output "$DAGBT_RELEASE_SMOKE"
```

要求无活跃writer、state=complete、全部28个canonical成功合法选项、14个residual终端与新鲜审计合格，以及运行源码/配置/题组/数据严格一致。日志或离线测试通过不能替代check。失败不能通过删题、换题、放宽预算/闭包或更改结果变为成功；源码若再修改，另建新运行身份。

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
