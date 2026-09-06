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
  --config configs/default.yaml --offline --no-reranker --limit 1 \
  --output-dir outputs/runs/repair_smoke
```

结果目录为 `outputs/runs/repair_smoke_v2/semantic_development_1788704790601243000/`，S0/S1/S2/S3/S2-shuffle 均完成检索，L0/L1 按要求因没有旧执行器 trace 显式失败；没有生成服务调用，因此没有伪造答案准确率。该目录包含逐行 JSONL、`summary.json`、`run_manifest.json` 和失败记录。

本 checkout 已完成离线算法和测试闭环。完整 PreferenceMem 生成实验仍取决于配置的 reranker、embedding 和 generator 服务；服务可用后可去掉 `--offline --no-reranker` 并设置 `--limit 20` 做 development smoke，再运行完整 development。确认集只执行冻结配置对应的独立命令，不用于调参。
