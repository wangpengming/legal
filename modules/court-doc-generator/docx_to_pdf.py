"""docx 转 PDF：用 reportlab 重新排版生成 PDF。

策略：读取 docx 的段落和 runs，提取对齐、字体大小等基础样式，
用 reportlab 重排版输出 PDF。中文字体按平台自适应探测（macOS 仿宋/宋体、
Linux Noto CJK、Windows 宋体/黑体），reportlab 自动嵌入字体子集，
确保 PDF 在任何操作系统打印都能正常显示
（之前用 reportlab 内置的 STSong-Light CID 字体是伪字体，macOS 打印时找不到
对应字形导致 04/05 打印空白）。可用 FONT_DIR 环境变量指定自定义字体目录。
"""
import os
import sys
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
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def _font_candidates() -> list:
    """探测可用的中文字体文件，返回 (路径, subfontIndex) 候选列表（多平台自适应）。

    优先级：
    1. FONT_DIR 环境变量指向的目录（扫描 *.ttf / *.ttc / *.otf，排除隐藏文件）
    2. 平台内置字体：
       - macOS：Songti.ttc（face 0 = STSong，face 1 = STFangsong）/ STFangsong TTF
       - Linux：Noto CJK、文泉驿微米黑、AR PL UMing、DroidSansFallback 常见路径
       - Windows：SimSun / SimHei / Microsoft YaHei
    全部候选失败时由调用方回退 CID 字体（保证 PDF 可生成，打印可能空白）。
    """
    candidates = []

    # 1. FONT_DIR 环境变量（server 部署时可将字体文件放进指定目录，优先级最高）
    font_dir = os.environ.get("FONT_DIR", "").strip()
    if font_dir:
        d = Path(font_dir)
        if d.is_dir():
            for pattern in ("*.ttf", "*.ttc", "*.otf"):
                for p in sorted(d.glob(pattern)):
                    if p.name.startswith("."):
                        continue
                    candidates.append((str(p), 0))
            if candidates:
                return candidates  # FONT_DIR 命中即独占返回；目录空/缺失时回退平台候选

    # 2. 平台内置字体
    if sys.platform == "darwin":
        candidates.extend(
            [
                # Songti.ttc（face 0 = STSong 宋体，face 1 = STFangsong 仿宋）
                ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
                # STFangsong（仿宋，TTF 格式，macOS 自带，docx 模板原意）
                ("/System/Library/AssetsV2/com_apple_MobileAsset_Font8/1b6b2f148cdf17dd0d788706c83c61ca1998c3a6.asset/AssetData/STFANGSO.ttf", 0),
            ]
        )
    elif sys.platform.startswith("linux"):
        candidates.extend(
            [
                ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
                ("/usr/share/fonts/truetype/noto/NotoSerifCJKsc-Regular.otf", 0),
                ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
                ("/usr/share/fonts/truetype/arphic/uming.ttc", 0),
                ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 0),
            ]
        )
    elif sys.platform.startswith("win"):
        candidates.extend(
            [
                ("C:/Windows/Fonts/simsun.ttc", 0),
                ("C:/Windows/Fonts/simhei.ttf", 0),
                ("C:/Windows/Fonts/msyh.ttc", 0),
            ]
        )
    return candidates


def _register_cn_font() -> tuple:
    """注册中文字体（真实 TTF 嵌入子集，多平台自适应）。

    返回 (字体名, 来源描述)。不依赖任何单一平台路径：
    FONT_DIR 环境变量 → 平台内置候选 → CID 字体 fallback。
    """
    for path, face_index in _font_candidates():
        try:
            if not Path(path).exists():
                continue
            font = TTFont("CN-Font", path, subfontIndex=face_index)
            pdfmetrics.registerFont(font)
            return "CN-Font", path
        except Exception:
            continue
    # Fallback：reportlab CID 字体（macOS 打印会空白，但保证 PDF 至少能生成）
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light", "CID STSong-Light（无真实字体文件，部分系统打印可能空白）"


CN_FONT, CN_FONT_SOURCE = _register_cn_font()


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
        fontName=CN_FONT,
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
                        ("FONT", (0, 0), (-1, -1), CN_FONT, 10),
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
