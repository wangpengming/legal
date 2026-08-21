"""在线打印 API — 调系统打印机（macOS lp / Linux lp / Windows Start-Process）。"""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class PrintRequest(BaseModel):
    file_path: str  # 相对路径，如 workspaces/<ws_id>/outputs/<case>/merged.pdf


@router.post("/")
def print_pdf(req: PrintRequest):
    """把 PDF 直接送到系统默认打印机。

    前端可同时提供浏览器打印（window.print）= 预览 + 选打印机，本接口是无弹窗直送。
    """
    from app.core.config import settings

    full_path = (settings.DATA_DIR / req.file_path).resolve()

    # 安全检查：禁止路径穿越
    if not str(full_path).startswith(str(settings.DATA_DIR)):
        raise HTTPException(403, "禁止访问")

    if not full_path.exists():
        raise HTTPException(404, f"文件不存在: {req.file_path}")

    if full_path.suffix.lower() != ".pdf":
        raise HTTPException(400, "仅支持 PDF 打印")

    # 调 generator.py 中的 print_pdf_to_default_printer
    sys.path.insert(0, str(settings.MODULE_ROOT))
    from generator import print_pdf_to_default_printer

    success, msg = print_pdf_to_default_printer(full_path)
    if success:
        return {"code": 0, "message": msg}
    else:
        raise HTTPException(500, msg)