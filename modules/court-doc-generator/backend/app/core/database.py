"""数据库封装（复用现有 database.py + workspace.py 逻辑）。"""
from contextlib import contextmanager
from pathlib import Path

import sqlite3

from app.core.config import settings


def _ws_db_path(workspace_id: str) -> Path:
    """workspace 业务 DB 路径。"""
    if not workspace_id or workspace_id in ("null", "undefined"):
        raise ValueError(f"无效的 workspace_id: {workspace_id!r}")
    p = settings.workspaces_dir / workspace_id / "court_matters.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def get_conn(workspace_id: str, db_path: Path | None = None):
    """获取 workspace 业务 DB 连接，自动初始化（幂等）。"""
    if db_path is None:
        db_path = _ws_db_path(workspace_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # 自动初始化：检测 companies 表是否存在（volumes 挂载前已存在的空 DB 需要补建表）
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='companies'"
        ).fetchone()
        if not tables:
            _init_db_from_schema(conn)
        # 迁移：每次连接都检查（避免新增列后未执行迁移）
        _run_migrations(conn)
        yield conn
    finally:
        conn.close()


def _init_db_from_schema(conn: sqlite3.Connection):
    """执行建表 schema（供 get_conn 和 init_db 共用）。"""
    schema = """
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        credit_code TEXT DEFAULT '',
        legal_rep_name TEXT DEFAULT '',
        legal_rep_position TEXT DEFAULT '',
        legal_rep_id_card TEXT DEFAULT '',
        address TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        is_default INTEGER DEFAULT 0,
        business_license_path TEXT DEFAULT '',
        legal_rep_id_card_path TEXT DEFAULT '',
        legal_rep_cert_path TEXT DEFAULT '',
        power_of_attorney_path TEXT DEFAULT '',
        recommendation_path TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        id_card TEXT DEFAULT '',
        id_card_pdf_path TEXT DEFAULT '',
        labor_contract TEXT DEFAULT '',
        contract_pdf_path TEXT DEFAULT '',
        company_id INTEGER DEFAULT NULL,
        is_default INTEGER DEFAULT 0,
        gender TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, company_id)
    );

    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_number TEXT NOT NULL,
        court TEXT DEFAULT '',
        cause TEXT DEFAULT '',
        hearing_date TEXT DEFAULT '',
        opposing_party TEXT DEFAULT '',
        our_role TEXT DEFAULT '原告',
        company_id INTEGER,
        agent_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS generation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        workspace_id TEXT NOT NULL,
        output_dir TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        value TEXT NOT NULL,
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (workspace_id, kind, value)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT NOT NULL,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        result TEXT DEFAULT 'ok',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    conn.executescript(schema)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    if "is_default" not in cols:
        conn.execute("ALTER TABLE companies ADD COLUMN is_default INTEGER DEFAULT 0")
    # 补建 unique index（已有表可能缺）
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")
    except Exception:
        pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_name_company ON agents(name, company_id)")
    except Exception:
        pass


def _run_migrations(conn: sqlite3.Connection):
    """对已有表执行增量迁移（幂等，每次 get_conn 都调用）。"""
    # 补 gender 列（v2.2.5）
    try:
        agent_cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)")}
        if "gender" not in agent_cols:
            conn.execute("ALTER TABLE agents ADD COLUMN gender TEXT DEFAULT ''")
            conn.commit()
    except Exception:
        pass

    # 补 UNIQUE 索引（防止 upsert ON CONFLICT 报错，#ON CONFLICT clause does not match）
    try:
        existing_indexes = {r[1] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_agents_name_company'"
        )}
        if "idx_agents_name_company" not in existing_indexes:
            conn.execute("CREATE UNIQUE INDEX idx_agents_name_company ON agents(name, company_id)")
            conn.commit()
    except Exception:
        pass


def init_db(workspace_id: str):
    """建表（幂等）。"""
    with get_conn(workspace_id) as conn:
        pass  # get_conn 已自动初始化
