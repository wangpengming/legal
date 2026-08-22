"""F6 操作日志：写入 + 查询 + PII 遮罩。"""
import re
import sqlite3

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()

# 15/18 位身份证号（18 位末位可为 X）
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{15}|\d{17}[\dXx])(?![\dXx])")


class AuditLogOut(BaseModel):
    id: int
    username: str
    action: str
    target: str
    result: str
    created_at: str | None = None


def mask_pii(text: str) -> str:
    """遮罩文本中的身份证号：前4位****后4位（不足 8 位原样返回）。"""
    if not text:
        return text

    def _mask(match: re.Match) -> str:
        s = match.group(0)
        if len(s) < 8:
            return s
        return s[:4] + "*" * (len(s) - 8) + s[-4:]

    return _ID_CARD_RE.sub(_mask, text)


def _ensure_table(conn):
    """幂等建表：兼容未跑过新 init_db 的老 workspace DB。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            result TEXT DEFAULT 'ok',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )


def get_workspace_name(workspace_id: str) -> str:
    """workspace 名（meta DB），找不到则回退为 id。"""
    conn = sqlite3.connect(str(settings.DATA_DIR / "workspaces.db"))
    try:
        row = conn.execute(
            "SELECT name FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else workspace_id


def log_action(
    workspace_id: str,
    action: str,
    target: str,
    result: str = "ok",
    username: str | None = None,
):
    """写一条操作日志（target 统一做 PII 遮罩）。"""
    from app.core.database import get_conn

    if username is None:
        username = get_workspace_name(workspace_id)
    with get_conn(workspace_id) as conn:
        _ensure_table(conn)
        conn.execute(
            """INSERT INTO audit_logs (workspace_id, username, action, target, result)
               VALUES (?, ?, ?, ?, ?)""",
            (workspace_id, username, action, mask_pii(target), result),
        )
        conn.commit()


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    from app.core.database import get_conn

    with get_conn(x_workspace_id) as conn:
        _ensure_table(conn)
        rows = conn.execute(
            """SELECT id, username, action, target, result, created_at
               FROM audit_logs WHERE workspace_id = ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (x_workspace_id, limit, offset),
        ).fetchall()
        return [AuditLogOut(**dict(r)) for r in rows]