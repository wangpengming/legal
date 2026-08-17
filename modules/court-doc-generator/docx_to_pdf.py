"""docx 转 PDF：用 reportlab 重新排版生成 PDF。

策略：读取 docx 的段落和 runs，提取对齐、字体大小等基础样式，
用 reportlab 重排版输出 PDF。中文用 reportlab 内置的 STSong-Light CID 字体。
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


# 注册中文字体（只注册一次）
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def _get_alignment(para) -> int:
    align_map = {
        WD_ALIGN_PARAGRAPH.LEFT: TA_LEFT,
        WD_ALIGN_PARAGRAPH.CENTER: TA_CENTER,
        WD_ALIGN_PARAGRAPH.RIGHT: TA_RIGHT,
    }
    return align_map.get(para.alignment, TA_LEFT)


def _get_first_run_font_size(para) -> float:
    for run in para.runs:
        if run.font.size:
            try:
                return run.font.size.pt
            except AttributeError:
                continue
    return 12


def _build_story(doc) -> list:
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=12,
        leading=24,
        alignment=TA_LEFT,
        firstLineIndent=2 * 12 * 1.5,  # 首行缩进 2 字符
    )
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=body_style,
        fontSize=18,
        leading=36,
        alignment=TA_CENTER,
        firstLineIndent=0,
        spaceAfter=12,
        spaceBefore=12,
    )
    right_style = ParagraphStyle(
        "ChineseRight",
        parent=body_style,
        alignment=TA_RIGHT,
        firstLineIndent=0,
    )
    no_indent_style = ParagraphStyle(
        "ChineseNoIndent",
        parent=body_style,
        firstLineIndent=0,
    )

    story = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            story.append(Spacer(1, 0.4 * cm))
            continue

        font_size = _get_first_run_font_size(para)
        align = _get_alignment(para)

        if font_size >= 16:
            style = title_style
        elif align == TA_CENTER:
            style = title_style if len(text) <= 25 else no_indent_style
        elif align == TA_RIGHT:
            style = right_style
        else:
            style = body_style

        story.append(Paragraph(text, style))

    # 表格
    for table in doc.tables:
        data = []
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            data.append(row_data)
        if data:
            t = Table(data)
            t.setStyle(
                TableStyle(
                    [
                        ("FONT", (0, 0), (-1, -1), "STSong-Light", 10),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(t)
            story.append(Spacer(1, 0.5 * cm))

    return story


def docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    """把 docx 文件转成 PDF 文件。"""
    doc = Document(str(docx_path))
    story = _build_story(doc)

    left_margin = right_margin = 2.5 * cm
    top_margin = bottom_margin = 2.5 * cm

    doc_pdf = BaseDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )
    page_width, page_height = A4
    frame = Frame(
        left_margin,
        bottom_margin,
        page_width - left_margin - right_margin,
        page_height - top_margin - bottom_margin,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc_pdf.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    doc_pdf.build(story)
