# 89846c3 repair notes

本轮把语义路径主链固定为任务书中的四项定义。`factor_conditioned_innovation` 直接对
`B[:,a]=sqrt(w[a,j] r[a]) v[a]` 做 thin-SVD，并返回
`sqrt(r[j]) (I+B B^T)^(-1/2) v[j]`；主选择器保存 rank-1 特征列，用小 Gram
矩阵计算目标和边际。只有小维度的兼容结果才组装旧的 `InformationAtom` 方阵。

`rho_squared_quality_records` 现在要求旧执行器导出的 `legacy_rho`，并以
`legacy_rho**2` 建立 L0/L1 质量；没有旧 trace 时不会把冻结图的随机访问质量 h
冒充 rho²，而是显式让原始 R1 行失败/等待 trace。
`single_path` 可接收 `legacy_parent_id`，不会从多父后验冒充旧父链。

来源置乱新增 `shuffle_frozen_graph`：按层生成固定 seed 的节点双射，同时迁移层成员、边、边权、根质量和提议记录；置换本身及有效节点数写入冻结图身份。S2-shuffle 在语义检索入口使用独立的图 hash 和重新计算的祖先占用。单节点层会自然记录为零有效干预。

通用 PSD 惰性接口的证书上界改为 `trace(Q)`；语义 rank-1 provider 继续使用合法的
`log1p(r)` 上界。QA/QB 高秩反例在 eager/lazy 中均选择 B。

多父路径展示在路径数超出显示上限时只保留 `representative_local_parent` 链，并写入该链真实的条件 posterior；完整 `gamma` 与祖先占用 `w` 仍是正式算子，不把展示链冒充全局 MAP。

验证命令：

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m bridgetree --help
```

另以真实仓库的 PersonaMem development 数据运行了 1 题离线 semantic-matrix smoke：

```bash
PYTHONPATH=src python -m bridgetree run-semantic-matrix \
  --config configs/default.yaml \
  --protocol-manifest outputs/protocol/confirmatory_v1/protocol_manifest.json \
  --phase development --rows S0,S1,S2 --baseline none \
  --offline --no-reranker --limit 1 \
  --output-dir outputs/runs/repair_smoke
```

结果目录为 `outputs/runs/repair_smoke_v2/semantic_development_1788704790601243000/`，S0/S1/S2/S3/S2-shuffle 均完成检索，L0/L1 按要求因没有旧执行器 trace 显式失败；没有生成服务调用，因此没有伪造答案准确率。该目录包含逐行 JSONL、`summary.json`、`run_manifest.json` 和失败记录。

本 checkout 已完成离线算法和测试闭环。完整 PreferenceMem 生成实验仍取决于配置的 reranker、embedding 和 generator 服务；服务可用后可去掉 `--offline --no-reranker` 并设置 `--limit 20` 做 development smoke，再运行完整 development。确认集只执行冻结配置对应的独立命令，不用于调参。

## 89846c3 后续实验接线

实验入口现在先执行 `canonical_phase`，真实 PersonaMem 的 development、confirmatory 和
full 别名都必须通过持久化 protocol manifest；只有显式 `synthetic=True` 的内存 fixture
可以绕过角色 manifest。角色筛选发生在 limit、embedding、reranker 和 generator 之前。

语义 proposal 查询在 `retrieve_method`、`BridgeTreeRetriever.retrieve` 和
`semantic_retrieve` 之间使用同一个 provider/instruction。正式
`real_member_query_anchor` 缺 provider 会显式失败；旧接口中向量维度不匹配的本地替身只
会被标记为 `offline_q_plus_anchor`，不会伪装成服务编码。

`run_semantic_matrix` 默认运行 S0/S1/S2；S3、shuffle、L0/L1 通过 `--rows` 显式选择。
L0/L1 会调用 `legacy_core` 执行器，从真实 `result.nodes` 导出 rho/parent 后冻结旧 trace，
不再从当前多父图的 h/gamma 推导 rho。`--baseline dense_rerank` 产生独立 Dense 候选池和
逐题可 join 的 `predictions_DenseRerank.jsonl`；缺服务时状态为 `not_run`，不会写入伪造
Gain/Damage/Net。

每个计划方法题目都会保留一行成功或失败记录。生成开启时，end-to-end 指标以完整计划题
集为分母，失败按未完成计 0，同时保留 `successful_response_accuracy` 诊断；retrieval-only
运行的答案指标保持 null。GenerationCache v2 只按 endpoint 身份和实际 JSON request 建键，
不再把 greedy 选择顺序混入生成缓存身份。

本轮实际运行的 development retrieval-only 命令（使用既有历史 manifest 的 development-seen
角色，未调用真实模型服务）：

```bash
PYTHONPATH=src python -m bridgetree run-semantic-matrix \
  --config configs/default.yaml \
  --protocol-manifest outputs/protocol/confirmatory_v1/protocol_manifest.json \
  --phase development --rows S0,S1,S2 --baseline none \
  --offline --no-reranker --limit 2 \
  --output-dir outputs/runs/repair_dev_current
```

结果目录为 `outputs/runs/repair_dev_current/semantic_development-seen_1788783154958999000/`：
2/2 题的 S0/S1/S2 检索记录成功，答案准确率为 null（未启用生成），Dense 基线明确记录
为 `not_run`。默认测试、ruff 和该 development smoke 均通过。
