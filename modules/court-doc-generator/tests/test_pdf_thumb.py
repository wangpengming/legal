"""pdf_thumb 单元测试：PyMuPDF 缩略图生成器。

覆盖：
- render_first_page_png：缺失文件返回 None；正常 PDF 返回 PNG 字节；PNG 以 \\x89PNG 开头
- render_first_page_base64：返回 base64 字符串；缺失文件返回 None
- render_all_pages_base64：返回 list；max_pages 截断；缺失文件返回 []
- page_count：缺失文件返回 0；正常 PDF 返回正确页数
"""
from pathlib import Path

import pytest

from pdf_thumb import (
    page_count,
    render_all_pages_base64,
    render_first_page_base64,
    render_first_page_png,
)


# ============================================================
# Fixture：用 reportlab 临时生成一个测试 PDF
# ============================================================

@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """生成一个 3 页测试 PDF（避免依赖外部资源）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    pdf_path = tmp_path / "sample.pdf"
    c = rl_canvas.Canvas(str(pdf_path), pagesize=A4)
    for i in range(3):
        c.drawString(100, 700, f"测试 PDF · 第 {i + 1} 页 · Page {i + 1}")
        c.drawString(100, 650, "ABCDEFG 中文测试 12345")
        c.showPage()
    c.save()
    return pdf_path


# ============================================================
# render_first_page_png
# ============================================================

def test_render_first_page_png_returns_png_bytes(sample_pdf: Path):
    """正常 PDF：返回 PNG 字节（PNG 头部 \\x89PNG）。"""
    png = render_first_page_png(sample_pdf)
    assert png is not None
    assert isinstance(png, bytes)
    assert len(png) > 100  # 不可能是空字节
    # PNG 文件签名：89 50 4E 47 0D 0A 1A 0A
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_first_page_png_missing_file_returns_none(tmp_path: Path):
    """缺失文件：返回 None（不抛异常）。"""
    png = render_first_page_png(tmp_path / "nope.pdf")
    assert png is None


def test_render_first_page_png_invalid_file_returns_none(tmp_path: Path):
    """损坏文件：返回 None（不抛异常，鲁棒降级）。"""
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a pdf at all")
    png = render_first_page_png(fake)
    assert png is None


def test_render_first_page_png_scale_affects_size(sample_pdf: Path):
    """scale 越大 → 输出 PNG 越大（至少要确认参数生效）。"""
    png_small = render_first_page_png(sample_pdf, scale=0.1)
    png_large = render_first_page_png(sample_pdf, scale=1.0)
    assert png_small is not None
    assert png_large is not None
    # 0.1x 应该比 1.0x 小很多（允许 PDF 压缩导致 10% 浮动）
    assert len(png_small) < len(png_large) * 0.5


# ============================================================
# render_first_page_base64
# ============================================================

def test_render_first_page_base64_returns_str(sample_pdf: Path):
    """正常 PDF：返回 base64 字符串。"""
    b64 = render_first_page_base64(sample_pdf)
    assert isinstance(b64, str)
    assert len(b64) > 100
    # base64 解码后必须是 PNG
    import base64
    decoded = base64.b64decode(b64)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_first_page_base64_missing_returns_none(tmp_path: Path):
    """缺失文件：返回 None。"""
    assert render_first_page_base64(tmp_path / "missing.pdf") is None


# ============================================================
# render_all_pages_base64
# ============================================================

def test_render_all_pages_base64_returns_list(sample_pdf: Path):
    """3 页 PDF：返回 3 个 base64。"""
    thumbs = render_all_pages_base64(sample_pdf)
    assert isinstance(thumbs, list)
    assert len(thumbs) == 3
    for t in thumbs:
        assert isinstance(t, str)
        assert len(t) > 100


def test_render_all_pages_base64_max_pages_truncates(sample_pdf: Path):
    """max_pages=2 → 返回 2 个（截断）。"""
    thumbs = render_all_pages_base64(sample_pdf, max_pages=2)
    assert len(thumbs) == 2


def test_render_all_pages_base64_missing_returns_empty_list(tmp_path: Path):
    """缺失文件：返回空列表（不抛异常）。"""
    thumbs = render_all_pages_base64(tmp_path / "missing.pdf")
    assert thumbs == []


# ============================================================
# page_count
# ============================================================

def test_page_count_returns_correct_count(sample_pdf: Path):
    """3 页 PDF：返回 3。"""
    assert page_count(sample_pdf) == 3


def test_page_count_missing_returns_zero(tmp_path: Path):
    """缺失文件：返回 0。"""
    assert page_count(tmp_path / "missing.pdf") == 0
