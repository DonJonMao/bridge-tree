> 当前状态：RELEASE 保持 `bcbd16f`，R17 已自然结束并失败；RECONCILE 基于 `8dac32b` 实施新的探索前沿修正。1880 项测试仅验证 8dac 旧字节，新修正尚未完成验证。下文 bcbd/R17/full19/301 文件命令保留为历史记录，不能审批新候选。必须先绑定最终提交、实际全套测试和新的 R18；当前不得执行正式建包、最终安装或清理。

# PersonaMem v4 最终发布执行清单

2026-10-14，发布准备清单。本文件中的建包、安装验收、清理命令尚未执行。

当前 release 和 reconcile 均为干净提交 `bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`。
该快照离线全套 1838 passed、69 warnings、106.30 秒
（`full_tests_19_shared_history.txt`，SHA256
`601197544b1f875de34f4a103afafc2096a403e8d0c57249fd599b4588102df1`）。
测试前后、提交 blob 及集成后 release 共 301 个文件一致。
源码已集成组合/审计的完整必要证据范围、失败输出的逐变量调用授权、冻结观察修复规则
和显式审计 verdict 契约。本次增加无损共享历史文本输入表示，并统一终端修复的
准入/发送 schema；没有放宽 16k、固定题组、调用预算或成功门槛。

R15 已在旧提交 `50d1ba0b2edb623384e51ac42ea12b36e5b69229` 上自然结束：
original 14 个 ok；residual 3 个 ok、9 个 unresolved_or_exhausted、1 个 audit_incomplete、
1 个 execution_failed。全部 28 行已验证并归档，严格 check 未通过。
旧结果仅属于旧源码，不能用于证明新源码通过；未读标签或计算准确率。

R16 已在旧提交 `b9e28a7faa8d419f9f1283574fa095399919c243` 上自然结束并封存：
original 14 个 ok；residual 6 个 ok、7 个 unresolved_or_exhausted、1 个 execution_failed。
`state=complete_with_failures`、`live_writer=false`、8 个失败任务；全部 28 个 canonical rows
及其 103 项运行源码身份核对正确，但严格 gate 失败。闭合证据见
`r16_reader_closed_run_receipt.json` 和 `r16_validation_candidate_closed.json`，不是新源码验收。

只有确认 R16 已结束后，才将 `bcbd16f` 快进集成到 release 并启动 R17。
本次更新时核实 PID 96297 存活，固定 14 题、两个方法、相同配置；实际输出为
`outputs/v4_validation_r17`，manifest 的 104 项运行来源含新增 `dagbt/history_wire.py`，
并与当前候选完全一致。两工作树继续冻结，本轮尚未通过真实模型门槛。
`reconcile_bcbd16f_validation.json` 和 `r17_prelaunch_bcbd16f.json` 记录本次源码与预启动核验；
当前候选状态以 `validation_candidate.json` 和实际 R17 输出为准。
不要因这里记载了当前源码和实验目录就执行建包或清理。最终提交、全套日志和输出目录均须绑定实际
最后通过的轮次；若后续修改源码，必须使用新实验目录重新验证。
`validation_candidate.json` 的 R17 状态为 running、live_writer=true，保持
`release_ready=false`。**目前不能建包、安装验收或清理；没有正式 tar 或删除操作。**

## 1. 已补正文档与最终核对

whole-value、失败恢复以及显式 summary revision 边界已写入当前正式 README，包含
旧路径/版本、保留负面经历、反证失效传播及不适用于普通事实/终端选项。
README 也明确 PersonaMem-v1 使用 32K 历史版本，16384 是单请求总容量；新增共享文本
只改变无损输入表示，计入解码指令后按 byte 判断候选，实际容量仍由部署 tokenizer 检查。
以下是边界对照，不再是待重复追加的文案。后续源码变化仍需对照实际提交与测试。
本次没有修改该 README，也没有修改 reader/contract/control 源码。

历史变量与整值复核边界：

> 历史变量只描述与当前问题相关、可由来源支持的事实。开放历史优先使用简短文本
> 摘要；集合变量必须有明确的完整集合边界。多个局部集合或不同文本草稿不能自动
> 并集或覆盖为一个完整值；出现歧义时，必须带原始来源进行有界联合复核。历史上的
> 喜欢、不喜欢及后续变化都可能是有效事实；只有挑战已有事实路径时才使用反证撤回。

失败记录恢复边界：

> 失败读取保留原始草稿、必要原文、已有有效反证及失败范围。仅历史检索/历史汇总
> 阶段，在同一任务与阶段出现新原文或实际父绑定变化后，才允许在现有模型调用和
> JSON 修复预算内显式复核；换查询标识或恢复 checkpoint 不会重置修复资格。
> 只有本次获准复核的失败记录完整通过来源、反证及下游容量检查，才原子解除该记录，
> 同变量其他失败记录继续保留。终端选择或审计失败不能由历史复核代替清除。
> 当前不把多次不完整的上下文分片累计视为一次完整复核；必要原文不能在单次上下文
> 容纳时，仍可能保守失败，不会通过丢弃来源或反证获得成功状态。

以上边界已由 reader 实现负责人确认：恢复还占用当前请求的 `max_repairs_per_request`，
消耗全局 `json_repairs` 与正常 LLM 预算；无关 program revision 不重置资格。
最终 README 不要承诺“所有失败可恢复”“全部已修复”或“准确率已提升”。

现有 CLI/README 操作命令无需因恢复语义变化增加参数。仍是
`original` 对 `dagbt_residual_memory_v2`，固定 14 道公开 smoke 题，16k context。
`check`/`full` 的验收条件继续要求两组所有行成功、合法选项，以及 residual 语义终值
与审计通过；不应放宽成部分通过。

## 2. Receipt 各自负责什么

### 源码与模型验收记录（打包输入）

建包器 `scripts/build_personamem_v4.py:37` 只强制检查：源码工作区干净、基线祖先正确、
输入记录 `release_ready=true`、`source_commit` 等于完整 HEAD，以及凭据扫描。
它不会自行执行 smoke，也不会验证记录中写的测试结果；root 仍须核对真实证据。

以 `source_approval_final.json` 作为最终打包输入，至少记录：

| 字段 | 应有证据 |
| --- | --- |
| `source_commit` | 最终完整 40 位提交，与建包 HEAD 一致 |
| `release_ready` | 只有该源码离线检查及模型 smoke 均通过才为 true |
| `scope` | 明确这是源码/模型通过、允许打包；实际 tar 安装和清理另有外部记录 |
| `source_hashes` | 与通过的 smoke manifest 和当前 `runner.frozen_sources()` 相同 |
| `config_sha256` | 最终 `configs/personamem-v4.json` 的字节哈希 |
| `offline_tests` | 最终源码测试的命令、退出码、passed/warnings、日志路径及 SHA256 |
| `model_smoke` | 实际 output、14 题、两个方法、`state=complete`、`live_writer=false`、`passed=true`、`check` 结果及证据哈希 |
| `model_smoke.labels_used_for_selection` | false，题目来自固定公开题型顺序 |
| `release_pending` | 如尚未进行，明确列出实际 tar 安装验收与旧包清理；不伪造已完成 |

建议同时记录 smoke 的 manifest/progress/current rows 文件摘要，保留原运行目录。
不能在最终包中放入密钥、完整 prompts、历史原文日志或评测内部中间态。

注意当前字段命名：建包输入的 `release_ready=true` 是允许打包的门槛，并非已经完成
实际 tar 的安装验收。实际 tar 安装证据只能在 tar 生成之后形成，须外置；不要为了把
安装记录嵌入 tar 而重建一个未经同样验收的新 tar。

### 实际 tar 安装验收记录

`verify_final_archive_install.py` 生成
`schema=dagv2_final_archive_installation_review_v1`，且始终 `release_ready=false`。
这并不表示安装失败；它仅负责安装，使用 `passed` 表示结果。

cleanup 必需这些字段为 true：

- `passed`
- `tar_manifest_verified`
- `committed_source_bytes_verified`
- `idempotent`
- `packaged_artifacts_unchanged`
- `wrapper_status_and_help_verified`
- `temporary_extraction_and_credentials_removed`
- `base_content_mode_mtime_inode_unchanged`
- `shared_index_content_mode_mtime_inode_unchanged`

还要求 `network_attempts=0`，存在准确的 `archive`、`archive_bytes`、`archive_sha256`、
`source_commit`；实时重新核对 tar、相邻 `.sha256`、tar 内 DEPLOYMENT 的提交及源码审批。

验收器还检查实际解包文件集/大小/哈希和 Git blob、两次真实 wrapper install、
57 项冻结文件、3 份向量独立 inode、0600 本地凭据、生产 `inspect_index`、共享索引
身份/向量哈希、wrapper status/help、凭据未进入包/输出/receipt，最后清除临时目录。

### 清理与最终交付记录

cleanup dry-run 应为 `status=verified_dry_run_no_copies_or_deletions`、`completed=false`。
执行记录应为 `schema=dagv2_reviewed_cleanup_execution_v1`、`status=completed`、
`completed=true`、14 份 metadata 已保留、14 个旧 tar/sha 文件删除、3 个 staging 根删除，
且 `scientific_logs_deleted=false`、`source_worktrees_deleted=false`。

最终交付状态另写外部 `final_delivery_receipt.json`，引用源码审批、真实安装记录、清理
记录及各自 SHA256；只在这些实际完成后报告交付完成。现有工具不会自动生成该总记录。

## 3. 准确命令（root 按门槛顺序执行）

以下命令使用 bash。命令示例指向正在运行、尚未通过的 `v4_validation_r17`。
这不表示当前已有结果可发布。若最终通过的是更新轮次，先把
`DAGBT_RELEASE_SMOKE` 改为该真实目录。
所有 receipt/正式 tar 路径应为新路径；工具拒绝覆盖既有文件。已经针对相同冻结
源码完成的测试不必重复，只引用真实日志。

```bash
export DAGBT_PYTHON=/Users/mao/projects/dagv2/.venv/bin/python
DAGBT_RELEASE_REPO=/Users/mao/projects/dagv2-personamem-v4
DAGBT_RELEASE_VALIDATION=/Users/mao/projects/dagv2_analysis/personamem_v4_validation
DAGBT_RELEASE_SMOKE=outputs/v4_validation_r17
DAGBT_RELEASE_TEST_LOG="$DAGBT_RELEASE_VALIDATION/full_tests_19_shared_history.txt"
DAGBT_RELEASE_TAR=/Users/mao/projects/dagv2_deploy/20261013_personamem_v4/dagv2_personamem_v4.tar.gz
DAGBT_RELEASE_SOURCE="$(git -C "$DAGBT_RELEASE_REPO" rev-parse HEAD)"
test -z "$(git -C "$DAGBT_RELEASE_REPO" status --porcelain --untracked-files=normal)"
test "$DAGBT_RELEASE_SOURCE" = bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94
git -C "$DAGBT_RELEASE_REPO" merge-base --is-ancestor a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1 "$DAGBT_RELEASE_SOURCE"
```

最终源码冻结、完整测试通过、candidate 绑定该提交及真实测试日志后，在新目录启动一次
固定 smoke（不会更改为两题或单方法）。以下是 R17 已执行的启动命令，仅保留为记录，
**不要再次执行**；后续若有新源码，必须另用新的输出目录和源码/测试绑定：

```bash
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" smoke --output "$DAGBT_RELEASE_SMOKE"
```

实际实验创建后，只读查看 smoke，随后用正式 CLI 验收；观察工具不能替代 `check`。
当前 R17 可只读查看；运行中或存在失败题时不能验收通过：

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/inspect_model_smoke.py" \
  --root "$DAGBT_RELEASE_REPO" --output "$DAGBT_RELEASE_SMOKE"
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" status --output "$DAGBT_RELEASE_SMOKE"
bash "$DAGBT_RELEASE_REPO/scripts/personamem_v4.sh" check --output "$DAGBT_RELEASE_SMOKE"
```

收到 `check` 的 `status: passed`，且最终离线测试及源码审查通过后，使用既有严格验证器
生成上文的 `source_approval_final.json`。先将 `DAGBT_RELEASE_TEST_LOG` 设为最终
`validation_candidate.json.offline_tests.report` 所指的真实全套日志绝对路径，不能指向旧轮次。
验证器重新检查 clean commit、候选/配置/冻结来源、全部 28 行和生产 gate；不是直接改 true。

```bash
: "${DAGBT_RELEASE_TEST_LOG:?请设置最终冻结源码的真实全套测试日志路径}"
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/prepare_source_approval.py" \
  --root "$DAGBT_RELEASE_REPO" \
  --candidate "$DAGBT_RELEASE_VALIDATION/validation_candidate.json" \
  --full-test-log "$DAGBT_RELEASE_TEST_LOG" \
  --smoke-output "$DAGBT_RELEASE_SMOKE" \
  --config configs/personamem-v4.json \
  --expected-commit "$DAGBT_RELEASE_SOURCE" \
  --output "$DAGBT_RELEASE_VALIDATION/source_approval_final.json"
```

建正式 tar（必须先通过全部上述门槛；R17 当前运行中，**现在不能执行**）：

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_REPO/scripts/build_personamem_v4.py" \
  --output "$DAGBT_RELEASE_TAR" \
  --validation-file "$DAGBT_RELEASE_VALIDATION/source_approval_final.json" \
  --private-credentials "$DAGBT_RELEASE_REPO/configs/credentials.local.json"
```

该凭据路径当前存在且属于忽略文件，只传文件路径，切勿打印文件或 key。
建包器从提交 blob 构建、扫描整个包、重新解包逐字节校验，再输出 tar 与 SHA256。

使用实际 tar 做两次隔离安装验收（会建立并删除临时解包目录；不调用网络）：

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

只有安装记录 `passed=true` 才继续。清理复核固定 SHA256 为
`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`。
不要手动改清单、换 hash 或用递归删除替代工具。

先 dry-run（只写新的 dry-run receipt，不复制、不删除）：

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/execute_reviewed_cleanup.py" \
  --review "$DAGBT_RELEASE_VALIDATION/cleanup_review.json" \
  --install-receipt "$DAGBT_RELEASE_VALIDATION/final_archive_installation.json" \
  --output "$DAGBT_RELEASE_VALIDATION/cleanup_dry_run_final.json"
```

dry-run 清单核验通过后，执行已经授权的精确清理：

```bash
"$DAGBT_PYTHON" "$DAGBT_RELEASE_VALIDATION/execute_reviewed_cleanup.py" \
  --review "$DAGBT_RELEASE_VALIDATION/cleanup_review.json" \
  --install-receipt "$DAGBT_RELEASE_VALIDATION/final_archive_installation.json" \
  --output "$DAGBT_RELEASE_VALIDATION/cleanup_execution_final.json" \
  --execute
```

工具会先复制验证全部 14 份 metadata 到 `historical_deployments/`，再复核新包和旧包
清单，逐文件 unlink、仅对空目录 rmdir。遇到新文件、哈希变化、已存在 receipt 或新包
身份变化会停止；不能绕过失败继续删。中断后保留增量执行 receipt，先审查已完成项。

## 4. 此次只读审查的结论

- 建包、实际 tar 验收、cleanup 的命令与参数相互匹配；没有发现需要更换命令名的变化。
- 当前提交的 README 已明确整值复核、历史失败记录恢复与 summary revision 边界，
  没有把普通事实或终端选择扩大为可随意修订摘要。
- `runner.frozen_sources()` 覆盖运行模块及 CLI，但不涵盖 README、installer/build 脚本；
  因此应冻结整个最终提交再验收，不能仅凭 `check` 通过推断所有发布脚本未变。
- `validation_candidate.json` 当前对应 `bcbd16f`，保留 `release_ready=false`，记录
  1838 条离线通过和 R17 运行中状态。源码、测试和实际模型 manifest 已绑定；仍须等待
  完整模型结果，不能把离线通过或 R15/R16 旧源码结果作为 R17 已通过的证据。
- 当前提交动态枚举为 301 个普通源码 blob，共 76,131,068 字节；含新增
  `dagbt/history_wire.py` 和两个回归测试。建包器与实际安装验收器都通过
  `git ls-tree -rz --full-tree` 枚举指定提交，并按 blob 校验，不需要修改固定文件清单。
  `runner.frozen_sources()` 递归覆盖 `dagbt/`，实际 R17 manifest 已含新增模块哈希。
  预计正式包为 301 项源码加两项生成 metadata；实际 tar 仍须完整安装验收。
- 正式 tar 当前不存在，实际 tar 安装与 cleanup 均未执行；本文件不是完成 receipt。

## 5. Summary revision 历史发布兼容性复核

本节保留此前 `74d2657` 与 `c10c6da` 的静态复核，不代表当前候选已验收。
当时对照的 build/install/CLI/wrapper、
`configs/personamem-v4.json`、`original_manifest.json` 的字节均相同。冻结文件仍为
57 项，其中 3 项 `.npy` 由安装器复制。没有为 summary revision 新增安装依赖、
包层级、索引类型或凭据字段。

验收器从新提交动态枚举 Git 文件，并将 tar 每项与该提交 blob 核对，因此新增
`dagbt/personal_wire.py` 与回归测试不需要改变验收器的文件清单或参数。当时 281 个
Git 文件均符合现有打包路径/对象要求，该模块已提交，并由 `runner.frozen_sources()`
的 `dagbt/` 递归纳入运行身份。`source_approval_final.json.source_commit` 必须与最终
通过模型验收的 HEAD 完整一致。

summary revision 的声明和路径状态位于运行计划/结果中，不改变安装验收器消费的
DEPLOYMENT/VALIDATION schema，也不改变 cleanup 的安装门槛。cleanup_review 的
锁定 SHA256 仍为 `f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`。

当时的结论是构建、真实 tar 双安装验收器及精确 cleanup 计划适配，不需放宽门槛；
两个验证/清理脚本通过 AST 语法解析，cleanup review 的锁定哈希未变。
本次只重新核对文中脚本参数与现有 CLI 声明一致，没有执行建包、安装或清理。
当前新提交的 R17 正在运行；R16 已失败闭合，正式 tar 和实际安装/清理记录仍不存在。
最终须以新冻结源码的真实通过证据按上文推进，不能用历史兼容性结论
替代最终包验收。

## 6. 剩余关键路径与耗时边界

1. 新源码冻结与完整离线测试已完成；当前实际全套耗时 106.30 秒，引用 tests 19 日志。
2. 固定 14 题 × 2 方法真实 smoke 全部完成并通过 gate。这是当前主要阻塞和不确定耗时；
   首题或部分题通过不能替代它，也不能拼接不同源码轮次的结果。
3. 严格源码审批、正式 tar/SHA256，再对同一个 tar 完成两次实际隔离安装和外部安装 receipt。
4. 安装 `passed=true` 后 cleanup dry-run，再执行精确清理；最后写外部交付 receipt 并提供包和校验值。

当前配置单次模型请求 timeout 600 秒、相同请求最多 3 次尝试、单题 timeout 3600 秒、
worker 启动 timeout 300 秒、tokenize timeout 15 秒；这些是失败边界，不是整轮完成时间承诺。
不能为了缩短等待而调低 gate 或改变本轮预算。实际包验收的每个子进程 timeout 为 180 秒；
整个流程还包含 tar/冻结文件/共享索引的读取、复制与哈希，没有经过此次实际包运行的耗时数据。

本次只读确认：正式 tar、源码审批、安装、cleanup dry-run/execute、最终交付 receipt 均不存在；
cleanup review 锁定 SHA256 未变。此次文档更新没有启动额外模型、建包、安装或清理。
R17 是此前已启动且仍存活的进程，R16 的失败结果已封存。当前没有新确认的发布脚本接口阻塞，后续步骤尚未完成
是因为真实 smoke 门槛仍待通过。
