"""工作空间（Workspace）管理：用户注册/登录 + 密码哈希 + 数据迁移。

设计原则：
- 每个注册用户 = 一个独立 workspace 子目录，内含独立的 court_matters.db
- 密码哈希用 hashlib.pbkdf2_hmac（Python 标准库，零外部依赖）
- 旧数据自动迁移（幂等，仅首次执行）
"""

import hashlib
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from config import DATA_DIR, PROJECT_ROOT, STATIC_DIR

# ============================================================
# 路径常量
# ============================================================

WORKSPACE_META_DB = DATA_DIR / "workspaces.db"
WORKSPACES_DIR = DATA_DIR / "workspaces"

# ============================================================
# 密码哈希
# ============================================================

_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """对密码进行 pbkdf2_hmac 哈希。

    返回格式：{salt_hex}${hash_hex}
    """
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希。"""
    try:
        salt_hex, hash_hex = password_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
        )
        return dk == expected
    except (ValueError, AttributeError):
        return False


# ============================================================
# workspace 元数据库
# ============================================================

SCHEMA_WORKSPACE_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,              -- UUID4 短哈希（8 位），作为目录名
    name TEXT NOT NULL UNIQUE,        -- 用户可见的 workspace 名称
    password_hash TEXT NOT NULL,      -- pbkdf2_hmac 结果
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _get_meta_conn():
    """获取 workspace 元数据库连接。"""
    conn = sqlite3.connect(str(WORKSPACE_META_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_workspace_db():
    """初始化 workspace 元数据库（幂等）。"""
    WORKSPACE_META_DB.parent.mkdir(parents=True, exist_ok=True)
    with _get_meta_conn() as conn:
        conn.executescript(SCHEMA_WORKSPACE_SQL)


def create_workspace(name: str, password: str) -> str:
    """创建新 workspace。

    参数：
        name: workspace 名称（唯一）
        password: 明文密码（内部哈希存储）

    返回：
        workspace_id（8 位 UUID 短哈希）

    异常：
        ValueError: 同名 workspace 已存在
    """
    name = name.strip()
    if not name:
        raise ValueError("workspace 名称不能为空")
    if not password:
        raise ValueError("密码不能为空")

    with _get_meta_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            raise ValueError(f"用户名「{name}」已存在，请换一个名称")

        ws_id = uuid.uuid4().hex[:8]
        pw_hash = hash_password(password)
        conn.execute(
            "INSERT INTO workspaces (id, name, password_hash) VALUES (?, ?, ?)",
            (ws_id, name, pw_hash),
        )

    # 创建 workspace 目录结构
    ws_dir = WORKSPACES_DIR / ws_id
    for sub in ("", "outputs", "agents"):
        (ws_dir / sub).mkdir(parents=True, exist_ok=True)

    return ws_id


def verify_workspace(name: str, password: str) -> str | None:
    """验证 workspace 名称和密码。

    返回：
        workspace_id（验证通过）或 None（验证失败）
    """
    name = name.strip()
    with _get_meta_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM workspaces WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        if verify_password(password, row["password_hash"]):
            return row["id"]
        return None


def list_workspaces() -> list[dict]:
    """列出所有 workspace（不含密码哈希）。"""
    with _get_meta_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM workspaces ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# 旧数据迁移（幂等）
# ============================================================

def _get_legacy_db():
    """惰性获取旧 DB 路径（支持测试 monkeypatch）。"""
    return DATA_DIR / "court_matters.db"

def _get_legacy_outputs():
    return PROJECT_ROOT / "outputs"

def _get_legacy_agents():
    return STATIC_DIR / "agents"

def _get_migration_flag():
    return DATA_DIR / ".migration_done"


def migrate_legacy_data() -> str | None:
    """迁移旧版数据到默认 workspace（幂等）。

    检测：
        - data/court_matters.db 存在 + 标记文件不存在 → 执行迁移
        - 标记文件存在 → 跳过（幂等）

    迁移内容：
        1. data/court_matters.db → data/workspaces/<id>/court_matters.db
        2. outputs/           → data/workspaces/<id>/outputs/
        3. static/agents/     → data/workspaces/<id>/agents/

    返回：
        workspace_id（迁移成功）或 None（无需迁移 / 已迁移）
    """
    if _get_migration_flag().exists():
        return None

    if not _get_legacy_db().exists():
        # 没有旧数据，标记完成
        _get_migration_flag().write_text("done")
        return None

    # 创建默认 workspace
    try:
        ws_id = create_workspace("默认", "admin")
    except ValueError:
        # "默认" 已存在（可能是之前迁移失败后重试），跳过创建
        with _get_meta_conn() as conn:
            row = conn.execute(
                "SELECT id FROM workspaces WHERE name = ?", ("默认",)
            ).fetchone()
            ws_id = row["id"] if row else None
        if not ws_id:
            _get_migration_flag().write_text("done")
            return None

    ws_dir = WORKSPACES_DIR / ws_id

    # 1. 迁移 DB
    legacy_db = _get_legacy_db()
    if legacy_db.exists():
        try:
            shutil.move(str(legacy_db), str(ws_dir / "court_matters.db"))
        except OSError:
            pass  # 源文件可能已被移动

    # 2. 迁移 outputs/
    legacy_outputs = _get_legacy_outputs()
    if legacy_outputs.exists() and not (ws_dir / "outputs").exists():
        try:
            shutil.move(str(legacy_outputs), str(ws_dir / "outputs"))
        except OSError:
            pass

    # 3. 迁移 static/agents/
    legacy_agents = _get_legacy_agents()
    if legacy_agents.exists():
        target_agents = ws_dir / "agents"
        if not target_agents.exists() or not any(target_agents.iterdir()):
            try:
                # 移动目录内容而非目录本身（避免覆盖）
                for item in legacy_agents.iterdir():
                    dest = target_agents / item.name
                    if not dest.exists():
                        shutil.move(str(item), str(dest))
            except OSError:
                pass

    # 标记迁移完成
    _get_migration_flag().write_text("done")
    return ws_id