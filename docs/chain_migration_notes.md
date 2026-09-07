# BridgeTree-Chain 迁移说明

当前基线是 `32afa36` 之后的 `main`。Chain 核心位于 `chain_judge.py`、
`chain_support.py` 和 `chain_search.py`，任务键和分母统计位于
`chain_experiment.py`。

离线检查：

```bash
PYTHONPATH=src pytest -q
ruff check src tests
```

Linux 打包和后台入口：

```bash
bash scripts/package_chain_server.sh
BRIDGETREE_BASE_PYTHON=.venv/bin/python \
  bash scripts/run_chain.sh start configs/chain_full.yaml
bash scripts/run_chain.sh status
bash scripts/run_chain.sh log
bash scripts/run_chain.sh resume configs/chain_full.yaml
bash scripts/run_chain.sh stop
```

`chain_worker.py` 会先冻结全量任务键并创建审计目录。输出中的
`completion.status=planned` 表示计划已冻结，不能当作真实答案实验完成。要运行真实
Chain，需要配置能在同一个输出位置返回 sufficient 和 insufficient 两个标签、且两者
来自同一前缀同一输出位置的 judge；缺少任一标签必须在全量任务开始前失败。reader 的
请求只应使用最终 `ContextPlan` 中的原文、角色和时间。

`configs/credentials.local.yaml` 保存私用服务 key，`load_config` 在端点完全匹配且主配置
未指定 key 时自动读取；不需要设置环境变量。此文件被 Git 忽略，但私用服务器打包
脚本会包含它，因此生成的包含有凭据，只用于私用部署。非空环境变量仍可显式覆盖 key。

压缩包不携带本机虚拟环境。远程模式只需要安装 `requirements.txt`；本地 judge 需要
另行安装用户配置的冻结模型运行时。工作区中的 `bridge-tree-30c41cd.zip` 是历史未跟踪
文件，不属于发布包。
