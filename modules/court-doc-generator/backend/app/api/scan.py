"""拍照扫描 OCR API（封装 scan_service.py）。"""
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, UploadFile, File
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from scan_service import extract_text, extract_fields

router = APIRouter()

# macOS sandbox 限制 subprocess 访问 /tmp/，用项目 .run/ 目录
_RUN_DIR = Path(__file__).parent.parent.parent.parent / ".run"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}
_PDFTOPPM = shutil.which("pdftoppm") or "/opt/homebrew/bin/pdftoppm"


def _pdf_to_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """用 pdftoppm 将 PDF 每页转为 PNG，返回图片路径列表。"""
    imgs = []
    try:
        result = subprocess.run(
            [_PDFTOPPM, "-png", "-r", "200", str(pdf_path), str(out_dir / "page")],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            imgs = sorted(out_dir.glob("page-*.png"))
    except Exception:
        pass
    return imgs


class ScanIn(BaseModel):
    url: str


class ScanOut(BaseModel):
    text: str
    fields: dict
    error: str | None = None


@router.post("/scan", response_model=ScanOut)
async def scan_image(
    file: Annotated[UploadFile, File(description="上传法律文书图片或 PDF")],
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """拍照扫描入口：接收本地文件上传，OCR 识别并抽取字段。"""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        return ScanOut(text="", fields={}, error=f"不支持的文件类型: {content_type}，仅支持 jpg/png/pdf")

    try:
        content = await file.read()
    except Exception as e:
        return ScanOut(text="", fields={}, error=f"读取文件失败: {e}")

    if len(content) > MAX_FILE_SIZE:
        return ScanOut(text="", fields={}, error="文件超过 20MB 限制")
    if len(content) == 0:
        return ScanOut(text="", fields={}, error="文件为空")

    ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png"}.get(content_type, "bin")

    try:
        # macOS sandbox 下 subprocess 无法访问 /tmp/，用 .run/ 目录
        _RUN_DIR.mkdir(exist_ok=True)
        import uuid
        tmp_name = _RUN_DIR / f"scan_{uuid.uuid4().hex}.{ext}"
        tmp_name.write_bytes(content)
        input_path = tmp_name
    except Exception as e:
        return ScanOut(text="", fields={}, error=f"创建临时文件失败: {e}")

    img_paths: list[Path] = []
    try:
        if content_type == "application/pdf":
            pdf_tmp_dir = _RUN_DIR / f"scan_pdf_{uuid.uuid4().hex}"
            pdf_tmp_dir.mkdir(exist_ok=True)
            imgs = _pdf_to_images(input_path, pdf_tmp_dir)
            if not imgs:
                return ScanOut(text="", fields={}, error="PDF 解析失败，请确保为可识别图片的 PDF")
            img_paths = imgs
        else:
            img_paths = [input_path]

        text = extract_text(img_paths)
        if not text.strip():
            return ScanOut(text="", fields={}, error="OCR 未识别到文字，请确认图片清晰")
        fields = extract_fields(text)
        return ScanOut(text=text, fields=fields, error=None)
    except Exception as e:
        return ScanOut(text="", fields={}, error=f"OCR 处理失败: {e}")
    finally:
        input_path.unlink(missing_ok=True)
        if content_type == "application/pdf":
            import shutil as _sh
            try: _sh.rmtree(pdf_tmp_dir) 
            except: pass


@router.post("/scan-url", response_model=ScanOut)
def scan_url(
    body: ScanIn,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """通过 URL 扫描图片（OCR）。"""
    try:
        from scan_service import download_and_scan_url
        result = download_and_scan_url(body.url)
        return ScanOut(
            text=result.get("text", ""),
            fields=result.get("fields", {}),
            error=result.get("error"),
        )
    except Exception as e:
        return ScanOut(text="", fields={}, error=str(e))
