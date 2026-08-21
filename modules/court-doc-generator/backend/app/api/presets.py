"""F5 法院/案由预设库 API。"""
from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

router = APIRouter()

VALID_KINDS = ("court", "cause")


class PresetIn(BaseModel):
    kind: str
    value: str


class PresetOut(BaseModel):
    id: int
    kind: str
    value: str
    usage_count: int
    created_at: str | None = None


def register_preset(conn, workspace_id: str, kind: str, value: str):
    """案件保存时自动注册预设值：不存在则插入 usage_count=1，存在则 +1。

    供 cases.py 在同一事务连接内调用。
    """
    _ensure_table(conn)
    if not value:
        return None
    conn.execute(
        """INSERT INTO presets (workspace_id, kind, value, usage_count)
           VALUES (?, ?, ?, 1)
           ON CONFLICT(workspace_id, kind, value)
           DO UPDATE SET usage_count = usage_count + 1""",
        (workspace_id, kind, value),
    )
    return conn.execute(
        "SELECT id FROM presets WHERE workspace_id=? AND kind=? AND value=?",
        (workspace_id, kind, value),
    ).fetchone()["id"]


def _ensure_table(conn):
    """幂等建表：兼容未跑过新 init_db 的老 workspace DB。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            value TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, kind, value)
        )"""
    )


@router.get("", response_model=list[PresetOut])
def list_presets(
    kind: str = Query(default="court"),
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    from app.core.database import get_conn

    if kind not in VALID_KINDS:
        from fastapi import HTTPException

        raise HTTPException(400, f"kind 必须为 {'/'.join(VALID_KINDS)}")
    with get_conn(x_workspace_id) as conn:
        _ensure_table(conn)
        rows = conn.execute(
            """SELECT id, kind, value, usage_count, created_at
               FROM presets WHERE workspace_id = ? AND kind = ?
               ORDER BY usage_count DESC, id DESC""",
            (x_workspace_id, kind),
        ).fetchall()
        return [PresetOut(**dict(r)) for r in rows]


@router.post("", response_model=PresetOut)
def create_preset(body: PresetIn, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from fastapi import HTTPException
    from app.core.database import get_conn

    if body.kind not in VALID_KINDS:
        raise HTTPException(400, f"kind 必须为 {'/'.join(VALID_KINDS)}")
    if not body.value.strip():
        raise HTTPException(400, "value 不能为空")
    with get_conn(x_workspace_id) as conn:
        _ensure_table(conn)
        existing = conn.execute(
            "SELECT * FROM presets WHERE workspace_id=? AND kind=? AND value=?",
            (x_workspace_id, body.kind, body.value.strip()),
        ).fetchone()
        if existing:
            return PresetOut(**dict(existing))
        conn.execute(
            "INSERT INTO presets (workspace_id, kind, value) VALUES (?, ?, ?)",
            (x_workspace_id, body.kind, body.value.strip()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM presets WHERE id = last_insert_rowid()"
        ).fetchone()
        return PresetOut(**dict(row))


@router.post("/{preset_id}/bump")
def bump_preset(preset_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from fastapi import HTTPException
    from app.core.database import get_conn

    with get_conn(x_workspace_id) as conn:
        _ensure_table(conn)
        cur = conn.execute(
            "UPDATE presets SET usage_count = usage_count + 1 WHERE id = ? AND workspace_id = ?",
            (preset_id, x_workspace_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "预设不存在")
    return {"ok": True}


@router.delete("/{preset_id}")
def delete_preset(preset_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from fastapi import HTTPException
    from app.core.database import get_conn

    with get_conn(x_workspace_id) as conn:
        _ensure_table(conn)
        cur = conn.execute(
            "DELETE FROM presets WHERE id = ? AND workspace_id = ?",
            (preset_id, x_workspace_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "预设不存在")
    return {"ok": True}