"""SQLite 数据库层：管理公司、代理人、案件、历史记录。"""
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Tuple

from config import DB_PATH


SCHEMA_SQL = """
-- 公司/法人信息表
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                 -- 公司全称
    credit_code TEXT,                          -- 统一社会信用代码
    legal_rep_name TEXT NOT NULL,              -- 法定代表人姓名
    legal_rep_position TEXT,                   -- 法人职务
    legal_rep_id_card TEXT,                    -- 法人身份证号
    address TEXT,                              -- 公司地址
    phone TEXT,                                -- 公司电话
    is_default INTEGER DEFAULT 0,              -- 是否默认公司
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 代理人信息表
-- UNIQUE (name, company_id)：同一公司下代理人姓名不重复
-- 修复记录：旧版本用 (name, id_card) 唯一，会导致未填身份证的多名同姓名代理人被合并为同一记录
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                        -- 代理人姓名
    gender TEXT,                               -- 性别
    id_card TEXT,                              -- 身份证号
    position TEXT,                             -- 职务
    phone TEXT,                                -- 电话
    company_id INTEGER,                        -- 所属公司
    is_default INTEGER DEFAULT 0,              -- 是否默认
    contract_pdf_path TEXT,                    -- 🆕 F-031 劳动合同 PDF 路径（相对 PROJECT_ROOT）
    id_card_pdf_path TEXT,                     -- 🆕 F-031 身份证 PDF 路径（相对 PROJECT_ROOT）
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE (name, company_id)
);

-- 案件信息表
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT NOT NULL,                 -- 案号
    case_cause TEXT NOT NULL,                  -- 案由（如"合同纠纷"）
    court TEXT NOT NULL,                       -- 审理法院
    hearing_date TEXT,                         -- 开庭日期
    opposing_party TEXT,                       -- 对方当事人
    our_role TEXT NOT NULL,                    -- 我方身份：原告/被告/第三人
    authority_type TEXT DEFAULT '特别授权',    -- 代理权限
    company_id INTEGER,                        -- 委托单位
    agent_id INTEGER,                          -- 代理人
    notes TEXT,                                -- 备注
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 生成历史表
CREATE TABLE IF NOT EXISTS generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    case_number TEXT,
    output_dir TEXT,                           -- 输出目录
    file_count INTEGER,                        -- 文件数量
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);
"""


@contextmanager
def get_conn():
    """获取数据库连接（上下文管理器）。"""
    conn = sqlite3.connect(str(DB_PATH))
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


def migrate_add_agent_pdf_paths(conn):
    """F-031 幂等迁移：给 agents 表新增 contract_pdf_path / id_card_pdf_path 字段。

    旧数据库升级时执行（已有数据保留，仅新增字段）。
    重复执行安全（sqlite3.OperationalError 捕获）。
    """
    for col in ("contract_pdf_path", "id_card_pdf_path"):
        try:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在，幂等


def init_db():
    """初始化数据库（建表 + F-031 迁移）。"""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        migrate_add_agent_pdf_paths(conn)


# ============================================================
# 公司 CRUD
# ============================================================

def list_companies() -> list:
    """列出所有公司。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM companies ORDER BY is_default DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_default_company() -> dict | None:
    """获取默认公司。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE is_default = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_company(company_id: int) -> dict | None:
    """按 id 获取公司（v1.1.0 测试需要，补全）。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        return dict(row) if row else None


def upsert_company(data: dict) -> int:
    """插入或更新公司信息。"""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM companies WHERE name = ?", (data["name"],)
        ).fetchone()
        now = datetime.now().isoformat(timespec="seconds")
        if existing:
            conn.execute(
                """UPDATE companies
                SET credit_code=?, legal_rep_name=?, legal_rep_position=?,
                    legal_rep_id_card=?, address=?, phone=?,
                    updated_at=?
                WHERE id=?""",
                (
                    data.get("credit_code"),
                    data.get("legal_rep_name"),
                    data.get("legal_rep_position"),
                    data.get("legal_rep_id_card"),
                    data.get("address"),
                    data.get("phone"),
                    now,
                    existing["id"],
                ),
            )
            return existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO companies
                (name, credit_code, legal_rep_name, legal_rep_position,
                 legal_rep_id_card, address, phone, is_default, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    data["name"],
                    data.get("credit_code"),
                    data.get("legal_rep_name"),
                    data.get("legal_rep_position"),
                    data.get("legal_rep_id_card"),
                    data.get("address"),
                    data.get("phone"),
                    now,
                    now,
                ),
            )
            return cur.lastrowid


def set_default_company(company_id: int):
    """设置默认公司。"""
    with get_conn() as conn:
        conn.execute("UPDATE companies SET is_default = 0")
        conn.execute("UPDATE companies SET is_default = 1 WHERE id = ?", (company_id,))


# ============================================================
# 代理人 CRUD
# ============================================================

def list_agents() -> list:
    """列出所有代理人。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, c.name AS company_name
            FROM agents a LEFT JOIN companies c ON a.company_id = c.id
            ORDER BY a.is_default DESC, a.name"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_default_agent() -> dict | None:
    """获取默认代理人。"""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.*, c.name AS company_name
            FROM agents a LEFT JOIN companies c ON a.company_id = c.id
            WHERE a.is_default = 1 LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None


def upsert_agent(data: dict) -> int:
    """插入或更新代理人（以 name+company_id 判重）。

    修复：旧版本以 (name, id_card) 判重，当 id_card 为空字符串时，
    同一公司下未填身份证的多名同姓名代理人会被错误地判定为同一人。
    现改为 (name, company_id)，符合业务语义。
    """
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM agents WHERE name = ? AND company_id IS ?",
            (data["name"], data.get("company_id")),
        ).fetchone()
        now = datetime.now().isoformat(timespec="seconds")
        if existing:
            conn.execute(
                """UPDATE agents
                SET gender=?, id_card=?, position=?, phone=?,
                    contract_pdf_path=?, id_card_pdf_path=?,
                    updated_at=?
                WHERE id=?""",
                (
                    data.get("gender"),
                    data.get("id_card"),
                    data.get("position"),
                    data.get("phone"),
                    data.get("contract_pdf_path"),
                    data.get("id_card_pdf_path"),
                    now,
                    existing["id"],
                ),
            )
            return existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO agents
                (name, gender, id_card, position, phone, company_id,
                 is_default, contract_pdf_path, id_card_pdf_path,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                (
                    data["name"],
                    data.get("gender"),
                    data.get("id_card"),
                    data.get("position"),
                    data.get("phone"),
                    data.get("company_id"),
                    data.get("contract_pdf_path"),
                    data.get("id_card_pdf_path"),
                    now,
                    now,
                ),
            )
            return cur.lastrowid


def set_default_agent(agent_id: int):
    """设置默认代理人。"""
    with get_conn() as conn:
        conn.execute("UPDATE agents SET is_default = 0")
        conn.execute("UPDATE agents SET is_default = 1 WHERE id = ?", (agent_id,))


def delete_agent(agent_id: int) -> Tuple[bool, str, list]:
    """F-039 删除代理人（DB 记录 + 返回待清理文件路径列表）。

    参数：
        agent_id: 代理人 ID

    返回：
        (success: bool, message: str, file_paths_to_delete: list[str])
        - success=True, message="已删除", file_paths_to_delete=["static/agents/3/contract_xxx.pdf", ...]
        - success=False, message="该代理人关联 N 个案件...", file_paths_to_delete=[]
        - success=False, message="代理人 N 不存在", file_paths_to_delete=[]

    设计：
        - 数据库函数只管 DB（职责单一）
        - 文件删除由调用方（app.py）负责，避免 DB 函数依赖 path 路径
        - 检查 cases.agent_id 关联：有关联不删（保留历史案件可追溯性）
    """
    with get_conn() as conn:
        # 1. 检查关联案件数
        related_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM cases WHERE agent_id = ?", (agent_id,)
        ).fetchone()["cnt"]

        if related_count > 0:
            return False, f"该代理人关联 {related_count} 个案件，请先解除关联", []

        # 2. 读取旧路径（用于返回给调用方删文件）
        row = conn.execute(
            "SELECT contract_pdf_path, id_card_pdf_path FROM agents WHERE id = ?",
            (agent_id,),
        ).fetchone()
        if not row:
            return False, f"代理人 {agent_id} 不存在", []

        paths = [p for p in (row["contract_pdf_path"], row["id_card_pdf_path"]) if p]

        # 3. 删记录
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    return True, "已删除", paths


# ============================================================
# 案件 CRUD
# ============================================================

def create_case(data: dict) -> int:
    """创建案件记录。"""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO cases
            (case_number, case_cause, court, hearing_date, opposing_party,
             our_role, authority_type, company_id, agent_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["case_number"],
                data["case_cause"],
                data["court"],
                data.get("hearing_date"),
                data.get("opposing_party"),
                data["our_role"],
                data.get("authority_type", "特别授权"),
                data.get("company_id"),
                data.get("agent_id"),
                data.get("notes"),
            ),
        )
        return cur.lastrowid


def list_cases(limit: int = 50) -> list:
    """列出最近案件。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*, co.name AS company_name, a.name AS agent_name
            FROM cases c
            LEFT JOIN companies co ON c.company_id = co.id
            LEFT JOIN agents a ON c.agent_id = a.id
            ORDER BY c.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_case(case_id: int) -> dict | None:
    """获取单个案件。"""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT c.*, co.name AS company_name, co.legal_rep_name,
                       co.legal_rep_position, co.address AS company_address,
                       co.phone AS company_phone, co.credit_code,
                       a.name AS agent_name, a.gender AS agent_gender,
                       a.id_card AS agent_id_card, a.position AS agent_position,
                       a.phone AS agent_phone
            FROM cases c
            LEFT JOIN companies co ON c.company_id = co.id
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.id = ?""",
            (case_id,),
        ).fetchone()
        return dict(row) if row else None


def search_cases(keyword: str) -> list:
    """按案号/案由/对方当事人搜索。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*, co.name AS company_name, a.name AS agent_name
            FROM cases c
            LEFT JOIN companies co ON c.company_id = co.id
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.case_number LIKE ? OR c.case_cause LIKE ?
                  OR c.opposing_party LIKE ?
            ORDER BY c.created_at DESC""",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# 生成历史
# ============================================================

def add_history(case_id: int, case_number: str, output_dir: str, file_count: int):
    """添加生成历史。"""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO generation_history
            (case_id, case_number, output_dir, file_count)
            VALUES (?, ?, ?, ?)""",
            (case_id, case_number, output_dir, file_count),
        )


def list_history(limit: int = 20) -> list:
    """列出最近的生成历史。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT h.*, c.case_cause, c.court
            FROM generation_history h
            LEFT JOIN cases c ON h.case_id = c.id
            ORDER BY h.generated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
