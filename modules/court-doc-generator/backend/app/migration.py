"""单租户初始化脚本：创建 shared workspace 注册表 + 业务库 schema（幂等）。"""
import hashlib
import os
import sqlite3
from pathlib import Path

SHARED_WS_ID = "shared"
SHARED_WS_NAME = "共享工作空间"


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"{salt.hex()}${dk.hex()}"


def run_migration(data_dir: Path) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)
    ws_db = data_dir / "workspaces.db"

    # 1. workspaces 注册表
    conn = sqlite3.connect(str(ws_db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    existing = conn.execute("SELECT id FROM workspaces WHERE id = ?", (SHARED_WS_ID,)).fetchone()
    if not existing:
        conn.execute("INSERT INTO workspaces (id, name, password_hash) VALUES (?, ?, ?)",
                     (SHARED_WS_ID, SHARED_WS_NAME, _hash_password("changeme")))
        conn.commit()
        print(f"[migration] created shared workspace: {SHARED_WS_ID}")
    else:
        print(f"[migration] shared workspace already exists: {SHARED_WS_ID}")
    conn.close()

    # 2. 初始化 shared workspace 业务库 schema
    shared_ws_dir = data_dir / "workspaces" / SHARED_WS_ID
    shared_ws_dir.mkdir(parents=True, exist_ok=True)
    shared_db = shared_ws_dir / "court_matters.db"

    conn = sqlite3.connect(str(shared_db))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
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
    """)

    for idx_sql in [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_name_company ON agents(name, company_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number)",
    ]:
        try:
            conn.execute(idx_sql)
        except Exception:
            pass

    conn.commit()
    conn.close()

    return {
        "shared_ws_id": SHARED_WS_ID,
        "note": "schema initialized",
    }
