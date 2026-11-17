# PrefEval：original 与完整 residual v2

本包从 2026-10-14 PersonaMem v4 已交付的实验包派生。
`original` 是原 DAGv2；`dagbt_residual_memory_v2` 是完整 residual 算法分支，
保留动态需求控制、联合证据阅读、个人历史摘要修订、终端选项判断和审计。
这是一项 RAG 推理评测，不训练模型参数。没有切换到 WebWalker 的网页导航实现。

## 安装并直接跑全量

将 `dagv2_prefeval_v4_experiment.tar.gz` 上传到服务器 `~/bt/`，执行：

```bash
mkdir ~/dagbt_runs/20261020_prefeval_v4_experiment && tar -xzf ~/bt/dagv2_prefeval_v4_experiment.tar.gz -C ~/dagbt_runs/20261020_prefeval_v4_experiment && bash ~/dagbt_runs/20261020_prefeval_v4_experiment/dagv2/scripts/prefeval_v4.sh install
bash ~/dagbt_runs/20261020_prefeval_v4_experiment/dagv2/scripts/prefeval_v4.sh full
```

安装命令使用 `mkdir`，目标目录已存在时会停止，避免覆盖已冻结的实验；此时换一个新的部署目录名。
安装默认从 `~/dagbt_runs/20261014_personamem_v4_experiment/dagv2` 复用经过校验的旧冻结资源和本机凭据，
不修改旧部署，不复制旧实验输出。凭据不在 tar 中；新本机凭据文件权限为 0600。
冻结旧向量尽量使用硬链接，避免额外占用约 431 MiB；跨文件系统才复制。
**PrefEval 的检索索引会在本新目录自动构建**，不能复用 PersonaMem 的向量。
首次启动会先检查模型及规划协议，再构建索引，因此暂时没有逐题进度是正常的。

默认 Python：`~/dagbt_runs/20260930_v3/dagv2/.venv/bin/python`。
需要更换时设置 `DAGBT_PYTHON`。默认模型沿用 PersonaMem：DeepSeek-V4-Flash、Qwen3-Embedding-8B，
端点和 `/tokenize` 设置在 `configs/prefeval-v4.json`。
若旧部署位置不同，安装时追加 `--base /你的旧PersonaMem目录/dagv2`。

## 看进度、准确率和停止

```bash
bash ~/dagbt_runs/20261020_prefeval_v4_experiment/dagv2/scripts/prefeval_v4.sh status
bash ~/dagbt_runs/20261020_prefeval_v4_experiment/dagv2/scripts/prefeval_v4.sh accuracy
bash ~/dagbt_runs/20261020_prefeval_v4_experiment/dagv2/scripts/prefeval_v4.sh stop
```

默认输出：`outputs/prefeval_v4_t10_full/`。
日志：该目录的 `launcher.log`；最终结果：`prefeval/summary.json`；
临时准确率快照：`interim_accuracy.json`。
准确率同时报告两臂完成数、有效数、正确数、含失败准确率，以及同题含失败、双方有效的配对比较，
并按偏好形式和干扰长度拆分。失败和非法选项计错，不只展示有效答案的条件准确率。
统计仅使用原子发布的当前结果，不需要外部裁判模型，也不会把评分反馈送回生成流程。

停机或磁盘空间恢复后，再执行**相同的 full 命令**继续；已发布的结果不会重跑。
沿用 PersonaMem 单次题目尝试设置：被中断且已消耗尝试的任务会如实记失败，不自动重答。
生成前剩余磁盘少于 2 GiB 时停止，腾空间后可继续。运行中不要改源码、配置、数据或输出目录中的选择文件。

## 数据与任务

- 官方仓库：<https://github.com/amazon-science/PrefEval>。
- 固定版本：`50795054b5ff5f418d2b768a331d71e480f93331`。
- 使用官方 **MCQ 四选一任务**，不是开放生成任务的 LLM-judge 指标。
- 默认全部 20 个主题、每类 1,000 题：显式偏好、隐式选择对话、隐式人设对话。
- 默认 10 轮无关对话：**3,000 题 × 2 方法 = 6,000 个任务**，不抽训练集，不微调。
- 包内同时准备 0、10、70、300 轮条件，共 12,000 个题目条件。
  同一基础题跨偏好形式及长度共享选项排列；不能把这些重复条件视为独立的 12,000 条基础问题。
- 官方 MCQ 文件的第一个原始选项是正确答案；按官方每主题 `Random(41)` / `random.sample` 排序，
  转换后正确答案单独存入 `evaluation_only.json`，生成只加载公开字段白名单。
- 显式任务按官方分类入口读取 `mcq_options` 中的偏好文本；它与生成版 explicit 文件的 30 条措辞有差别。
- 隐式任务只提供对应官方 conversation，不提供隐藏的 preference、persona、explanation、aligned_op 元数据。
- 按官方顺序展平无关对话，取前 `2*N` 条消息；保留角色和观察顺序。
- 两种算法都只能检索当前题目的历史，不能看到其他题的偏好或额外未来干扰消息。
  共享存储/索引不扩大问题可见范围；每题重建独立 ANN 作用域。
- `third_party/prefeval/` 保存原始来源、代码参考、版本清单及上游许可证。
  生成模块不读取该目录；`dagbt.prefeval.prepare_dataset` 可在另一个新目录重建数据。

## 可选烟测及其他长度

```bash
# 三类各取第一道公开题，只检查部署兼容性，不挑答案，不作为全量启动门槛。
bash scripts/prefeval_v4.sh smoke
bash scripts/prefeval_v4.sh status --output outputs/prefeval_v4_t10_smoke
bash scripts/prefeval_v4.sh accuracy --output outputs/prefeval_v4_t10_smoke

# 各自生成独立输出目录，保留所有题，不混入默认10轮结果。
bash scripts/prefeval_v4.sh full --turns 0
bash scripts/prefeval_v4.sh full --turns 70
bash scripts/prefeval_v4.sh full --turns 300
bash scripts/prefeval_v4.sh status --turns 70
bash scripts/prefeval_v4.sh accuracy --turns 70

# 如需一次覆盖所有长度（24,000任务）：
bash scripts/prefeval_v4.sh full --turns 0 10 70 300
```

也可用 `--forms explicit` / `implicit_choice` / `implicit_persona` 选择形式；目录名会包含选择条件。
可用 `--output` 自定新目录；之后 status/accuracy/stop 使用相同的 --output。
不要同时启动多个共享模型服务的长实验而不记录资源竞争。

## 资源与结果解释

继承 PersonaMem v4：每次请求上下文 16,384、residual LLM 调用预算 24、ANN 36、JSON 修复 6、
每请求修复最多 2、每题超时 3,600 秒、题目尝试最多 1。**完整方法不等于取消预算**；
WebWalker 的“不限模型调用”续跑补丁没有移植到这里。
original 保留原生规划/检索/求解/Reader 停止与调用机制；residual 保留自身 Ledger，
不能把共享配置解释成两者实际调用量或有效调用上限完全一致。输出记录各阶段调用与 token。

本包是把 PersonaMem 算法移植到官方 PrefEval MCQ 数据：
两方法使用历史检索，显式偏好后不额外生成 acknowledgment，输出沿用 PersonaMem 的单选标签，
没有使用官方 `<choice>` XML 协议，也没有直接复现官方“保留全历史再追加 top-k 提示”的 baseline。
因此与论文数值比较时需注明模型、任务、历史切分、训练状态和协议差异。
测试使用的本地脚本模型响应仅验证工程流程，不能用作真实准确率。
实际服务器的模型访问、索引构建及全量准确率需安装后运行获得。

## 本地核验

具体测试和父版本对应关系见 `VALIDATION_PREFEVAL_V4.json` 与 `DEPLOYMENT.json`。
保留 PersonaMem v4 的全部核心方法文件；仅在 runner/resources 中增加数据集、作用域与评分分发，
并增加 PrefEval 数据适配、命令封装、低磁盘停止和中断结果身份标记。

```bash
python -m pytest tests/test_prefeval_port.py -q
python scripts/prefeval_v4.py validate
```
