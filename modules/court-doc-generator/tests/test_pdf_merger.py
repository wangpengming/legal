"""测试 pdf_merger.merge_pdfs。"""
import os
from pathlib import Path

import pytest

import pdf_merger


def test_merge_two_pdfs(tmp_path):
    """合并两份单页 PDF。"""
    # 用 reportlab 生成两份最简 PDF
    from reportlab.pdfgen import canvas
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"

    for p, label in [(pdf1, "A"), (pdf2, "B")]:
        c = canvas.Canvas(str(p))
        c.drawString(100, 750, f"PDF {label}")
        c.save()

    out = tmp_path / "merged.pdf"
    pdf_merger.merge_pdfs([pdf1, pdf2], out)
    assert out.exists()
    assert out.stat().st_size > 1000, "合并 PDF 应有内容"


def test_merge_with_nonexistent_file_raises(tmp_path):
    """输入文件不存在时（跳过所有文件后）抛 ValueError。"""
    with pytest.raises(ValueError):
        pdf_merger.merge_pdfs([tmp_path / "ghost.pdf"], tmp_path / "out.pdf")


def test_merge_empty_list_raises(tmp_path):
    """空列表应抛 ValueError。"""
    with pytest.raises(ValueError):
        pdf_merger.merge_pdfs([], tmp_path / "out.pdf")