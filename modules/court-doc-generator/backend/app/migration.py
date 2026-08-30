"""单租户迁移脚本：将多 workspace 数据合并到 shared workspace。"""
import hashlib
import os
import shutil
import sqlite3
from pathlib import Path

SHARED_WS_ID = "shared"
SHARED_WS_NAME = "共享工作空间"


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"{salt.hex()}${dk.hex()}"


def _copy_file(src_path: str, dst_dir: Path, filename: str, data_dir: Path) -> str | None:
    """根据数据库中存储的路径格式复制文件，返回新路径或 None。

    数据库存储的路径格式为 data/workspaces/<ws_id>/agents/<id>/<file>，
    volume 根为 /app/data。实际文件在：
    /app/data/workspaces/<ws_id>/agents/<id>/<file>
    """
    if not src_path:
        return None
    src = Path(src_path)

    candidates = []

    # 格式1: data/workspaces/<ws>/agents/<id>/<file>
    #         → 去掉 data/ 前缀: workspaces/<ws>/agents/<id>/<file>
    #         → /app/data/workspaces/<ws>/agents/<id>/<file>
    if src.parts[0] == "data" and "workspaces" in src.parts:
        candidates.append(Path(*src.parts[1:]))

    # 格式2: data/workspaces/<ws>/agents/<id>/<file> 但文件实际在 data/<ws>/agents/<id>/
    #         → data/<ws>/agents/<id>/<file>
    if src.parts[0] == "data" and "workspaces" in src.parts:
        idx = src.parts.index("workspaces")
        if idx >= 1:
            ws_part = src.parts[idx + 1] if idx + 1 < len(src.parts) else None
            if ws_part and "agents" in src.parts:
                agents_idx = src.parts.index("agents")
                rest = "/".join(src.parts[agents_idx:])
                candidates.append(Path("data") / ws_part / rest)

    # 格式3: agents/<id>/<file> → 直接使用
    if src.parts[0] == "agents":
        candidates.append(src)

    # 格式4: 直接使用原始路径
    candidates.append(Path(src_path))

    for cand in candidates:
        abs_path = data_dir / cand if not cand.is_absolute() else cand
        print(f"    [_copy_file] trying: {abs_path} (exists={abs_path.exists()})")
        if abs_path.exists():
            dst = dst_dir / filename
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(abs_path, dst)
            return str(dst)

    return None


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

    # 2. 初始化 shared workspace 业务库（使用 database.py 的 schema，保持与 API 一致）
    shared_ws_dir = data_dir / "workspaces" / SHARED_WS_ID
    shared_ws_dir.mkdir(parents=True, exist_ok=True)
    shared_db = shared_ws_dir / "court_matters.db"

    conn = sqlite3.connect(str(shared_db))
    conn.row_factory = sqlite3.Row

    # 使用与 database.py 相同的 schema（CREATE TABLE IF NOT EXISTS 是幂等的）
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
    # 补建索引
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")
    except: pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_name_company ON agents(name, company_id)")
    except: pass

    conn.commit()

    # 幂等保护：完全迁移过则跳过
    existing_agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    cases_existing = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    print(f"[migration] shared db: {existing_agent_count} agents, {cases_existing} cases")

    if existing_agent_count > 0 and cases_existing > 0:
        conn.close()
        return {
            "shared_ws_id": SHARED_WS_ID,
            "agents_migrated": 0,
            "agents_skipped": 0,
            "cases_migrated": 0,
            "cases_skipped": cases_existing,
            "note": "fully migrated, skipping",
        }

    leishi_name = "北京雷石天地电子技术股份有限公司"
    existing_leishi = conn.execute("SELECT id FROM companies WHERE name = ?", (leishi_name,)).fetchone()
    if not existing_leishi:
        conn.execute("""
            INSERT INTO companies
              (name, credit_code, legal_rep_name, legal_rep_position, address, phone,
               is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            leishi_name, "91110108MA01234X7Y",
            "马杰", "总经理",
            "北京市朝阳区望京东园四区1号楼29层2901号10",
            "010-84488000",
            1
        ))
        conn.commit()
        print(f"[migration] inserted company: {leishi_name}")

    leishi = conn.execute("SELECT id FROM companies WHERE name = ?", (leishi_name,)).fetchone()
    leishi_id = leishi[0] if leishi else None

    # 3. 合并 agents（含文件）
    agents_migrated = 0
    agents_skipped = 0
    existing_agents = {r[0] for r in conn.execute("SELECT name FROM agents").fetchall()}
    migrated_agent_ids = {}  # old_key -> new_id

    seen_dbs = set()
    search_dirs = list(data_dir.iterdir())
    if (data_dir / "workspaces").exists():
        search_dirs += list((data_dir / "workspaces").iterdir())

    for ws_dir in search_dirs:
        if not ws_dir.is_dir():
            continue
        if ws_dir.name in ("workspaces", SHARED_WS_ID, "shared"):
            continue
        ws_id = ws_dir.name

        for db_name in ("court.db", "court_matters.db"):
            db_path = ws_dir / db_name
            if not db_path.exists() or str(db_path) in seen_dbs:
                continue
            seen_dbs.add(str(db_path))
            print(f"[migration] reading {db_path}")

            try:
                src = sqlite3.connect(str(db_path))
                src.row_factory = sqlite3.Row
                tables = {r[0] for r in src.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")}
                if "agents" not in tables:
                    src.close()
                    continue
                agents = src.execute("SELECT * FROM agents ORDER BY id").fetchall()
                src.close()

                for agent in agents:
                    a = dict(agent)
                    name = a.get("name", "")
                    if name in existing_agents:
                        # 记录旧ID→新ID映射（用于案件关联）
                        old_id = a.get("id")
                        # 尝试找到新ID
                        new_row = conn.execute(
                            "SELECT id FROM agents WHERE name = ? AND company_id = ?",
                            (name, leishi_id)).fetchone()
                        if new_row and old_id:
                            migrated_agent_ids[f"{ws_id}:{old_id}"] = new_row[0]
                        agents_skipped += 1
                        continue

                    # 复制文件（使用正确的路径解析）
                    print(f"  [_copy_file for {name}] src_id_card={a.get('id_card_pdf_path')}")
                    new_id_card = _copy_file(
                        a.get("id_card_pdf_path"), shared_ws_dir / "agents", "id_card.pdf", data_dir)
                    print(f"  [_copy_file for {name}] src_contract={a.get('contract_pdf_path')}")
                    new_contract = _copy_file(
                        a.get("contract_pdf_path"), shared_ws_dir / "agents", "labor_contract.pdf", data_dir)
                    print(f"  [_copy_file result] id_card={new_id_card}, contract={new_contract}")

                    cursor = conn.execute("""
                        INSERT INTO agents
                          (name, position, phone, id_card, gender, company_id,
                           is_default, id_card_pdf_path, contract_pdf_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name or "",
                        a.get("position") or "",
                        a.get("phone") or "",
                        a.get("id_card") or "",
                        a.get("gender") or "",
                        leishi_id,
                        a.get("is_default") or 0,
                        new_id_card or "",
                        new_contract or "",
                    ))
                    old_id = a.get("id")
                    new_id = cursor.lastrowid
                    if old_id:
                        migrated_agent_ids[f"{ws_id}:{old_id}"] = new_id
                    existing_agents.add(name)
                    agents_migrated += 1
                    print(f"  [migrated agent] {name} -> id={new_id}")
            except Exception as e:
                print(f"[migration] error reading agents from {db_path}: {e}")

    conn.commit()

    # 4. 合并 cases
    cases_migrated = 0
    cases_skipped = 0

    seen_dbs2 = set()
    for ws_dir in search_dirs:
        if not ws_dir.is_dir():
            continue
        if ws_dir.name in ("workspaces", SHARED_WS_ID, "shared"):
            continue
        ws_id = ws_dir.name

        for db_name in ("court.db", "court_matters.db"):
            db_path = ws_dir / db_name
            if not db_path.exists() or str(db_path) in seen_dbs2:
                continue
            seen_dbs2.add(str(db_path))

            try:
                src = sqlite3.connect(str(db_path))
                src.row_factory = sqlite3.Row
                tables = {r[0] for r in src.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'")}
                if "cases" not in tables:
                    src.close()
                    continue
                cases_rows = src.execute("SELECT * FROM cases ORDER BY id").fetchall()
                src.close()

                for case_row in cases_rows:
                    c = dict(case_row)
                    case_num = c.get("case_number")
                    if not case_num:
                        cases_skipped += 1
                        continue

                    # 映射旧 agent_id → 新 agent_id
                    old_agent_id = c.get("agent_id")
                    new_agent_id = None
                    if old_agent_id:
                        key = f"{ws_id}:{old_agent_id}"
                        new_agent_id = migrated_agent_ids.get(key)

                    # 兼容新旧字段名
                    opposite = c.get("opposite_party") or c.get("opposing_party") or ""
                    filing_date = c.get("filing_date") or c.get("hearing_date") or ""

                    try:
                        conn.execute("""
                            INSERT INTO cases
                              (case_number, court, cause, hearing_date, opposing_party,
                               agent_id, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            case_num,
                            c.get("court") or "",
                            c.get("cause") or "",
                            filing_date,
                            opposite,
                            new_agent_id,
                            c.get("status") or "pending",
                        ))
                        cases_migrated += 1
                    except Exception as e:
                        if "UNIQUE" in str(e):
                            cases_skipped += 1
                        else:
                            print(f"[migration] error inserting case {case_num}: {e}")
            except Exception as e:
                print(f"[migration] error reading cases from {db_path}: {e}")

    conn.commit()
    conn.close()

    return {
        "shared_ws_id": SHARED_WS_ID,
        "agents_migrated": agents_migrated,
        "agents_skipped": agents_skipped,
        "cases_migrated": cases_migrated,
        "cases_skipped": cases_skipped,
    }
