# BridgeTree 效果优先 Reranker 引导实验

## 1. 已完成正式实验的事实

PersonaMem-v1 32K 正式运行已通过独立完成审计：
`completion_audit.status=passed`，`errors=[]`。Embedding 维度为 4096，所有方法
答案解析失败率均为 0。因此下面的差异不是由空结果、答案解析失败或 embedding
维度错误造成的。

测试集共有 73 题：

| 方法 | 正确数 | Accuracy | 相对旧 BridgeTree |
| --- | ---: | ---: | ---: |
| Dense Rerank | 51/73 | 69.86% | +13.70 pp |
| Dense | 48/73 | 65.75% | +9.59 pp |
| RFMem Familiarity | 47/73 | 64.38% | +8.22 pp |
| RFMem Recollection | 47/73 | 64.38% | +8.22 pp |
| RFMem | 46/73 | 63.01% | +6.85 pp |
| Cluster PRF | 43/73 | 58.90% | +2.74 pp |
| 旧 BridgeTree | 41/73 | 56.16% | 基准 |

这是明确的负结果：旧 BridgeTree 不仅低于 Dense Rerank 10 题，也低于不使用
reranker 的 Dense 7 题。现有实验不能支持“旧 BridgeTree 提升最终答案精度”的
主张。

## 2. 旧 BridgeTree 的模块诊断

每题平均候选树为 20 个节点，其中第一跳 12 个、第二跳约 8 个；两次核心 ANN
调用，`visited_budget_ratio=1.0` 且 `budget_frozen=1.0`，说明每题都用满固定预算。
没有重复 proposal，平均每次 ANN 获得 10 个新节点，候选扩展链路本身工作正常。

关键路径统计：

| 指标 | 值 | 含义 |
| --- | ---: | --- |
| `deep_node_rate` | 40.00% | 20 个候选中约 8 个为第二跳 |
| `selected_deep_node_rate` | 71.78% | 最终 5 条中平均约 3.59 条来自第二跳 |
| `bridge_node_rate` | 100% | 所有第二跳节点的 bridge lift 均为正 |
| 一跳平均 query cosine | 0.4644 | 一跳与问题直接相关性 |
| 二跳平均 query cosine | 0.3613 | 比一跳低约 0.1030 |
| 平均 parent-child cosine | 0.5838 | 二跳与父节点保持一定主题连续性 |
| 平均 reachability | 0.4894 | 路径代理分数不低 |
| 平均/max bridge lift | 0.1656 / 0.2182 | 桥接扩展确实发现了直接相似度较低的节点 |
| navigation-only parent rate | 38.13% | 不少父节点仅用于导航，未进入最终上下文 |

这组数字说明“搜索没启动”不是主要问题。真正异常是选择比例：第二跳只占候选
40%，却占最终上下文 71.78%。第二跳与原问题的直接相似度显著下降，但正 bridge
lift 和路径 reachability 会使其在 `rho_logdet` 下获得结构性优势。路径可达性回答的
是“能否从已有记忆方向到达”，并不等价于“是否能帮助生成器区分当前答案选项”。

旧配置使用 `feature_mode=rho`，`mean_retention_ratio` 与最小值几乎都是 1；这在该
特征定义下接近构造结果，不能证明选出的内容具有额外语义价值。
`path_objective_advantage=0.0001635` 也非常小。与此同时最终 accuracy 明显下降，
因此 log-det、bridge lift、reachability 只能保留为搜索/结构诊断，不能继续作为
效果优先版本的最终选择依据。

## 3. 旧调参协议还暴露出的选择问题

84 题 validation 上，点估计最高的是 trial 9：

```text
initial_width=12, branch_width=4, search_budget=20
59/84 = 70.24%
```

但旧 `final_summary.json` 记录的 `best_trial=13` 为：

```text
initial_width=12, branch_width=8, search_budget=20
56/84 = 66.67%
```

二者相差 3 题、3.57 个百分点。原因是旧选择逻辑让配对 bootstrap/成本影响了
incumbent 更新，而不是严格选择 accuracy 点估计最高者。该问题使 trial 13 的
73 题结果不能代表 16 个配置中点估计最优配置在 test 上的表现；不过不能据此
推测 trial 9 的测试准确率，因为 trial 9 没有在 test 上运行。

网格趋势同样清楚：更宽分支和更大搜索预算通常没有帮助。最佳点使用最小预算
20 与较窄 `branch_width=4`；在 `initial_width=12, branch_width=4` 下，预算从
20 增到 28/36/44 后，validation 从 70.24% 降到 65.48%/65.48%/63.10%。这与
“越扩展越容易引入对问题无用的二跳记忆”的诊断一致。

新效果验证已经改为：严格按 validation accuracy 点估计排序，只有完全同分才按
成本破同；paired bootstrap 只作事后报告，不参与顺序依赖的配置选择。

## 4. 新方案的研究问题

本轮只检验一个假设：BridgeTree 可能有候选发现价值，但旧的最终选择器发生了
目标错位。新主链路为：

```text
Dense Top-W
-> 任务条件 rerank 选择真实锚点
-> 锚点聚类形成不同方向
-> 批量编码 query + anchor 条件查询
-> 每方向检索新候选
-> 可选逐路径 rerank 过滤
-> Dense 候选与 bridge 候选稳定并集
-> 同一任务条件 reranker 取 Top-5
-> 按时间排序后调用一次 generator
```

BridgeTree 只负责扩大候选支持集；最终任务价值由 reranker 判断。实现没有增加
多分数线性加权、教师蒸馏、RL 或额外生成 LLM，也没有删除旧 log-det/path/
certificate 代码。新方法不宣称 certificate，并会拒绝
`stop_mode=certificate_or_budget`。

## 5. 六个验证方法

| 方法 | 候选与选择方式 | 作用 |
| --- | --- | --- |
| `dense_rerank_20` | Dense Top-20 后统一 rerank Top-5 | 当前强基线 |
| `dense_rerank_28` | Dense Top-28 后统一 rerank Top-5 | 控制“只是多看 8 条”的解释 |
| `bridgetree_union_rerank` | Dense-20 ∪ 旧树全部新发现节点，再 rerank | V1：隔离旧 final selector 的影响 |
| `bridgetree_guided_rerank` | rerank 锚点 + 两个 query-anchor 分支，各保留 ANN Top-4 | V2：任务引导候选扩展 |
| `bridgetree_guided_pathfilter` | 每支 8 条经 anchor+candidate rerank 保留 Top-4 | V3：抑制同主题复述与漂移 |
| `full_pool_rerank` | 对每题全部约 90 条记忆 rerank Top-5 | 诊断候选召回上界，不是效率主基线 |

默认宽度为 Dense 20、anchor 12、4 个 anchor 簇、扩展得分最高的 2 个不同簇、
每支过取 8 并保留 4，最终并集最多 28 条。V1 复用同一次 Dense ANN 的前 12 条
作为旧树种子，避免重复 Dense 查询；guided 方法也只执行一次 Dense ANN。

所有 rerank 方法共享完全相同的：reranker 模型、问题与规范化答案选项、数值时间
元数据、最终 context size、generator prompt 与 token budget。`correct_answer` 从不
进入 rerank query。

## 6. 运行与产物

服务器项目根目录执行：

```bash
./scripts/run_effect_first_validation.sh > effect_first.log 2>&1
```

需要脱离 SSH 时，在 tmux 内执行上述命令，然后按 `Ctrl-b`、松开、再按 `d`。
验证入口只使用 persona-disjoint validation，不评估已经查看过的 73 题 test。

输出目录为：

```text
outputs/effect-first-validation/effect_validation_<timestamp>/
```

主要文件：

- `effect_summary.json`：方法排名、选中方法、逐方法指标、full-pool recall；
- `paired_results.json`：相对 Dense-Rerank-28 的 paired bootstrap 与净纠错；
- `effect_results.csv`：可直接查看或导入表格软件的配对结果总表；
- `predictions.jsonl`：逐题候选、来源、父边、阶段 score、回答和成本；
- `events.jsonl`、`metrics.csv`、`modules/*.jsonl`：可聚合模块指标；
- `resolved_config.json`、`run_manifest.json`：完整协议与 `test_queries_read=0`；
- `run_status.json`、`progress.json`、`failures.jsonl`：运行状态与失败证据。

Reranker 缓存保存完整排序而非某个 Top-n，key 包含 endpoint、model、完整 query 与
有序 documents。缓存命中仍计入逻辑 `rerank_calls/rerank_documents`；命中时物理
`rerank_ms=0`，因此既可公平比较算法工作量，也可安全断点重跑。

## 7. 新结果的判定方式

第一步比较 `bridgetree_union_rerank` 与 `dense_rerank_20/28`：若 V1 从旧版
56.16% 恢复到接近 Dense Rerank，说明主因是旧 `rho_logdet` 最终选择错位；若仍
显著落后，则旧 BridgeTree 候选本身也存在问题。

第二步看 guided 两版相对 `dense_rerank_28` 的逐题净纠错：

```text
bridge_net_correction
= (BT correct & Dense-Rerank-28 wrong)
  - (Dense-Rerank-28 correct & BT wrong)
```

正值才说明 bridge 候选带来净答案收益。还需同时看
`selected_bridge_count/rate`、Dense Top-5 retention、候选规模和 rerank 文档数，
不能只看总体 accuracy。

第三步看 `full_pool_top5_recall`：若 Full-Pool 与 Dense-Rerank-20 几乎同分，说明
Dense 候选召回已经接近饱和，BridgeTree 扩展空间有限；若 Full-Pool 明显更高且
guided 方法提高了对 Full-Pool Top-5 的覆盖，则桥接候选发现假设得到支持。

在服务器产生新 validation 结果以前，只能确认代码与协议已离线验证，不能声称
新方法已经提升 accuracy。正式主张必须等待新 validation 选择完成，并在未用于
选择的新 persona-disjoint test 上逐题配对复验。
