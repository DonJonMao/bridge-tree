# 后台诊断服务交付验收

日期：2026-09-16。代码提交：`2d2f48e`（本地提交，未推送）。

## 实际验证

- 当前工作树：562 tests，0 failures/errors，`outputs/diagnostics-background-acceptance/worktree.xml`。
- 独立提交副本：556 tests，0 failures/errors，`outputs/diagnostics-background-acceptance/committed-isolated.xml`。差额来自原有未提交测试与工作树变动，不把它们混入本次提交。
- 真正的本机 detached 后台离线启动和 resume 完成；使用真实两份归档，历史分数仍为 24/28，4 项缺失保持缺失。
- 离线 run：`outputs/diagnostics-background-check/diagnostic_20260916_001005_813a7e4b`。
- manifest：`a9df55e7fffad55756896aee606077b96e7e7c2ca49f25902e1887251cc5484b`。
- 真实 embedding / reranker / generator 调用：0。28/310/12 在线项目仍 pending；不声称任何新模型准确率。
- 假 HTTP 测试覆盖全部阶段、拒绝未知部署、失败统计、持久预算、中断和幂等续跑。独立进程测试验证新 session、立即可见日志、重复启动与验证 PID 后停止。
- 观测器开启/关闭的算法产物和实际模型请求一致；持久化日志有额外 I/O 成本。

## 文件

- `scripts/start_diagnostics_linux.sh`：一键准备独立环境并提交后台任务。
- `scripts/run_diagnostics.sh`：start/status/log/module-log/stop/resume/preflight。
- `docs/background_diagnostics.md`：详细日志字段、口径与改进定位方法。
- `BridgeTree_Background_Diagnostics.pdf`：4 页操作补充；不是替代旧 R2 机制报告。
- `pdf_qa/`：页面 PNG、文字提取、溢出检查及逐页视觉验收记录。

## 边界

本服务是 PR1–PR4 无训练诊断，不是 589 题 × 5 方法全量评测，不是 PR5，不更新权重。用户原有未提交文件保留。未部署真实 Linux 服务、未进行真实 SSH/调度器测试，未调用外部模型。

服务器须自行配置原归档/数据路径、私有服务覆盖和真实身份，并在最终上传源码上建立新 manifest。安装成功且后台启动信息返回后可退出 SSH；不保证机器重启、容器销毁或调度器回收后进程继续存活。
