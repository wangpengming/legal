"""历史记录 API。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


class HistoryOut(BaseModel):
    id: int
    case_id: int
    workspace_id: str | None = None
    output_dir: str
    created_at: str | None = None


@router.get("", response_model=list[HistoryOut])
def list_history(x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(generation_history)")}
        # 兼容不同 schema
        created_col = "created_at" if "created_at" in cols else ("generated_at" if "generated_at" in cols else None)
        ws_col = "workspace_id" if "workspace_id" in cols else None
        sel = "id, case_id"
        if ws_col:
            sel += ", workspace_id"
        sel += ", output_dir"
        if created_col:
            sel += f", {created_col} as created_at"
        order_col = created_col or "id"
        rows = conn.execute(f"SELECT {sel} FROM generation_history ORDER BY {order_col} DESC").fetchall()
        results = []
        for r in rows:
            d = dict(r)
            results.append(HistoryOut(
                id=d["id"], case_id=d.get("case_id", 0),
                workspace_id=d.get("workspace_id") or x_workspace_id,
                output_dir=d["output_dir"],
                created_at=d.get("created_at"),
            ))
        return results


@router.delete("/{record_id}")
def delete_history(record_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    with get_conn(x_workspace_id) as conn:
        conn.execute("DELETE FROM generation_history WHERE id = ?", (record_id,))
        conn.commit()
    return {"ok": True}


@router.get("/{record_id}/files")
def list_history_files(record_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    from app.core.config import settings
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT output_dir FROM generation_history WHERE id = ?", (record_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "记录不存在")
    output_dir = Path(row["output_dir"])
    if not output_dir.exists():
        return []
    files = []
    for f in sorted(output_dir.iterdir()):
        # 相对 DATA_DIR 的路径（含 workspaces/ 前缀），与 files API 拼接逻辑一致
        try:
            rel = f.relative_to(settings.DATA_DIR)
        except ValueError:
            rel = f
        files.append({
            "name": f.name,
            "path": str(rel),
            "size": f.stat().st_size,
            "is_pdf": f.suffix.lower() == ".pdf",
        })
    return files


@router.get("/{record_id}/download-zip")
def download_history_zip(record_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    import zipfile
    from app.core.database import get_conn
    import sqlite3
    import tempfile, os
    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT output_dir FROM generation_history WHERE id = ?", (record_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "记录不存在")
    output_dir = Path(row["output_dir"])
    if not output_dir.exists():
        raise HTTPException(404, "输出目录不存在")

    # 创建 ZIP
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in output_dir.iterdir():
            zf.write(f, f.name)

    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"出庭手续_{output_dir.name}.zip",
    )
