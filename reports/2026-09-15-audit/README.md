# BridgeTree 实验审计报告材料

本目录用于 2026-09-15 的只读实验审计、文献核查与 PDF 报告制作。
不修改实验实现、当前配置或服务器运行状态。

## 证据边界

- 实验结果来自 `/Users/mao/chain-audit-full.tgz` 的逐任务 outcomes；
  summary/current 是独立刷新快照，允许存在少量时点差异。
- 机制案例来自 `/Users/mao/chain-audit-detail.tgz`，共三个诊断案例，
  不能据此估计整个数据集的问题发生率。
- 代码位置以本地工作树为准，运行身份以归档 manifest 的 source/config/data hash 为准。
- 论文核查时间为 2026-09-15；采用 2025–2026 正式会议年份，不把未确认投稿当已接收论文。

## 文档制作

已读取 documents 技能及其设计、创建、验证指南。由于环境没有该技能所需的
受管文档依赖运行时和 LibreOffice，采用 HTML + 独立临时 Chrome profile 直接
打印 PDF 的替代方案，再使用系统 PDFKit 离线逐页生成 PNG 并检查。

设计沿用 standard_business_brief / memo_masthead 的克制研究备忘风格。
PDF 原生样式覆盖：中文 PingFang SC / Hiragino Sans GB，正文字号 10.5–11 pt，
Letter 纸张，1 英寸页边距；使用语义标题、真实列表、比较表及低对比度页眉页脚。

## 当前本地诊断测试

2026-09-15：

- `pytest tests/test_dependency_search.py tests/test_dependency_scoring.py`：42 passed。
- `pytest tests/test_clients.py`：21 passed。

这 63 个离线单元测试仅验证其覆盖的实现行为，不验证远端服务可靠性、
真实历史证据充分性或方法的统计优越性。
