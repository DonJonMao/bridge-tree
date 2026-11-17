# 旧 HotpotQA reranker fusion 与当前 PersonaMem residual 的核对

日期：2026-10-13。只读调查；未运行模型、未改生产代码。旧包通过 `tarfile.extractfile` 择取小型 JSON / 指标源码 / 答案汇总在内存解析，未展开整个归档。为了核对用户提出的旧成绩，读取旧 HotpotQA evaluation labels **仅作评分**，没有据此调整检索或参数。

## 最重要的结论

1. **旧版在共同成功题上确实高于 original。** 704 道双方执行成功的相同题：fusion EM 63.35%，original EM 58.38%，差 4.97 个百分点。这支持用户关于旧版有效回答有收益的观察。
2. **旧版总体并没有更高。** 已导出的同题 951 题：original 565/951=59.41%，fusion 447/951=47.00%；fusion 有 246 次执行失败。包是在 1000 题中间导出的快照，不是完整结束结果。
3. **当前 residual 不是“同一方法只关了 reranker”。** 它同时改变搜索控制、是否做原问题 dense baseline、原文映射/联合阅读、最终文档重选、是否使用独立 Reader、终端输出及成功条件。因此现有两个跨数据集实验不能给出 reranker 的单因素因果结论。

## 旧包身份与可核实范围

- 包：`/Users/mao/projects/dagv2/scripts/dagv2_results_20261008_025515.tar.gz`，约 389 KiB。
- SHA256：`86c93c31308ca1c9df52758e2d07c30d41c17557de178f8412b6dad9ffbf5963`。
- 只有 11 个成员：manifest、original manifest、metric 源码、HotpotQA questions/evaluation labels、`answers.jsonl`、progress/pid、事件尾部、launcher log、export report。没有完整逐题 diagnostics、检索来源或 HTTP 请求。
- `report.json` 标为 `dagv2_compact_results_v1`，明确只读取 top-level answer、不是全局事务快照，导出时间 2026-10-08 02:55 UTC。
- `run/manifest.json` 中 20 个 `dagbt/` 源码 SHA256 全部匹配本地 git 对象 **`774d285ffe91a23a99ee9afb006e85103be335b5`**。这个结果给出可核实代码对应关系；manifest 自身没有 git commit 字段。
- 当前生产树 HEAD：**`a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1`**；主仓库 HEAD：`f4e38df23b5b621a4d0e759c018c60e1fe25dd9b`。主仓库当前文件并非旧包原样，比较旧逻辑使用 `git show 774d285:<path>`，没有用当前主仓库文件冒充旧版本。
- `original_manifest.json` 中全部 **57 个冻结文件**与当前生产树逐个 SHA256 相同。因此原算法主体文件未变；外围 PersonaMem 输入适配与 transport 计数等并非不变。

## 旧 HotpotQA 结果重新核算

使用包内的 EM/F1 定义；确认当前 `package/metrics.py` 与包内该文件 SHA256 相同，再调用其纯评分函数。`status != ok` 计 0，不把失败剔除后冒充总体。

| 口径 | original | fusion | 解释 |
| --- | ---: | ---: | --- |
| 已导出同题 951：EM | 565/951 = 59.41% | 447/951 = 47.00% | 截至导出时，失败计 0 |
| 已导出同题 951：F1 | 73.62% | 57.00% | 同一批分母 |
| 双方共同成功 704：EM | 411/704 = 58.38% | 446/704 = 63.35% | 同题且都成功，fusion +4.97 pp |
| 双方共同成功 704：F1 | 73.02% | 76.85% | fusion +3.83 pp |
| 各臂自己的成功题：EM | 565/950 = 59.47% | 447/705 = 63.40% | 分母不同，不能作为配对增益 |

`run/progress.json` 仍为 `generating/hotpotqa/fusion`，question_index=951，questions_in_dataset=1000。还有 49 道未导出，不能把上述快照称作完整 1000 题最终成绩。附带机器汇总 `old_hotpotqa_metrics.json` 也保留“计划1000题、未完成计零”的字段，但明确不是最终结果，不建议用它报告成品 accuracy。

旧失败原因来自答案中的错误字符串：

- original：1 个 `planner_failed / plan_size`。
- fusion：129 个 `Coverage repair changed the fixed selection header`；110 个 `A disputed source group must be retained together`；6 个 reasoning output truncated；1 个 missing global selection header/coverage。

这里说明旧全量收益主要被执行失败抵消，不能证明修复这些失败后就会达到共同成功子集的效果。成功子集存在选择偏差。

## 旧 fusion 与当前 residual 的实际差异

| 维度 | 旧 HotpotQA `fusion`（774d285） | 当前 PersonaMem `dagbt_residual_memory_v1` |
| --- | --- | --- |
| 任务 | 开放式事实 QA、短答案 EM/F1 | 历史个人记忆四选一、单标签 accuracy |
| 原始检索范围 | HotpotQA 包装 corpus | 逐题 shared conversation 且严格 `messages[:end_index]` 的 scope；original 与 residual 共用同一 scoped docs/index |
| query 中选项 | HotpotQA 没有 MCQ options | 两臂 planner/retrieval/intermediate 只见 `user_question`；options 在 original Reader / residual terminal 才出现 |
| 起始 baseline | 增加原问题 dense `__baseline__`，保留 Reader 容量可容纳的候选 | 进入 ResidualControl 后直接绕过这条全局 baseline 路径；按 active local demand dense 初始化 |
| 搜索信号 | EvidenceBridgeSearcher + set reranker activation；`R(S)` 的 query 为原问题，grounded subquery 控制发现 | `proxy_mode=none`，`set_score_calls=0`；需求轮转、ANN 排序根节点与原文条件化 continuation 交替；没有 gain、pair tests、score-gated speculation/pivot |
| 推理表示 | 映射原文证据，构造支持图，逐节点 solve/refine/feedback | typed variables/program/output contract、FactState、联合原文读取、残余求值调度与版本化依赖 |
| 末端证据 | `select_support` 之后 `FinalSelector` 可以重选文档，并 raw review；最终最多20篇 | 无 global FinalSelector，无独立原文 raw-review selector；通过实际局部来源和父依赖进行终端 composition/审计 |
| 最终作答 | 独立 Reader 阅读重选后的完整原文，默认 `reader_chain=false` | 指定 DAG terminal 输出 semantic answer + option；无独立 Reader、无额外 fallback Reader |
| 成功条件 | Reader finish_reason=stop 且非空 prediction（推理/审计可以有部分失败） | audit_complete 且有有效 symbolic certificate 或 semantic terminal path；单标签输出还必须通过 parser |
| 每题名义预算 | ANN36、set-score512、reasoning LLM24、Reader1；reasoning输出4096、Reader输出1024 | ANN36、set-score0、LLM24、Reader0；结构化终端在推理预算内，reasoning输出4096 |
| 单请求容量 | 16384，本地 estimator；margin256 | 16384，部署 `/tokenize` 并验证生成 usage；margin256；辅助计数 HTTP 单列 |
| 问题级重试配置 | `max_question_attempts=3` | 当前配置为1；HTTP `max_identical_attempts=3` 仍在 |

旧 reranker manifest 声明为 Qwen3-Reranker-8B、pointwise、unit_interval、batch4、8192 服务容量；不是简单的最终 top-K 排序器，它参与搜索内部多个决策。仅切断打分会同时失去这些机制，当前 `proxy_free.py` 自己也明示这是多个机制一起禁用，**不是 isolated mathematical A intervention**。

旧/新配置均声明 `deepseek-v4-flash` 与 `qwen3-embedding-8b`。这只能证明声明模型 ID 相同，不能独立证明跨日期服务权重、模板及服务行为完全一致。旧简包无请求记录，不能核实各题真实调用次数、token 成本、retrieval recall、reranker分数或实际Reader输入。

## original 到底相不相同

**核心 native 算法相同，不能说所有输入和运行条件相同。** original 一直是 `make_plan → archive_for_resources → native.solve`，冻结文件全部相同：原问题+去占位子问题建 archive，top50取并集；各节点再对可见corpus做dense检索；保留来源闭包、选最多20篇；独立 Reader 接收原文和中间 answer chain。

当前 PersonaMem 的 options 被移到 Reader；原问题/节点没有 options，也不会被“只输出选项”指令破坏 JSON 协议。旧774 PersonaMem runner把完整 `q['question']`（含选项及只输出字母指令）传入 planner，这正是之后修复的适配问题；但旧归档没有一条 PersonaMem结果，**不能拿旧Hotpot成绩验证旧PersonaMem baseline**。

original 不受 `fusion.llm_calls=24` 那个 ledger 配额约束：`AuditedCalls` 构造 `Ledger({})`，由 native pipeline 的节点数/单阶段请求与上下文检查约束。故“两臂同配置文件”不等于同一在线计算预算。原生 planner 输出2048、每节点512、Reader1024；residual中间结构化请求4096。这些设计在比较成本时必须单独报告。

此外，“旧fusion的dense baseline”是其内部候选来源，不是 `original` 这一整个对照算法。不能把二者混为一谈。

## 能支持与不能支持的解释

可支持：旧 scored fusion 在共同成功 HotpotQA 上有正增益；当前方法关闭了真实搜索打分机制，而且也去掉全局重选与独立 Reader，改变了停止/成功协议。当前 open-ended preference/recommendation 问题若被过窄子问题、过早充分性判断或不完整终端原文限制，可能损失相对原baseline的优势，这些是需要逐题证据检验的机制假设。

不可支持：单凭这两个实验断言“全部是reranker造成”“数学残余求解一定无效”“把reranker接回去就恢复原效果”。同样不能把当前 successful-only accuracy 与旧不同题集的 Hotpot EM 作数值因果比较。

建议后续最少先在同一 PersonaMem、同一模型与 cutoff 下恢复可运行的旧 `fusion` 对照，并把其输入选项适配保持当前规则，再与 `fusion_proxy_free` 比较搜索信号变化；这仍是 scored-search机制组的对照。`fusion ↔ residual` 应视为完整架构比较，分别消融 final selection/Reader、联合读取和残余调度才能归因。此处只是实验建议，本次未修改代码或发起模型调用。

## 具体代码出处

生产树 `/Users/mao/projects/dagv2-personamem-a48`：

- `dagbt/runner.py:378`：original transport `Ledger({})`；`:528` original native流程；`:570` PersonaMem Reader适配；`:640` scope/无选项query/terminal选项边界。
- `dagbt/resources.py:347`：两臂 scoped resources；`:366` original archive top50和维度guard适配。
- `dagbt/config.py:7`：默认预算；`:30` local terminal覆盖项；`:50` residual zero-score设置。
- `dagbt/engine.py:517`：residual在全局baseline前转入ResidualControl。
- `dagbt/bridge.py:527`：零评分的逐步dense/conditional协议。
- `dagbt/proxy_free.py:1`、`:26`、`:60`：被关闭的评分机制和实际调度。
- `dagbt/residual_control.py:407`：residual停止、active demand、局部池/父原文读取；`:569`最终成功条件。
- `dagv2/frozen_flow_v6.py:16`、`:22`：original top50与节点512输出；`:87` Reader chain；`:110` native solve/最终20篇。
- `dagv2/experiment.py:138`：original planner2048；`package/core.py:80` 来源闭包与选择。
- `configs/residual-memory.personamem16k.json`：当前请求/问题预算与tokenize profile。

准确旧源码通过 `git show 774d285:<path>` 读取：

- `dagbt/bridge.py:166` set-score预算与集合序列化；`:228` 原问题打分语义；`:275` reranker初始化；`:290` ANN/score分配。
- `dagbt/engine.py:398` support选择与FinalSelector；`:431` 原query dense baseline与全DAG/反馈；`:497`独立Reader及成功状态。
- `dagbt/runner.py:460` original native流程；`:562`旧PersonaMem完整MCQ进入generation question。

评分附表：同目录 `old_hotpotqa_metrics.json`。本调查未接触当前 full 包答案，当前PersonaMem各分母结果由主调查单独核对。
