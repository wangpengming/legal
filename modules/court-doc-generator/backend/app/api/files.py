"""静态文件服务 API（workspace 数据目录文件访问 + 系统模板文件访问）。"""
import base64
import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter()

# 模板文件映射（模板名 → 文件名）
TEMPLATE_FILES = {
    "power_of_attorney": "4.授权委托书.docx",
    "recommendation": "5.推荐信.docx",
}


@router.get("/templates/{template_name}")
def serve_template_file(template_name: str):
    """返回系统内置模板文件（转 PDF 后在线预览）。
    
    template_name: power_of_attorney / recommendation
    先把 docx 转成 PDF，再用 PDF.js 在浏览器预览。
    """
    if template_name not in TEMPLATE_FILES:
        raise HTTPException(404, f"未知模板: {template_name}")
    
    from app.core.config import settings
    
    template_path = settings.TEMPLATES_DIR / TEMPLATE_FILES[template_name]
    if not template_path.exists():
        raise HTTPException(404, f"模板文件不存在: {TEMPLATE_FILES[template_name]}")
    
    # 把 docx 转成 PDF（临时文件）
    import sys
    sys.path.insert(0, str(settings.MODULE_ROOT))
    from docx_to_pdf import docx_to_pdf
    
    tmp_pdf_path = Path(tempfile.gettempdir()) / f"template_{template_name}.pdf"
    
    # 删除旧文件（如果存在）
    if tmp_pdf_path.exists():
        tmp_pdf_path.unlink()
    
    # 转换
    docx_to_pdf(template_path, tmp_pdf_path)
    
    # 使用 ASCII 文件名避免 Content-Disposition latin-1 编码问题
    pdf_filename = TEMPLATE_FILES[template_name].replace(".docx", ".pdf")
    ascii_filename = f"{template_name}.pdf"  # power_of_attorney.pdf / recommendation.pdf
    
    return FileResponse(
        str(tmp_pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=utf-8''{ascii_filename}"},
        background=None,
    )


@router.get("/{path:path}")
def serve_workspace_file(
    request: Request,
    path: str,
    x_workspace_id: str | None = Header(alias="X-Workspace-Id", default=None),
):
    """返回 workspace 数据目录下的文件（用于 PDF 预览）。

    path 支持两种格式：
    1. Base64+URL编码（如前端 btoa(encodeURIComponent(path))）
    2. 普通URL编码（备用）

    workspace ID 支持两种传参方式：
    1. Header X-Workspace-Id（推荐）
    2. Query ?ws=（用于 PDF.js 或直接 URL 访问）
    """
    # 解析 workspace ID
    ws_id = x_workspace_id
    if not ws_id and "ws=" in request.url.query:
        parts = request.url.query.split("=")
        if len(parts) >= 2:
            ws_id = parts[1].split("&")[0]
    if not ws_id:
        raise HTTPException(401, "缺少 workspace ID")

    # 解析路径：支持 hex 编码（始终安全）
    file_rel_path: str
    if path.startswith("~hex/"):
        # hex 编码格式：~hex/<hex>
        hex_str = path[5:]
        file_rel_path = bytes.fromhex(hex_str).decode("utf-8")
    else:
        # URL-safe base64 解码
        try:
            decoded = base64.urlsafe_b64decode(path + "===").decode("utf-8")
            file_rel_path = decoded
        except Exception:
            # 降级：URL 解码
            import urllib.parse
            file_rel_path = urllib.parse.unquote(path)

    from app.core.config import settings

    # 安全检查：只允许访问 workspace 数据目录
    # file_rel_path 格式：workspaces/<id>/...（前端已包含 workspaces 前缀）
    # 直接拼接：DATA_DIR / workspaces/<id>/... = DATA_DIR/workspaces/<id>/...
    base = settings.DATA_DIR  # /Users/.../court-doc-generator/data
    full_path = (base / file_rel_path).resolve()

    # 防止路径穿越
    if not str(full_path).startswith(str(base)):
        raise HTTPException(403, "禁止访问")

    if not full_path.exists():
        raise HTTPException(404, f"文件不存在: {file_rel_path}")

    media_type_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".zip": "application/zip",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    suffix = full_path.suffix.lower()
    media_type = media_type_map.get(suffix, "application/octet-stream")
    return FileResponse(str(full_path), media_type=media_type)
