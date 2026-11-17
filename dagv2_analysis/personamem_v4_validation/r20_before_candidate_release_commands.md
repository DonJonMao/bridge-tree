> 最新状态（2026-10-14）：R19 已自然结束，27/28 失败，严格验收退出 1。原版 1 ok/13 服务失败，新方法 2 unresolved/12 服务失败；新隔离表示修订定向 226 通过，Full24 正在运行，尚无全套通过结论。下文旧 R19 running 描述是启动时记录，不能视为当前状态。正式包/安装/清理未执行。

# PersonaMem v4 发布执行清单

本文件绑定当前 0cc2cc7 / Full23 / R19。前版已保存为 `r19_before_running_release_commands.md`。
以下未执行的发布命令不能视为验收回执。

## 当前状态

- RELEASE clean 0cc2cc78498bcd215252fb8e82d2168868a71b3f；312 文件与 Full23 字节一致。RECONCILE 正在实施新的无损表示修订，尚未验收。
- Full23：2020 passed、69 warnings、109.93秒；完整实际命令 `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`。
- R18 在旧源码自然失败：original14ok、新方法12ok/2failed；严格 gate 退出1。证据保留，不复用为新源码验收。
- R19 已启动，启动核对 PID21059、writer=true，回执 `r19_root_launch_receipt.json`。已出现自然失败与服务超时，全轮仍待自然结束，release_ready=false。本轮不能批准发布；新修订最终通过后必须重新绑定以下源码/测试/运行参数。
- 正式tar、同一tar安装验收、清理均未执行。没有准确率提高结论。
- 代理不读标签/评分作选题、调参或结构验收；runner 在全部生成终止后自动评分。

## 当前运行观察与后续验收

```bash
export DAGBT_PYTHON=/Users/mao/projects/dagv2/.venv/bin/python
DAGBT_RELEASE_REPO=/Users/mao/projects/dagv2-personamem-v4
DAGBT_RELEASE_VALIDATION=/Users/mao/projects/dagv2_analysis/personamem_v4_validation
DAGBT_RELEASE_SMOKE=outputs/v4_validation_r19
DAGBT_RELEASE_SOURCE=0cc2cc78498bcd215252fb8e82d2168868a71b3f
DAGBT_RELEASE_TEST_LOG="$DAGBT_RELEASE_VALIDATION/full_tests_23_planner_handoff.txt"
```

R19 实际 manifest104源码、配置、固定14题、公开题目摘要和数据清单已核对，新输出不借用旧任务缓存。

```bash
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" status --output "$DAGBT_RELEASE_SMOKE"
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/inspect_model_smoke.py" --root "$DAGBT_RELEASE_REPO" --output "$DAGBT_RELEASE_SMOKE"
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" check --output "$DAGBT_RELEASE_SMOKE"
```

让整个固定14题自然结束，不因普通失败提前停止。要求 writer=false、state=complete、28条成功合法记录、14条真实终端和新鲜完整审计及源码/配置/题组/数据一致。失败不可通过删换题、提高预算或修改结果绕过；源码再变更必须使用全新验证身份。

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
