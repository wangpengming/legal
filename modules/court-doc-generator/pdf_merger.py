"""PDF 合并工具：用 pypdf 按顺序合并多个 PDF 文件。"""
from pathlib import Path

from pypdf import PdfWriter


def merge_pdfs(pdf_paths: list, output_path: Path) -> Path:
    """按顺序合并多个 PDF 文件，返回输出路径。"""
    writer = PdfWriter()
    appended = 0
    for pdf_path in pdf_paths:
        if pdf_path is None or not Path(pdf_path).exists():
            continue
        writer.append(str(pdf_path))
        appended += 1
    if appended == 0:
        raise ValueError("没有任何可合并的 PDF 文件")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
