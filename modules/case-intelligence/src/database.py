# =============================================
# case-intelligence 数据库层
# SQLite: data/case_registry.db
# 包含: cases / artifacts / templates 三张表
# =============================================
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "case_registry.db"

# 提取维度（5个固定维度，适用于所有案由类型）
ARTIFACT_TYPES = ["D1", "D2", "D3", "D4", "D5"]
ARTIFACT_TYPE_NAMES = {
    "D1": "事实认定",
    "D2": "法律依据",
    "D3": "攻防策略",
    "D4": "证据体系",
    "D5": "赔偿裁量",
}

# 录入方式
ENTRY_METHODS = ["CLI", "UI", "AI"]

# 涉案场景
SCENE_TYPES = [
    "实体KTV",
    "车载KTV",
    "线上平台",
    "实体场所",
    "线上应用",
    "混合场景",
    "其他",
]

# 被告授权状态
AUTH_STATUS_TYPES = [
    "已获音集协+音著协双授权",
    "已获音集协授权",
    "已获音著协授权",
    "部分授权",
    "未获授权",
    "待核实",
]

# 原告授权层级
PLAINTIFF_AUTH_LEVELS = [
    "原始权利人",
    "独家被授权方",
    "间接授权(2级)",
    "间接授权(3级+)",
    "集体管理组织",
    "待核实",
]


def _get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """获取数据库连接（自动建表）。"""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """建表（幂等）。"""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS cases (
        id           TEXT PRIMARY KEY,
        case_number  TEXT UNIQUE,
        case_name    TEXT NOT NULL,
        plaintiff    TEXT,
        defendant    TEXT,
        cause        TEXT,
        result       TEXT,
        source_path  TEXT,
        status       TEXT DEFAULT 'pending',
        notes        TEXT,
        extracted_at TEXT,
        created_at   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS artifacts (
        id            TEXT PRIMARY KEY,
        case_id       TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        title         TEXT NOT NULL,
        content       TEXT,
        source_ref    TEXT,
        version       INTEGER DEFAULT 1,
        created_at    TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    );

    CREATE TABLE IF NOT EXISTS templates (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        category        TEXT,
        source_artifacts TEXT,
        content         TEXT,
        version         INTEGER DEFAULT 1,
        source_case_ids  TEXT,
        usage_count     INTEGER DEFAULT 0,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_artifacts_case_id ON artifacts(case_id);
    CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category);
    """)


# =============================================
# Cases 表操作
# =============================================

def create_case(
    case_name: str,
    case_number: Optional[str] = None,
    plaintiff: str = "",
    defendant: str = "",
    cause: str = "",
    result: str = "",
    source_path: str = "",
    notes: str = "",
    entry_method: str = "CLI",
    scene: str = "",
    plaintiff_auth_level: str = "",
    defendant_auth_status: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """注册新案件，返回案件记录 dict（含 id）。"""
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    case_id = str(uuid.uuid4())
    try:
        conn.execute(
            """
            INSERT INTO cases
              (id, case_number, case_name, plaintiff, defendant, cause,
               result, source_path, status, notes, created_at,
               entry_method, scene, plaintiff_auth_level, defendant_auth_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (case_id, case_number, case_name, plaintiff, defendant, cause,
             result, source_path, notes, now,
             entry_method, scene, plaintiff_auth_level, defendant_auth_status),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise ValueError(f"案号冲突或数据错误: {e}")
    finally:
        conn.close()
    return get_case(case_id, db_path)


def get_case(case_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """按 ID 查询案件。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM cases WHERE id = ?", (case_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_case_by_number(
    case_number: str, db_path: Optional[Path] = None
) -> Optional[dict]:
    """按案号查询案件。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM cases WHERE case_number = ?", (case_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_cases(status: Optional[str] = None, db_path: Optional[Path] = None) -> list[dict]:
    """列出案件（可选 status 过滤）。"""
    conn = _get_conn(db_path)
    if status:
        rows = conn.execute(
            "SELECT * FROM cases WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_case_status(
    case_id: str, status: str, db_path: Optional[Path] = None
) -> None:
    """更新案件状态。"""
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE cases SET status = ?, extracted_at = ? WHERE id = ?",
        (status, now, case_id),
    )
    conn.commit()
    conn.close()


def search_cases(
    query: str, db_path: Optional[Path] = None
) -> list[dict]:
    """模糊搜索案件（案号/案名/原告/被告/案由）。"""
    conn = _get_conn(db_path)
    q = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM cases
        WHERE case_number LIKE ?
           OR case_name  LIKE ?
           OR plaintiff  LIKE ?
           OR defendant  LIKE ?
           OR cause      LIKE ?
        ORDER BY created_at DESC
        """,
        (q, q, q, q, q),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_artifacts_by_case(
    case_id: str, db_path: Optional[Path] = None
) -> int:
    """统计某案件下的提取物数量。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT COUNT(*) FROM artifacts WHERE case_id = ?", (case_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


# =============================================
# Artifacts 表操作
# =============================================

ARTIFACT_TYPES = [
    "defense_argument_chain",    # 抗辩论证链
    "cross_exam_strategy",       # 质证策略
    "evidence_structure",        # 证据结构
    "legal_reasoning_chain",     # 法律推理链
    "quantitative_analysis",     # 量化分析
    "liability_calculation",     # 责任计算
    "contingency_response",      # 应变话术
    "reverse_strategy",          # 反向维权路径
    "court_statement",           # 当庭陈述
    "case_key_facts",            # 关键事实清单
]

TEMPLATE_CATEGORIES = [
    "答辩状",
    "质证意见",
    "当庭陈述",
    "证据目录",
    "上诉状",
    "申请书",
    "其他",
]


def create_artifact(
    case_id: str,
    artifact_type: str,
    title: str,
    content: str = "",
    source_ref: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """创建提取物，返回 dict（含 id）。"""
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(
            f"无效 artifact_type: {artifact_type}，有效值: {ARTIFACT_TYPES}"
        )
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    artifact_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO artifacts
          (id, case_id, artifact_type, title, content, source_ref, version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (artifact_id, case_id, artifact_type, title, content, source_ref, now),
    )
    conn.commit()
    conn.close()
    return get_artifact(artifact_id, db_path)


def get_artifact(
    artifact_id: str, db_path: Optional[Path] = None
) -> Optional[dict]:
    """按 ID 查询提取物。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_artifacts_by_case(
    case_id: str, db_path: Optional[Path] = None
) -> list[dict]:
    """列出某案件下所有提取物。"""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM artifacts WHERE case_id = ? ORDER BY created_at ASC",
        (case_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all_artifacts(
    artifact_type: Optional[str] = None, db_path: Optional[Path] = None
) -> list[dict]:
    """列出所有提取物（可选按类型过滤）。"""
    conn = _get_conn(db_path)
    if artifact_type:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_type = ? ORDER BY created_at DESC",
            (artifact_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM artifacts ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_artifact(
    artifact_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    source_ref: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """更新提取物内容（version +1）。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT version FROM artifacts WHERE id = ?", (artifact_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"提取物不存在: {artifact_id}")
    new_version = row[0] + 1
    updates, params = [], []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if source_ref is not None:
        updates.append("source_ref = ?")
        params.append(source_ref)
    updates.append("version = ?")
    params.append(new_version)
    params.append(artifact_id)
    conn.execute(
        f"UPDATE artifacts SET {', '.join(updates)} WHERE id = ?", params
    )
    conn.commit()
    conn.close()
    return get_artifact(artifact_id, db_path)


def delete_artifact(artifact_id: str, db_path: Optional[Path] = None) -> None:
    """删除提取物。"""
    conn = _get_conn(db_path)
    conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    conn.commit()
    conn.close()


# =============================================
# Templates 表操作
# =============================================

def create_template(
    name: str,
    content: str = "",
    category: str = "其他",
    source_artifacts: list[str] | None = None,
    source_case_ids: list[str] | None = None,
    db_path: Optional[Path] = None,
) -> dict:
    """创建模板，返回 dict（含 id）。"""
    if category not in TEMPLATE_CATEGORIES:
        raise ValueError(
            f"无效 category: {category}，有效值: {TEMPLATE_CATEGORIES}"
        )
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    import json
    template_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO templates
          (id, name, category, source_artifacts, content, version,
           source_case_ids, usage_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, 0, ?, ?)
        """,
        (
            template_id,
            name,
            category,
            json.dumps(source_artifacts or [], ensure_ascii=False),
            content,
            json.dumps(source_case_ids or [], ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_template(template_id, db_path)


def get_template(
    template_id: str, db_path: Optional[Path] = None
) -> Optional[dict]:
    """按 ID 查询模板。"""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM templates WHERE id = ?", (template_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_templates(
    category: Optional[str] = None, db_path: Optional[Path] = None
) -> list[dict]:
    """列出模板（可选按分类过滤）。"""
    conn = _get_conn(db_path)
    if category:
        rows = conn.execute(
            "SELECT * FROM templates WHERE category = ? ORDER BY usage_count DESC, created_at DESC",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM templates ORDER BY usage_count DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def increment_usage(
    template_id: str, db_path: Optional[Path] = None
) -> None:
    """模板被引用时 usage_count +1。"""
    conn = _get_conn(db_path)
    conn.execute(
        "UPDATE templates SET usage_count = usage_count + 1 WHERE id = ?",
        (template_id,),
    )
    conn.commit()
    conn.close()


def delete_template(
    template_id: str, db_path: Optional[Path] = None
) -> None:
    """删除模板。"""
    conn = _get_conn(db_path)
    conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


# =============================================
# 统计报告
# =============================================

def get_summary(db_path: Optional[Path] = None) -> dict:
    """获取全局统计摘要。"""
    conn = _get_conn(db_path)
    total_cases = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    extracted_cases = conn.execute(
        "SELECT COUNT(*) FROM cases WHERE status = 'extracted'"
    ).fetchone()[0]
    pending_cases = conn.execute(
        "SELECT COUNT(*) FROM cases WHERE status = 'pending'"
    ).fetchone()[0]
    total_artifacts = conn.execute(
        "SELECT COUNT(*) FROM artifacts"
    ).fetchone()[0]
    total_templates = conn.execute(
        "SELECT COUNT(*) FROM templates"
    ).fetchone()[0]
    conn.close()
    return {
        "total_cases": total_cases,
        "extracted_cases": extracted_cases,
        "pending_cases": pending_cases,
        "total_artifacts": total_artifacts,
        "total_templates": total_templates,
    }
