# PR1–PR4 同轮诊断运行手册

本轮交付是诊断改造，不是 PR5 主方法重设计。不训练，不引入 dense 保护、Judge 或新选择器。旧集合评分、空集合真实评分、正边际选择和默认搜索策略保留；PR4 只提供初始零优先级根的平局顺序开关。

## 独立验收

所有测试默认只用合成数据和假 HTTP。不能把假服务通过当成真实在线实验已完成。

```bash
.venv/bin/python -m pytest tests/test_diagnostic_identity.py tests/test_request_audit.py tests/test_clients.py tests/test_dependency_scoring.py tests/test_config.py tests/test_dependency_experiment.py
.venv/bin/python -m pytest tests/test_dependency_diagnostics.py
.venv/bin/python -m pytest tests/test_diagnostic_runner.py
.venv/bin/python -m pytest tests/test_root_tie_diagnostics.py tests/test_diagnostic_root_runner.py tests/test_dependency_search.py tests/test_dependency_config.py
.venv/bin/python -m pytest
```

PR2 可在尚未接入其他诊断入口时单独运行：

```bash
.venv/bin/python -m bridgetree.dependency_diagnostics /Users/mao/chain-audit-detail.tgz --expected-sha256 c040e839dc5f957596cde0632d739d60769e1ec884092829460bde62c3334c80
```

三个真实案例恢复 28 个子集中的 24 个历史分数；缺口为绘画 `{11,39}` 和音乐 `{5,6,27}`、`{5,8,27}`、`{5,6,8,27}`。读书会四项完整。全 archive 回放与受限格点模拟分开，所有结论带评分及可行性来源；缺分不补零，不将跨界 bundle 截成 B∩U。

## 准备部署与冻结运行

`configs/diagnostic_28.yaml` 是当前真实归档的可执行离线配置。路径可以复制后调整，归档 SHA 不得随意更换。`configs/diagnostic_deployment.example.yaml` 是有意保留未知身份的模板，不是一个已冻结的部署。

在线前由部署操作者确认每个实际服务的 checkpoint / 权重 / deployment revision 至少一种，以及身份来源等级。量化、tokenizer、服务版本未知时明确保留未知。模型 API 名、地址或人工填写“284B INT8”不能冒充服务端验证。把真实部署信息放在私有 override，修改诊断配置的 `deployment_override`，再创建一个新运行；不要改旧 manifest，也不要用旧输出目录重新冻结。

完整输入计划为：三个问题的全部子集含三个独立空集（28 个）；加各题原 dense 上下文（3 个）；每条件 10 次独立客户端请求，共 310 个生成 trial。没有偷偷补造长度对照；可在冻结前用 `cases[].controls` 显式提供来自可见历史的控制集合和理由。新增 3 个长度对照会使生成 trial 成为 340，必须同步增加冻结预算。

默认上限：评分 28 个逻辑输入 / 84 个物理传输尝试；生成 310 个 trial / 930 个物理尝试；根消融 12 次搜索 / 12,000 个物理尝试，根消融不生成答案。根消融每次保留原 ANN=36、搜索和选择各512个逻辑唯一集合增量上限；三例×（legacy+seed 7/19/43）全部报告。物理上限不是保证会消耗的调用量，更不是 token 或账单金额。

以下以独立新目录为例；这组命令不是自动启动后台任务。

```bash
.venv/bin/python -m bridgetree diagnostic-plan --config configs/diagnostic_28.yaml --output-dir outputs/diagnostics/frozen-run
.venv/bin/python -m bridgetree diagnostic-analyze --run-dir outputs/diagnostics/frozen-run
.venv/bin/python -m bridgetree diagnostic-score --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
.venv/bin/python -m bridgetree diagnostic-generate --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
.venv/bin/python -m bridgetree diagnostic-roots --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml
```

`plan/analyze/evaluate/report` 无网络。`score/generate/roots` 不带 `--execute` 只展示冻结清单和上限。在线入口会核对源码、服务配置、实际 payload 身份和部署声明；身份未知或漂移时写 gate 失败并在任何模型请求前拒绝执行。只有部署方保证服务未热切换，配置声明才具备实际冻结含义；客户端不能证明服务没有未披露的路由、缓存或量化变化。

## 显式执行与续跑

```bash
.venv/bin/python -m bridgetree diagnostic-score --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute
.venv/bin/python -m bridgetree diagnostic-analyze --run-dir outputs/diagnostics/frozen-run --score-view fresh
.venv/bin/python -m bridgetree diagnostic-generate --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute --resume
.venv/bin/python -m bridgetree diagnostic-roots --run-dir outputs/diagnostics/frozen-run --config configs/diagnostic_28.yaml --execute --resume
.venv/bin/python -m bridgetree diagnostic-evaluate --run-dir outputs/diagnostics/frozen-run --gold-source data/raw/personamem-v1/questions_32k.csv
.venv/bin/python -m bridgetree diagnostic-report --run-dir outputs/diagnostics/frozen-run
```

续跑始终以同一个预注册 trial_id 为单位，成功和已经终止的失败不会因再次执行命令获得额外样本或重试额度。不同 repeat 始终绕过响应缓存；相同 trial 的已落盘成功、不可重试失败或已耗尽任务次数的失败事件都可以恢复原 outcome，不重复调用或把已知错误改成 InterruptedAttempt。只有可重试且任务额度未耗尽的失败可以继续下一次尝试。崩溃留下的 started 保守消耗一次任务/物理额度；已发请求但响应不明的情况不能计成“服务没执行”。错误答案与解析失败不触发重试。实际物理尝试额度从 durable 请求日志恢复，不能因进程重启清零。

请求前事件持久化、失败、拆批父子关系、原文档 index 和集合身份都在 `requests.jsonl`。默认不输出凭据、私网 endpoint 或记忆原文。评分文档和完整 reader 上下文在本地受控 manifest 中，和脱敏请求 hash 可关联。实际 token 不可获得时为 null，估算 token 不冒充实际 token。

## 输出与解释

- `manifest.json`：公开题目、严格可见历史、完整输入、部署身份、调用顺序和预算；无正确答案。
- `offline_analysis.json`：历史分数来源、24/28 缺口、真实 bundle 可达性与预算感知历史回放。
- `score/*.json`、`fresh_analysis.json`：本会话完整新评分或失败；不混入24个旧分。局部最高 R 不称全库最优。
- `generation/*.json`：每个预注册重复的原始输出或失败；`attempts.jsonl` 保存全部尝试。
- `root/*.json`、`root_summary.json`：每个预声明 seed 的完整/部分搜索、选择和 trace，最终集合差异；无答案生成。
- `evaluation.json`：独立评价、固定 trial 分母、成功输出分母、解析失败、答案分布与原选择的分块配对。
- `diagnostic_report.json`：统一汇总，包括未执行和 gate 阻断项；不是只统计成功样本。

三例为事后选出的机制诊断案例，不是正式测试集；技术重复不是新的独立问题。新证据是否帮助回答、R是否错位、archive是否可构造、严格正路径是否存在和greedy是否找到分别报告。根 tie-only 消融仅测无语义次序敏感性，不保证根覆盖，也不实现轮询或根预算。

## 下一步机制方向（尚未实现）

优先审视相关性、条件证据贡献和停止依据是否应分离。如果补历史稳定改善回答却降低R，应改目标；如果高R且更有用的可行组合没找到，再研究联合添加、有限回退或替换；若关键事实在可见库却没被召回，再研究跨目标覆盖。不能把新Judge随意输出的分数直接当cardinal utility，也不能用logit修复固定archive下的选择排序。PR5须依据诊断另行定义和批准。
