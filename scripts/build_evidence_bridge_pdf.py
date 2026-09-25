#!/usr/bin/env python3
"""Build the Chinese method-revision report from the maintained Markdown source."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#17334B")
TEAL = colors.HexColor("#167E88")
INK = colors.HexColor("#273746")
MUTED = colors.HexColor("#627482")
PALE = colors.HexColor("#EDF5F6")
WIDTH = A4[0] - 88


def inline(text: str) -> str:
    value = html.escape(text).replace("**", "")
    return re.sub(
        r"https?://[^\s<]+", lambda m: f'<link href="{m.group(0)}" color="#167E88">{m.group(0)}</link>', value
    )


def styles():
    common = dict(fontName="CJK", textColor=INK, wordWrap="CJK", alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", fontSize=10.15, leading=17.2, spaceAfter=9, **common),
        "title": ParagraphStyle(
            "title", fontSize=24, leading=32, spaceAfter=16, **{**common, "fontName": "CJKB", "textColor": NAVY}
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontSize=14.2, leading=22, spaceAfter=15, **{**common, "fontName": "CJKB", "textColor": TEAL}
        ),
        "h3": ParagraphStyle(
            "h3",
            fontSize=12,
            leading=19,
            spaceBefore=6,
            spaceAfter=7,
            **{**common, "fontName": "CJKB", "textColor": NAVY},
        ),
        "quote": ParagraphStyle("quote", fontSize=10.1, leading=17.2, spaceAfter=0, **common),
        "cell": ParagraphStyle("cell", fontSize=9.2, leading=14.6, spaceAfter=0, **common),
        "th": ParagraphStyle(
            "th", fontSize=9.4, leading=14.6, spaceAfter=0, **{**common, "fontName": "CJKB", "textColor": colors.white}
        ),
    }


def table(rows, style):
    n = len(rows[0])
    if n == 2:
        widths = [WIDTH * 0.265, WIDTH * 0.735]
    elif n == 3:
        widths = [WIDTH * 0.28, WIDTH * 0.36, WIDTH * 0.36]
    elif n == 4:
        widths = [WIDTH / 4] * 4
    elif n == 5:
        widths = [WIDTH * 0.32] + [WIDTH * 0.17] * 4
    else:
        widths = [WIDTH / n] * n
    cells = [[Paragraph(inline(item), style["th" if i == 0 else "cell"]) for item in row] for i, row in enumerate(rows)]
    value = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1)
    value.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F1F5F8"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#D2DEE5")),
            ]
        )
    )
    return value


def page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(44, height - 43, 29, 3, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("CJK", 8.4)
    canvas.drawString(82, height - 43, "BRIDGETREE  /  METHOD REVISION")
    canvas.drawRightString(width - 44, height - 43, "2026-09-23")
    canvas.setStrokeColor(colors.HexColor("#D9E2E8"))
    canvas.line(44, 43, width - 44, 43)
    canvas.setFont("CJK", 8)
    canvas.drawString(44, 28, "日志依据 · 方法设计 · 可追溯运行")
    canvas.drawRightString(width - 44, 28, f"{doc.page:02d}")
    canvas.restoreState()


def build(source: Path, output: Path, regular: str, bold: str) -> None:
    pdfmetrics.registerFont(TTFont("CJK", regular, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("CJKB", bold, subfontIndex=0))
    style = styles()
    pages = source.read_text(encoding="utf-8").split("<!-- page -->")
    story = []
    for page_index, content in enumerate(pages):
        if page_index:
            story.append(PageBreak())
        lines = content.strip().splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            index += 1
            if not line:
                continue
            if line.startswith("|"):
                rows = [[cell.strip() for cell in line.strip("|").split("|")]]
                while index < len(lines) and lines[index].strip().startswith("|"):
                    cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                        rows.append(cells)
                    index += 1
                story.extend([table(rows, style), Spacer(1, 13)])
            elif line.startswith("> "):
                quote = Table([[Paragraph(inline(line[2:]), style["quote"])]], colWidths=[WIDTH])
                quote.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), PALE),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
                            ("LEFTPADDING", (0, 0), (-1, -1), 13),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                            ("TOPPADDING", (0, 0), (-1, -1), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                        ]
                    )
                )
                story.extend([KeepTogether(quote), Spacer(1, 13)])
            else:
                key, text = "body", line
                for prefix, target in (("### ", "h3"), ("## ", "subtitle"), ("# ", "title")):
                    if line.startswith(prefix):
                        key, text = target, line[len(prefix) :]
                        break
                story.append(Paragraph(inline(text), style[key]))
        if page_index == 0:
            story.append(Spacer(1, 10))
            story.append(HRFlowable(width=WIDTH, thickness=1, color=TEAL))
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=66,
        bottomMargin=58,
        title="BridgeTree 机制修订：日志、文献与实现计划",
        author="BridgeTree 项目",
        pageCompression=1,
    )
    document.build(story, onFirstPage=page, onLaterPages=page)
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/evidence_bridge_revision_report.md")
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf/BridgeTree_Mechanism_Revision_20260923.pdf")
    parser.add_argument("--font", default="/System/Library/Fonts/STHeiti Light.ttc")
    parser.add_argument("--bold-font", default="/System/Library/Fonts/STHeiti Medium.ttc")
    args = parser.parse_args()
    build(args.source, args.output, args.font, args.bold_font)


if __name__ == "__main__":
    main()
