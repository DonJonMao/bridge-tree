# PersonaMem v4 算法实验包

源码版本：`e6677081cdfb33c01db3aaa274a497168f314f78`。
比较方法：`original` 与 `dagbt_residual_memory_v2`。这是推理评测，不做模型参数微调。

本次按“算法可测试”的研究实验版本交付。2381 项离线测试通过；新版本已完成首题真实作答和审计，14 题验证仍在运行，已有失败题。不能据此宣称准确率提升或全量无失败。包内 `VALIDATION_PERSONAMEM_V4.json` 保存打包时的真实状态。

## 1. 上传并安装

将 tar 和同名 `.sha256` 上传到服务器 `~/bt/`，执行：

```bash
cd ~/bt
sha256sum -c dagv2_personamem_v4_experiment.tar.gz.sha256
mkdir -p ~/dagbt_runs/20261014_personamem_v4_experiment
tar -xzf dagv2_personamem_v4_experiment.tar.gz -C ~/dagbt_runs/20261014_personamem_v4_experiment
cd ~/dagbt_runs/20261014_personamem_v4_experiment/dagv2
bash scripts/personamem_v4.sh install
```

安装器默认从 `~/dagbt_runs/20261011_personamem_a48/dagv2` 复用已校验数据、索引和模型凭据；不修改旧部署。密钥不包含在 tar 内。Python 默认复用原来的 v3 环境。

如果安装器明确报告缺少兼容索引，再按包内 README 的 `install --assets-only`、`prepare-index` 流程处理；已有兼容索引无需重建。

## 2. 启动全量实验

在上述新版 `dagv2` 目录执行：

```bash
export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
NO_PROXY='*' no_proxy='*' "$DAGBT_PYTHON" -m dagbt.runner launch \
  --config configs/personamem-v4.json \
  --datasets personamem \
  --arms original dagbt_residual_memory_v2 \
  --output outputs/personamem_v4_experiment_full
```

这会运行全部 589 题。模型、数据、预算和算法校验沿用已测试配置；失败照实记录。每次新实验使用新输出目录。

本实验使用上述 `dagbt.runner launch` 入口。包内旧的 `personamem_v4.py full/check` 保留了严格的 14 题全成功自检门槛，不是本次全量实验的前置步骤。

## 3. 看进度和准确率

```bash
bash scripts/personamem_v4.sh status --output outputs/personamem_v4_experiment_full
bash scripts/personamem_v4.sh accuracy --output outputs/personamem_v4_experiment_full
```

`accuracy` 可在运行中使用，同时显示含失败题的同题比较与双方有效作答的同题比较。最终结果位于 `outputs/personamem_v4_experiment_full/personamem/summary.json`。

如需停止这个实验：

```bash
bash scripts/personamem_v4.sh stop --output outputs/personamem_v4_experiment_full
```
