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
    files: Annotated[list[UploadFile] | None, File(description="上传法律文书图片或 PDF（支持多文件，多图信息自动合并识别）")] = None,
    file: Annotated[UploadFile | None, File(description="单文件兼容参数（旧版前端使用）")] = None,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """拍照扫描入口：接收一个或多个文件，OCR 合并识别并抽取字段。

    起诉状往往多页/多图，各文件依次转图片后交由 scan_service
    extract_text 统一拼接识别，字段从合并文本中抽取。
    """
    targets = list(files) if files else []
    if file is not None:
        targets.append(file)
    if not targets:
        return ScanOut(text="", fields={}, error="未收到文件，请选择图片或 PDF 上传")

    import uuid
    _RUN_DIR.mkdir(exist_ok=True)

    img_paths: list[Path] = []
    cleanup_paths: list[Path] = []
    cleanup_dirs: list[Path] = []

    try:
        for i, up in enumerate(targets):
            content_type = up.content_type or ""
            if content_type not in ALLOWED_TYPES:
                return ScanOut(text="", fields={}, error=f"第 {i+1} 个文件类型不支持: {content_type}，仅支持 jpg/png/pdf")
            try:
                content = await up.read()
            except Exception as e:
                return ScanOut(text="", fields={}, error=f"读取第 {i+1} 个文件失败: {e}")
            if len(content) > MAX_FILE_SIZE:
                return ScanOut(text="", fields={}, error=f"第 {i+1} 个文件超过 20MB 限制")
            if len(content) == 0:
                return ScanOut(text="", fields={}, error=f"第 {i+1} 个文件为空")

            ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png"}.get(content_type, "bin")
            # macOS sandbox 下 subprocess 无法访问 /tmp/，用 .run/ 目录
            tmp_path = _RUN_DIR / f"scan_{uuid.uuid4().hex}.{ext}"
            tmp_path.write_bytes(content)
            cleanup_paths.append(tmp_path)

            if content_type == "application/pdf":
                pdf_tmp_dir = _RUN_DIR / f"scan_pdf_{uuid.uuid4().hex}"
                pdf_tmp_dir.mkdir(exist_ok=True)
                cleanup_dirs.append(pdf_tmp_dir)
                imgs = _pdf_to_images(tmp_path, pdf_tmp_dir)
                if not imgs:
                    return ScanOut(text="", fields={}, error=f"第 {i+1} 个 PDF 解析失败，请确保为可识别图片的 PDF")
                img_paths.extend(imgs)
            else:
                img_paths.append(tmp_path)

        if not img_paths:
            return ScanOut(text="", fields={}, error="没有可识别的图片")

        text = extract_text(img_paths)
        if not text.strip():
            return ScanOut(text="", fields={}, error="OCR 未识别到文字，请确认图片清晰")
        fields = extract_fields(text)
        return ScanOut(text=text, fields=fields, error=None)
    except Exception as e:
        return ScanOut(text="", fields={}, error=f"OCR 处理失败: {e}")
    finally:
        for p in cleanup_paths:
            p.unlink(missing_ok=True)
        for d in cleanup_dirs:
            try:
                shutil.rmtree(d)
            except Exception:
                pass


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
