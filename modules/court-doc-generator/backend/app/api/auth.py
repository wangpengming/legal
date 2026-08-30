"""认证 API（workspace 登录/注册/登出）。"""
import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()

# ── workspace 元数据 DB（独立于业务 DB）──────────────────────────────────
_WS_DB = settings.DATA_DIR / "workspaces.db"  # 复用 Streamlit workspace.py 的 DB


def _init_ws_meta():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(str(_WS_DB))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"{salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


# 启动时初始化
_init_ws_meta()


# ── 请求/响应模型 ─────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    name: str
    password: str


class LoginIn(BaseModel):
    name: str
    password: str


class WorkspaceOut(BaseModel):
    id: str
    name: str
    created_at: str | None = None


class LoginOut(BaseModel):
    workspace_id: str
    workspace_name: str
    token: str  # 简单 session token


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


# ── 端点 ─────────────────────────────────────────────────────────────────
@router.post("/register", response_model=LoginOut)
def register(body: RegisterIn):
    if len(body.name) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if len(body.password) < 4:
        raise HTTPException(400, "密码至少 4 个字符")

    import sqlite3
    conn = sqlite3.connect(str(_WS_DB))
    conn.row_factory = sqlite3.Row
    existing = conn.execute(
        "SELECT id FROM workspaces WHERE name = ?", (body.name,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(409, "用户名已存在")

    ws_id = secrets.token_hex(8)
    pw_hash = _hash_password(body.password)
    conn.execute(
        "INSERT INTO workspaces (id, name, password_hash) VALUES (?, ?, ?)",
        (ws_id, body.name, pw_hash),
    )
    conn.commit()
    conn.close()

    # 创建 workspace 业务 DB（建表）
    from app.core.database import init_db
    init_db(ws_id)

    # 写默认公司「雷石」
    _ensure_leishi(ws_id)

    # F6 操作日志
    from app.api.audit import log_action
    log_action(ws_id, "register", f"workspace {ws_id}", username=body.name)

    token = secrets.token_hex(16)
    return LoginOut(workspace_id=ws_id, workspace_name=body.name, token=token)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn):
    import sqlite3
    conn = sqlite3.connect(str(_WS_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM workspaces WHERE name = ?", (body.name,)
    ).fetchone()
    conn.close()

    if not row or not _verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    # F6 操作日志
    from app.api.audit import log_action
    log_action(row["id"], "login", f"workspace {row['id']}", username=body.name)

    token = secrets.token_hex(16)
    return LoginOut(
        workspace_id=row["id"],
        workspace_name=row["name"],
        token=token,
    )


@router.put("/password")
def change_password(
    body: ChangePasswordIn,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """登录用户修改自己的密码（需验证旧密码）。"""
    import sqlite3
    if len(body.new_password) < 4:
        raise HTTPException(400, "新密码至少 4 个字符")

    conn = sqlite3.connect(str(_WS_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT password_hash FROM workspaces WHERE id = ?", (x_workspace_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "workspace 不存在")

    if not _verify_password(body.old_password, row["password_hash"]):
        conn.close()
        raise HTTPException(400, "旧密码错误")

    new_hash = _hash_password(body.new_password)
    conn.execute(
        "UPDATE workspaces SET password_hash = ? WHERE id = ?",
        (new_hash, x_workspace_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/list")
def list_workspaces() -> list[WorkspaceOut]:
    import sqlite3
    conn = sqlite3.connect(str(_WS_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, created_at FROM workspaces ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [WorkspaceOut(id=r["id"], name=r["name"], created_at=r["created_at"]) for r in rows]


def _ensure_leishi(ws_id: str):
    """写默认公司「雷石」（每个 workspace 都有），公司文件指向 static 默认文件。"""
    from app.core.database import get_conn, init_db

    init_db(ws_id)
    with get_conn(ws_id) as conn:
        existing = conn.execute(
            "SELECT id FROM companies WHERE name = '北京雷石天地电子技术股份有限公司'"
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO companies
                   (name, credit_code, legal_rep_name, legal_rep_position,
                    address, phone, business_license_path, legal_rep_cert_path,
                    legal_rep_id_card_path, is_default)
                   VALUES (
                     '北京雷石天地电子技术股份有限公司',
                     '91110108MA01234X7Y',
                     '马杰', '总经理',
                     '北京市朝阳区望京东园四区1号楼29层2901号10',
                     '010-84488000',
                     'static/1.营业执照复印件.pdf',
                     'static/2.法定代表人证明.pdf',
                     'static/法人身份证.pdf',
                     1)""",
            )
            conn.commit()
