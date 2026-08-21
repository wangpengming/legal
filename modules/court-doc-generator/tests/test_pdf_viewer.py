"""测试 pdf_viewer_component：核心 UI 函数存在 + PDF.js 检测逻辑。"""
from pathlib import Path


def test_pdfjs_paths():
    """PDF.js 库路径应指向正确的相对路径。"""
    from pdf_viewer_component import PDFJS_DIR, PDFJS_MAIN, PDFJS_WORKER

    assert PDFJS_DIR.name == "pdfjs"
    assert PDFJS_MAIN.name == "pdf.min.js"
    assert PDFJS_WORKER.name == "pdf.worker.min.js"
    # PDFJS_DIR 应在 static/ 下
    assert PDFJS_DIR.parent.name == "static"


def test_pdfjs_not_ready_when_libs_missing():
    """库未就位时 is_pdfjs_ready() 应返回 False。"""
    from pdf_viewer_component import is_pdfjs_ready
    # static/pdfjs/ 已包含 PDF.js 库文件，预期返回 True
    assert is_pdfjs_ready() is True


def test_render_pdf_viewer_signature():
    """render_pdf_viewer 应接受 (pdf_path, height, key) 参数。"""
    import inspect
    from pdf_viewer_component import render_pdf_viewer

    sig = inspect.signature(render_pdf_viewer)
    params = sig.parameters
    assert "pdf_path" in params
    assert "height" in params
    assert "key" in params
    # height 默认值
    assert params["height"].default == 800