# PR1–PR4 代码/PDF交付验收与服务器后续事项

按用户最新确认，本轮只完成代码修改、离线验收和 PDF，真实模型调用由用户上传服务器后执行。本轮上述交付已完成；不将尚未执行的线上实验记作已完成，也不再以本机网络和部署身份缺失阻断本轮交付。

## 交付入口

- PDF：`BridgeTree_Diagnostic_R2.pdf`，8 页；旧 15 页报告原样保留。
- 运行手册：`../../docs/diagnostic_runbook.md`。
- 需求契约：`../../docs/diagnostic_implementation_requirements.md`。
- 运行配置：`../../configs/diagnostic_28.yaml`；部署模板为 `diagnostic_deployment.example.yaml`。
- 最终交付离线运行：`../../outputs/diagnostics/2026-09-15-pr1-pr4-delivery`。
- 统一报告：该运行内 `diagnostic_report.json`；原始明细为 `offline_analysis.json`、`manifest.json`、`evaluation.json`。三个在线入口只做不带 execute 的预览，未触发线上执行或身份门禁。

最新 manifest：`7142f11ecd2207e9b5de5ce8d70e363f13ebf04507aff04ec593fc9b0e77fbb5`。

工作树源码快照：`b9e0c674653fcb3be2cd1a97b815bbef086c4327534ef7fa4d88cd508bb41f9e`。

旧 `2026-09-15-pr1-pr4`、`2026-09-15-pr1-pr4-r2` 和其中的真实门禁记录保留不改，不得用于修改后源码的在线执行。服务器路径与部署配置确定后仍须创建新的运行目录，而不是修改现有 manifest。

## 本地提交与独立验收

以下是本地 Git 提交；没有推送或创建远程 PR。四项改造分别提交，另有一项 PR3 恢复窗口补充修复，不是 PR5。最终服务器移交说明提交为 `e4bf4583ffbcd6b46676463e4efe22e90ded4f50`，只改需求/运行手册和 PDF 构建文本。

| 改造 | 提交 | 独立测试 | JUnit（位于 outputs/diagnostics/acceptance） |
| --- | --- | ---: | --- |
| PR1 身份、请求、缓存隔离及预算 | c03f959cd9b674fd188541fb7e997f7136ca1f40 | 143 | pr1-isolated.xml |
| PR2 历史恢复与预算回放 | 9e301b1fd91416888048ca0a173edc3c165b3218 | 81 | pr2-isolated.xml |
| PR3 冻结诊断执行 | cfbcc875fc35a70d7259f468c44c56f91120ef0f | 81 | pr3-isolated.xml |
| PR4 根平局顺序消融 | 252e50324be523c7e5c9080ae0949b0087086ad5 | 79 | pr4-isolated.xml |
| PR4 提交全量回归 | 同上 | 461 | full-isolated.xml |
| PR3 终止失败恢复补充修复，全量回归 | ee39aa42b26eef1e6a2676ac39f8cff1ee9a44f4 | 469 | pr3-recovery-isolated.xml |
| 最终用户工作树，全量回归 | e4bf458 加原有用户改动 | 475 | server-handoff-worktree.xml |

全部 0 failures/errors/skipped。独立验收使用各提交 detached worktree，并确认实际导入隔离 src；不是在当前工作树上模拟旧提交。工作树多出的 6 项是未混入本轮提交的原有测试。

补充修复覆盖 8 项失败日志 fsync 后、outcome 写入前崩溃的回归：不可重试失败不重发，耗尽任务次数的失败保留原错误，可重试且仍有次数才继续下一次任务尝试。相关测试仅使用假 HTTP，不冒充真实在线验证。

## 逐项需求核验

| 需求 | 当前状态 | 直接证据与边界 |
| --- | --- | --- |
| PR1 身份冻结、请求身份、审计与调用预算 | 代码及回归完成 | diagnostic_identity / request_audit / clients 测试；三阶段实际身份门禁在任何网络请求前拒绝执行。尚未定位旧 HTTP500 的服务端根因。 |
| PR2 28 子集历史评分恢复 | 真实离线完成 | 24 项历史分数、4 项缺失；绘画 7/8、音乐 13/16、读书会 4/4。每项保留字面分数来源；不补零、不混用新旧分。 |
| 真实 bundle 可达性 | 代码与归档分析完成 | 保留完整真实 bundle，跨出 U 的 B 不截成 B∩U；并集可达、正路径和 greedy 成功分别报告，缺分或未知可行性保留 unknown。 |
| 原选择器预算感知回放 | 真实离线完成 | 三例 historical_match=true；选中 IDs、停止原因、初末逻辑计费、逐轮决策、完整比较域六项全部匹配。使用原 DynamicBundleSelector。 |
| PR3 冻结评分与重复生成 | 实现及假服务回归完成；真实执行未完成 | 固定输入、顺序、部署与请求身份、预算、310 个 trial；fresh-all 与历史隔离，技术重复绕过响应缓存，gold 仅独立评价阶段读取。 |
| PR4 根顺序扰动与搜索/选择追踪 | 实现及假服务回归完成；真实执行未完成 | 默认 legacy 与修改前 golden 匹配；仅可选根平局次序，保留非根排序。没有轮询、根预算保留或新调度机制。 |
| CLI、配置及统一报告 | 已交付 | diagnostic-plan/analyze/score/generate/roots/evaluate/report；最终本地 run 实测离线和无 execute 预览，pending 与 0 次物理请求归档。旧 run 保留实际门禁证据。 |
| PDF 内容及视觉验收 | 完成 | 8 页逐页图像检查；全页 overflowPx=0，替代字符=0。包含大方向、未决算子、各 PR 性质及线上未完成状态。 |
| 不实施 PR5、保持原机制 | 满足 | 未加入 dense 保护、新 Judge、新选择器、轮询、训练；legacy 评分、选择与默认搜索行为保留。 |

## 数据与用户工作区

数据为 `bowen-upenn/PersonaMem-v1`，revision `fd7c30f071d5c2ee2a211506783be222d7b6002e`，32k split。实际文件 SHA 与固定官方文件匹配，见 `outputs/diagnostics/acceptance/data-identity.json`。

- questions SHA256：`cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c`。
- contexts SHA256：`217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a`。
- full archive SHA256：`51e5a511c198a4d14799128ef6d511204582a43c2473da387a1c394642697d53`。
- detail archive SHA256：`c040e839dc5f957596cde0632d739d60769e1ec884092829460bde62c3334c80`。

8 个原有 tracked dirty 文件的增删行与只读备份 tree `4e346ee4d50c78fa2becec6ab1dce727388d221c` 相对起点 `39efab3dd547c522c22e3739d03e9b1904661567` 的增删行一致（忽略 hunk 行号）。未 reset/stash 用户文件；报告、数据、原有未追踪测试没有打包进代码提交。未删除原归档或历史报告。

## 用户上传服务器后的执行条件

embedding、reranker、generator 的实际部署身份由用户在服务器上配置。本轮最终 run 不调用模型，task_attempt_starts=0，physical_attempt_reservations=0。310 个生成 trial 全部 pending；固定分母下当前的 0 不是测得的模型准确率。部署身份检查仍是服务器线上执行的必要条件，但不是本轮代码/PDF交付的阻断项。

服务器后续计划：28 个评分输入（最多 84 次物理传输）、310 个生成 trial（最多 930 次物理传输）、12 次根实验（最多 12,000 次物理传输，不生成）。每次根实验保留 ANN=36 和搜索/选择各 512 的逻辑唯一集合增量上限；种子 7/19/43 全部报告，不挑最好结果。

部署操作者需提供各服务 checkpoint / 权重校验值 / deployment revision 至少一种及其来源，并确认服务可用、实验期间不热切换。量化、tokenizer 和服务版本可明确标为未知，不得伪造。无需粘贴密钥；通过私有 override 配置后新建冻结运行。真实评分与重复生成结果产生后，再更新 fresh 分析、统一报告和 PDF。

机制结论仍限于方向：优先拆开相关性、证据贡献和停止依据；是否修改效用、组合优化或跨目标调度，依据受控诊断分别决定。三个事后案例不代表全体 589 题，不把技术重复视为新增独立问题。

## 恢复后只读部署核验（2026-09-15 15:33 UTC）

在用户澄清本轮只交付代码/PDF之前，检查当时配置、仓内部署说明及两份归档后，未发现真实 checkpoint、权重校验值或 deployment revision；配置 override 为空。旧 service_probes 仅有评分一致性记录，不能补充部署身份。当时 r2 manifest 与当时源码匹配；该核验记录不是最终交付 manifest 的门禁记录。

额外向三个已配置服务各发出一次只读元信息 GET：embedding/generator 查询模型列表，reranker 尝试常见 OpenAPI 路径。三次均在 5 秒内未取得响应。这个结果不能证明模型服务停机，也不能确定元信息路由存在；它意味着当前环境未能通过这条只读途径取得部署证据，还需确认可访问服务的实际运行环境。

这些不是评分、嵌入或生成请求；未发送题目与记忆，冻结实验的模型推理调用数仍为 0。完整脱敏结果见 `deployment_preflight_20260915.json`。没有修改旧 manifest、在线预算、实验结果或原算法。
