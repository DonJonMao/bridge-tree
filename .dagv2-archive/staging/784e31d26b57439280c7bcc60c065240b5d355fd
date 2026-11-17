# WebWalkerQA v4 轻量 v2

本包只运行 WebWalkerQA：完整 680 题、joint/residual 两组，生成结束后自动评分。
运行文件、配置、数据、107 个公共核心文件及 PDF wheel 均精确保留自双数据集修订 2。
BrowseComp-Plus 数据与专属代码、配置、脚本和双数据集协调器已移除。
WebWalker 的 Playwright/Chromium 浏览器能力及安装脚本保留。

这是原 v2 的轻量派生包，没有加入后续 v3 算法改动。新包安装与离线验证状态见
validation.json；未重新运行付费真实题目，不声称新的真实回归或服务器全量结果。
原 v2 WebWalker 小样本 2/4 正确仅为历史来源记录。

## 上传并启动

上传本目录同名 tar.gz 与 tar.gz.sha256 到服务器 ~/bt/，执行：

    cd ~/bt
    sha256sum -c dagbt_webwalker_v4_v2_experiment.tar.gz.sha256
    mkdir -p ~/dagbt_patches/webwalker_v4_v2
    tar -xzf dagbt_webwalker_v4_v2_experiment.tar.gz -C ~/dagbt_patches/webwalker_v4_v2
    export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
    bash ~/dagbt_patches/webwalker_v4_v2/dagbt_webwalker_v4_v2_experiment/install_and_run.sh

入口依次完成独立安装、浏览器检查、WebWalker 离线夹具验证和真实服务预检，
然后在后台运行 WebWalker full。SSH 断开后继续运行。
默认新目标：~/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2。
不覆盖旧部署、旧 tar 或旧输出。不要对同一输出重复启动 full。

仅安装及离线检查时，将入口换为 install_and_offline.sh；该入口不调用真实模型。
两个入口均接受第一参数自定义目标，第二参数 --no-browser：

    bash install_and_offline.sh /独立/目标/dagv2 --no-browser

--no-browser 仅适用于目标已经有完整且可运行的浏览器依赖。
首次浏览器安装需要访问 PyPI 和 Chromium CDN；安装器不运行 sudo。

## 来源部署与 PersonaMem

默认来源为 ~/dagbt_runs/20261014_personamem_v4_experiment/dagv2，
可用 DAGBT_PERSONAMEM_BASE 指定。来源须满足固定公共核心基线；
私人凭据不在包内，只在服务器本地从来源部署复用，权限为 0600。
沿用已有可用 Python 环境，DAGBT_PYTHON 可指定解释器。

full 使用的 PersonaMem 输出默认为上述来源部署的
outputs/personamem_v4_experiment_full，可用 PERSONAMEM_OUTPUT 指定。
该输出必须有 progress.json，状态为 complete、complete_with_failures 或 stopped，
且没有活跃 writer。安装和离线检查本身不要求运行 PersonaMem。

## 状态、日志、停止与恢复

    cd ~/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2
    bash scripts/run_webwalker.sh status
    tail -f outputs/webwalkerqa_v4_access_v13_full/launcher.log
    bash scripts/run_webwalker.sh stop outputs/webwalkerqa_v4_access_v13_full

启动后用状态和日志确认。停止后等 live_writer、live_scorer 均为 false；
同源码、配置、PersonaMem 路径及输出目录下再次执行：

    bash scripts/run_webwalker.sh full

已终态任务复用；已经开始但未正常发布结果的任务保留失败，不自动重试。
WEBWALKER_OUTPUT 可指定 WebWalker 输出；恢复时保持一致。
stop 的第二参数必须明确传入 WebWalker 输出路径；full 第二参数则是 PersonaMem 输出。
progress.state=complete 表示生成完成；评分另看 live_scorer、日志及 evaluation.json。
单题日志与结果位于 tasks/<题>/<组>/，完整调用和成本明细保留在同一任务目录。

轻量包移除了未使用的模块，因此 source manifest 的文件集合不同于双数据集包。
必须使用本包的新目标与全新输出，不能复用旧双数据集输出继续生成或评分。
