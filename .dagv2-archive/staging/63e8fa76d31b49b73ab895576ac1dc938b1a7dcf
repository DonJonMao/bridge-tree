当前建议已更新：先不启动全量。逐次轨迹确认规划修复丢失输出要求，以及导航/阅读闭环缺陷；详见 FAILURE_ANALYSIS.md。下文启动方式仅保留为操作记录。

access_v4 验证结果

源码：1175175084315d9d6e2b307e18d772fb1b340f73；已推送。

完整回归2532项、解压安装测试151项通过；107个公共核心文件保持基线一致。最终tar再次干净安装及离线两组通过。

本地真实smoke四任务全部终止并独立评分：JOINT两题预算耗尽；RESIDUAL一题预算耗尽、一题生成地点但漏了时间。两组均0/2。未观察到原先的规划类型错误或实际修复输入溢出；单次付费恢复分支由回归夹具覆盖，本次真实sample没有触发。生成阶段物理LLM响应87次，usage缺失0；汇总token已与原始日志逐条核对。

这不是Linux全量结果，答题准确率问题未宣称解决。上传包、校验文件、START_WEBWALKER_ACCESS_V4.sh后，在Linux执行 `bash ~/bt/START_WEBWALKER_ACCESS_V4.sh` 真正启动680题×两组，再比较evaluation.json的准确率和generation_summary.json的成本。完整命令及缺库处理见SERVER_START.md。
