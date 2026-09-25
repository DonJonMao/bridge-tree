# 方法修订 PDF 核验记录

文件：`output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf`，共 12 页。

源稿：`docs/evidence_bridge_revision_report.md`；生成脚本：`scripts/build_evidence_bridge_pdf.py`。

使用 ReportLab 和嵌入的 STHeiti 字体生成，macOS PDFKit 以 1.65 倍渲染成逐页 PNG，再对全部 12 页逐页目视检查；最后文字更正后的第 5、6、11 页再次核验。正文、表格、页眉页脚、页码清晰，无截断、重叠、缺字或孤立溢出页。pypdf/PDFKit 都识别到 12 页，零替换字符，末页 5 个官方论文链接有效嵌入为 PDF 链接注释。

PDF SHA-256：`859b64752cd17c5fe6ccaec4c9c86200c4437e0811e85c0b017c48c20cd47415`。

| 页 | 主题 | 检查结果 |
|---|---|---|
| 1 | 修订目标、三个方向与交付 | 通过 |
| 2 | 原版日志分母与方法结果 | 通过 |
| 3 | 预算垄断与 activation 语义 | 通过 |
| 4 | 历史理由、已测集合遗漏 | 通过 |
| 5 | 正式顶会论文与适用边界 | 通过 |
| 6 | 完整数据流与信息边界 | 通过 |
| 7 | 双预算调度 | 通过 |
| 8 | 目标留存、探索与转向 | 通过 |
| 9 | 全文映射、整体选择和缺口反馈 | 通过 |
| 10 | 实时事件、快照与权威汇总 | 通过 |
| 11 | Linux 命令和本地验证边界 | 通过 |
| 12 | 文献链接与审计索引 | 通过 |

本地完整渲染与机器可读核验保存在 `outputs/operations_validation/pdf_render/`，其中 `visual_review.json` 包含每页 PNG SHA-256。旧 outputs 不进入服务器包；此核验说明和 PDF 源稿随包交付。PDF 描述本地验证，不声称运行过新版远端模型评测或取得准确率提升。

重新生成 PDF 时需要额外安装 reportlab；仅运行实验不需要该依赖。macOS 默认字体由脚本参数指定，Linux 重新排版时须用 `--font`、`--bold-font` 指定可用且支持中文的 TrueType 字体。服务器可直接使用已经生成并嵌入字体的 PDF。
