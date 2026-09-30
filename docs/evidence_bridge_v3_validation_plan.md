# Evidence BridgeTree v3：验证与版本隔离计划

日期：2026-09-30。状态：实施前只读审查与验证设计，**不是已通过验收记录**。本文件不预写测试数量、生产准确率、提交号或包校验值。核心方法由当前实施方案定义；这里规定怎样验证它没有再次把接口正确当作语义正确。

## 当前入口与最小运维改动

项目和其祖先目录没有适用的 AGENTS.md。`pyproject.toml` 要求 Python >=3.9，运行依赖为 NumPy/PyYAML；测试使用 pytest，tests 为默认发现目录，Ruff 规则为 E/F/I/B/SIM。测试不能引入 Python 3.10+ 专用语法而破坏服务器要求。

复用现有正式 executor、background manager、stop/resume/export，不增加另一套 worker 或任务注册系统。当前配置默认三方法 dense/activation/evidence_bridge、589 题，source/config/data 身份已冻结；源码 hash 已覆盖 src、reference、configs、scripts 与 pyproject，并支持无 Git 解包目录。新算法不能在 v2 run 上 resume。

| 文件/范围 | 最小更新 |
|---|---|
| `configs/evidence_bridge.yaml` | 显式写 v3 新策略参数；runtime.output_dir/cache_dir 更新到独立 v3 目录；保持基准配置和方法集合的有意选择 |
| `scripts/start_evidence_bridge_linux.sh` | 默认 `outputs/background-evidence-bridge-v3` 和 `outputs/evidence-bridge-v3`；维持完整数据预检及有限协议探测 |
| `scripts/evidence_bridge_control.py` | 与启动脚本同默认目录；JOB 保持 evidence_bridge；start/resume/source identity 逻辑复用 |
| `scripts/package_evidence_bridge.sh` | 默认新 dist 目录 `dist/evidence-bridge-v3-server` |
| `scripts/package_evidence_bridge.py` | 文件名 `bridge-tree-evidence-v3.tar.gz`、manifest.method_release=v3，REQUIRED 加入实际 v3 验证文档；明确旧 PDF 仅为 v1 背景 |
| `tests/test_evidence_bridge_operations.py` | 更新 release 文件名断言，增加默认 v3 状态与 v2 状态隔离断言；已有 detached start/stop/resume 测试复用 |
| README、implementation、runbook | 写当前 v3 行为及命令；旧 v2 验证记录只增加历史说明，不改它当时的结果与哈希 |

不得覆盖已分发 v1/v2 tar.gz、其 SHA256 或旧实验目录。新服务器目录建议 `~/bt/bridge-tree-evidence-v3-20260930`。旧任务通过**旧目录里的脚本**或显式旧 BACKGROUND_STATE_DIR 管理，不在新默认目录下误以为旧任务已经停止。沿用用户的一行命令偏好。

无需另外写一个版本身份系统：更新 prompt/policy/version 常量，已有源码与配置身份即可冻结实际运行。要测试新 source/config 无法 resume 旧 run，以及 Git 工作区与解包目录计算一致。

## 真实七题 fixture 的作用与边界

来源是本次实际 v2 export：`outputs/diagnostics/evidence_v2_20260930_logs/run`，不是 9 月 22 日旧 activation 归档。五个损失的已核实来源链见 `reports/2026-09-30-dense-evidence-audit/loss_cases_actual.json`；收益案例使用同次审计文件。

fixture 保留最小必要信息：query、实际冻结 requirements、必要的候选 Memory 及权威角色/来源偏移、原始 model mapping/selection 响应、v2 selected_ids、实际 reader context hash、原始 task ID、来源文件与响应 hash。不得把原部署密钥/端点导入 fixture，不复制整个数 GB export 进 Git/包。原始 public dataset 可以通过仓库固定文件恢复，fixture 明确它是开发/回归材料。

测试应验证**策略状态与信息流不变量**，不能用手写“正确模型回复”来宣称提示词会在真实服务上产生该回复。离线 replay 只能覆盖：旧错误响应再出现时，代码能否按 v3 明确的机制触发诊断、复核/救回或受控保留，预算和来源仍然正确；不能证明新增语义复核一定判断正确。

| 真实案例 | 回归验证要点 | 不可做的断言 |
|---|---|---|
| aa2c7800 烹饪脚本 | 给出真实全无关映射；m27“书评限制创造力”仍在初始候选，v3 不得在未记录风险/既定处理的情况下默默把空历史当成充分证据；若策略有救回路径，验证实际 reader 收到对应原始 Memory | 仅靠gold=d硬编码保留m27，或伪造covered |
| dbbd6663 flashcards | replay 真实缺历史原因的需求与m36拒绝；验证关键候选的路径状态、复核调用与真实原文进入/退出 reader 的记录；不存在凭缓存绕过调用预算 | 断言补回必然答对；把任何同主题片段标support |
| 17273334 painting | 需求r6实际存在但mapper仍拒绝m39；必须覆盖这一独立语义漏映射情形，不能只测试planner补需求；若复核仍拒绝，结果/诊断必须如实反映 | 只检查prompt含“historical”几个字就算已修复 |
| 40d94e80 图书推荐 | replay“历史没有完整推荐答案所以无关”；验证用户主题偏好可走拟议机制，空ledger/empty context与语义风险不能被normal隐藏 | 自动把泛正念历史等同关系类个性化偏好 |
| 2c7661cc romance | 验证不同历史阶段同时可追溯，数据gold/时段歧义单独标记，算法不使用gold修改历史 | 强行断言label b才是语义正确，或回归测试按b输出 |
| 56fb1ba3 meditation | v2 EB获胜却空选集；验证这类胜利被标记“无证据/不能归检索收益”，不作为救回机制正样例 | 因答案碰巧正确就认可zero-evidence策略 |
| 8f6defba cooking fact | 保留原本有效的个性化事实路径；增量修复不得破坏同源引用、角色和预算；复核额外费用可见 | 把获胜当成复杂搜索必要性的证明 |

以完整原始 Memory 为 reader 输入，测试关键文本必须查 `serialized_context` 的 memory 部分，不能只搜整个 messages：正确答案选项本身也会重复“deep learning”等文本，容易伪造“已进入上下文”的阳性。

## 必要自动验证

1. **新机制分支**：正常证据、全无关、部分无关、相关需求缺失、需求存在但映射错误、预算耗尽、源不可见、读取角色错误、救回/复核拒绝各自有明确结果；若只重试同样语义判断，测试应显示仍可能失败。
2. **来源与信息隔离**：所有进入 reader 的 Memory 必须来自题目cutoff内；复核不能引用未给出的span；gold不进入任何检索/需求/映射/选择请求；选项是否可见按v3明确契约测试，不能无意扩大权限。
3. **预算与有限执行**：新增plan/map/review/select每一次逻辑调用都计入现有总额度；为最终选择保留机会；批次分裂/修复不能重置总计数；空上下文救回/未能救回都须记录而非无限迭代。
4. **日志语义**：protocol normal与semantic status分离；有原始无关判断、关键阶段候选数量变化、审查触发原因与结果；已复核仍不确定不能伪装covered。成功/失败/回退/空历史的当前outcomes口径与summary一致，不叠加live及snapshot/retry。
5. **完整executor**：用固定小实例和脚本化backend贯通 `run_dependency_experiment`，assert真实ContextPlan、请求hash、outcome、模块日志、summary同时一致；成功resume为零新调用，改source/config拒绝resume。
6. **運维**：现有真实子进程 detached start/stop/resume 测试继续跑；新默认目录不能读取旧v2 run指针；协议探测失败禁止全量启动，preflight仍589题/1767任务/0模型调用。
7. **包验证**：先测试、Ruff、compileall、bash -n、diff check；再构建新包，逐成员内容hash对照工作区，确认无密钥、缓存、旧outputs/虚拟环境/软链接；解包后再次做0模型数据预检和源码身份一致性核对。

建议先运行改动相关测试（evidence_selection/protocol/integration/operations及新增实际fixture回归）；通过后执行一次全套pytest。新修改、失败或未解决疑点才扩大/重复相同检查，避免用重复测试堆“可靠”数字。

## 可选真实小规模 smoke

当前 `probe_evidence_protocol.py` 只用“去年春天喜欢哪种茶”执行一次planner，关闭修复；它正确地只宣称协议可用。它不会发现本次“合法但偏题的需求 + 全无关映射”。保留这个便宜的启动前检查，不把七题真实实验偷偷塞入每次一键启动。

单独的小规模开发smoke应复用现有 `load_dependency_dataset` 和 `run_dependency_experiment`，先核验完整589题数据，再显式提取预先固定的少量题目与方法。当前API通过 `examples=...`、`require_full_32k=False` 建立**synthetic/offline/subset身份边界**；即使例子取自真实数据，导出的dataset字段也标synthetic，报告必须同时注明“实际PersonaMem开发题的显式子集”，不可冒充全量正式运行。

最小代表组建议：40d94e80（推荐/空ledger）、dbbd6663（历史原因需求遗漏）、17273334（需求已有仍漏映射），dense和evidence_bridge共6任务。可扩展到全部七题14任务，但必须预先固定范围，不按答错临时加重试。其作用是观察本部署真实planner/map/复核/select/reader的全链实际响应、异常率、关键原文保留情况与成本，不是验证论文增益；这七题已经用于开发。

smoke必须新目录、独立缓存/状态，不改运行中的v2/v3配置，不向正式589题outcomes混写。无需新建完整runner：一个薄脚本调用已有executor即可，或由审计阶段使用受控Python入口。记录实际模型与服务身份、响应元数据、失败和额度；服务不可达记不可达，不假称通过、不用替身替代真实成功。

是否在正式新实验之前执行此真实smoke由任务授权与实际服务可达性决定；本次只读计划没有调用服务。代码验收文档应将“离线通过”“真实smoke通过/失败/未执行”“全量实验结果”明确分开。
