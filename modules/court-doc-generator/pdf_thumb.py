"""PDF 缩略图生成器（PyMuPDF）。

设计要点（中天经验总结，task-018.jsonl）：
- 用 `pymupdf` 不用 `fitz`（fitz 已废弃，PyMuPDF 官方 1.21+ 推荐 pymupdf）
- 缩放 0.4x（约 240x340 像素/张，base64 < 50KB）
- 渲染为 PNG 字节 → base64 内联到 st.image（避开 Streamlit SPA 路由拦截）
- 仅渲染 PDF 首页，避免大文件卡顿
- 失败降级：返回 None，UI 显示"缩略图生成失败"

为什么不用 PDF.js 渲染为缩略图？
- PDF.js 在 iframe sandbox 里 CMap 字体加载警告影响中文
- st.image(PDF.js 渲染产物) 会被 SPA 路由拦截
- 直接 PyMuPDF 渲染为 PNG 是 100% 可靠的方案
"""
import base64
from pathlib import Path

import pymupdf  # PyMuPDF 1.21+ 官方导入名（替代已废弃的 fitz）


def render_first_page_png(pdf_path: Path, scale: float = 0.4) -> bytes | None:
    """把 PDF 首页渲染为 PNG 字节。

    参数：
        pdf_path: PDF 文件路径
        scale: 缩放倍数（0.4 ≈ 240x340 像素）

    返回：
        PNG 字节，失败返回 None
    """
    if not pdf_path.exists():
        return None
    try:
        doc = pymupdf.open(str(pdf_path))
        try:
            page = doc[0]  # 首页
            mat = pymupdf.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)  # RGB 无 alpha，更小
            return pix.tobytes("png")
        finally:
            doc.close()
    except Exception:  # noqa: BLE001
        return None


def render_first_page_base64(pdf_path: Path, scale: float = 0.4) -> str | None:
    """把 PDF 首页渲染为 base64 字符串（可直接传给 st.image）。

    参数：
        pdf_path: PDF 文件路径
        scale: 缩放倍数

    返回：
        base64 字符串，失败返回 None
    """
    png_bytes = render_first_page_png(pdf_path, scale)
    if png_bytes is None:
        return None
    return base64.b64encode(png_bytes).decode("ascii")


def render_all_pages_base64(pdf_path: Path, scale: float = 0.3, max_pages: int = 7) -> list[str]:
    """把 PDF 多页渲染为 base64 字符串列表（用于缩略图网格）。

    参数：
        pdf_path: PDF 文件路径
        scale: 缩放倍数（多页时建议 0.3 更小）
        max_pages: 最多渲染几页

    返回：
        base64 字符串列表；失败/缺失页返回空列表
    """
    if not pdf_path.exists():
        return []
    try:
        doc = pymupdf.open(str(pdf_path))
        try:
            n = min(len(doc), max_pages)
            mat = pymupdf.Matrix(scale, scale)
            results = []
            for i in range(n):
                pix = doc[i].get_pixmap(matrix=mat, alpha=False)
                results.append(base64.b64encode(pix.tobytes("png")).decode("ascii"))
            return results
        finally:
            doc.close()
    except Exception:  # noqa: BLE001
        return []


def page_count(pdf_path: Path) -> int:
    """获取 PDF 页数（失败返回 0）。"""
    if not pdf_path.exists():
        return 0
    try:
        doc = pymupdf.open(str(pdf_path))
        try:
            return len(doc)
        finally:
            doc.close()
    except Exception:  # noqa: BLE001
        return 0
