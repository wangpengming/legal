# =============================================
# case-intelligence 数据库层
# SQLite: data/case_registry.db
# 包含: cases / artifacts / templates 三张表
# =============================================
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# DATA_DIR 可被环境变量覆盖：部署时指向卷挂载点（/data），本地默认 PROJECT_ROOT/data
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
DB_PATH = DATA_DIR / "case_registry.db"

# 提取维度（5 个固定维度，适用于所有案由类型）
DIMENSIONS = ["D1", "D2", "D3", "D4", "D5"]

# 维度 → artifact_type（唯一真值映射：importer / CLI / UI 共用，禁止各处再写死）
DIMENSION_ARTIFACT_TYPES = {
    "D1": "case_key_facts",          # 事实认定
    "D2": "legal_reasoning_chain",   # 法律依据
    "D3": "defense_argument_chain",  # 攻防策略
    "D4": "evidence_structure",      # 证据体系
    "D5": "liability_calculation",   # 赔偿裁量
}

# 提取物类型（唯一真值：语义名；后 5 个为 v3.2 遗留的文件层类型）
ARTIFACT_TYPES = [
    "case_key_facts",
    "legal_reasoning_chain",
    "defense_argument_chain",
    "evidence_structure",
    "liability_calculation",
    "quantitative_analysis",
    "cross_exam_strategy",
    "contingency_response",
    "reverse_strategy",
    "court_statement",
]

ARTIFACT_TYPE_NAMES = {
    "case_key_facts": "事实认定",
    "legal_reasoning_chain": "法律依据",
    "defense_argument_chain": "攻防策略",
    "evidence_structure": "证据体系",
    "liability_calculation": "赔偿裁量",
    "quantitative_analysis": "量化分析",
    "cross_exam_strategy": "质证策略",
    "contingency_response": "应变话术",
    "reverse_strategy": "反向维权路径",
    "court_statement": "当庭陈述",
}

# 录入方式（Bot = 飞书入口，见 docs/SPEC-feishu-bot.md）
ENTRY_METHODS = ["CLI", "UI", "AI", "Bot"]

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
    """获取数据库连接（自动建表）。

    三端（CLI / Streamlit UI / 飞书 Bot）同写一个库：WAL 让读写库级并行，
    busy_timeout 让写者等锁而非立刻抛 `database is locked`。
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    _init_schema(conn)
    return conn


# 进程内写串行化：三端同库时，跨进程由 SQLite 锁 + busy_timeout 兜底，
# 进程内多线程（WS 后台线程 / Streamlit）由这把可重入锁保证不互相争锁。
_WRITE_LOCK = threading.RLock()


@contextmanager
def _write(db_path: Optional[Path] = None):
    """写事务上下文：进程内互斥 + 跨进程等锁。

    用 `BEGIN IMMEDIATE` 立刻取写锁，避免「先读后写」升级锁时撞 SQLITE_BUSY
    （典型：update_artifact 先读 version 再自增）。
    """
    with _WRITE_LOCK:
        conn = _get_conn(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _ensure_columns(
    conn: sqlite3.Connection, table: str, columns: dict[str, str]
) -> None:
    """对已存在的老表补齐缺失列（CREATE TABLE IF NOT EXISTS 不会改老表）。"""
    have = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, ddl in columns.items():
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _init_schema(conn: sqlite3.Connection) -> None:
    """建表（幂等）+ 对旧库补齐缺失列（幂等迁移）。

    注：新库/容器首启必须能直接 INSERT 全部字段，故 CASES/ARTIFACTS 列
    必须与 create_case / create_artifact 的 SQL 完全一致；老库由
    _ensure_columns 兜底补列（历史事故：_init_schema 与代码脱节，
    fresh DB 一建就 OperationalError）。
    """
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS cases (
        id                     TEXT PRIMARY KEY,
        case_number            TEXT UNIQUE,
        case_name              TEXT NOT NULL,
        plaintiff              TEXT,
        defendant              TEXT,
        cause                  TEXT,
        court                  TEXT,
        year                   INTEGER,
        result                 TEXT,
        source_path            TEXT,
        source_files           TEXT,
        status                 TEXT DEFAULT 'pending',
        notes                  TEXT,
        entry_method           TEXT,
        scene                  TEXT,
        plaintiff_auth_level   TEXT,
        defendant_auth_status  TEXT,
        quality                TEXT,
        extracted_at           TEXT,
        created_at             TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS artifacts (
        id                TEXT PRIMARY KEY,
        case_id           TEXT NOT NULL,
        artifact_type     TEXT NOT NULL,
        title             TEXT NOT NULL,
        content           TEXT,
        source_ref        TEXT,
        version           INTEGER DEFAULT 1,
        parent_id         TEXT,
        generation_method TEXT,
        model_version     TEXT,
        created_at        TEXT NOT NULL,
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

    CREATE TABLE IF NOT EXISTS bot_audit (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ts         TEXT NOT NULL,
        open_id    TEXT,
        role       TEXT,
        action     TEXT NOT NULL,
        case_id    TEXT,
        result     TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_artifacts_case_id ON artifacts(case_id);
    CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category);
    CREATE INDEX IF NOT EXISTS idx_bot_audit_ts ON bot_audit(ts);
    """)
    _ensure_columns(conn, "cases", {
        # 基础列（历史最小库兜底）
        "case_number": "TEXT",
        "case_name": "TEXT",
        "plaintiff": "TEXT",
        "defendant": "TEXT",
        "cause": "TEXT",
        "result": "TEXT",
        "source_path": "TEXT",
        "status": "TEXT",
        "notes": "TEXT",
        "extracted_at": "TEXT",
        # v3.3+ 新增列
        "court": "TEXT",
        "year": "INTEGER",
        "source_files": "TEXT",
        "entry_method": "TEXT",
        "scene": "TEXT",
        "plaintiff_auth_level": "TEXT",
        "defendant_auth_status": "TEXT",
        "quality": "TEXT",
    })
    _ensure_columns(conn, "artifacts", {
        "case_id": "TEXT",
        "artifact_type": "TEXT",
        "title": "TEXT",
        "content": "TEXT",
        "source_ref": "TEXT",
        "version": "INTEGER",
        "parent_id": "TEXT",
        "generation_method": "TEXT",
        "model_version": "TEXT",
    })


# =============================================
# Cases 表操作
# =============================================

def create_case(
    case_name: str,
    case_number: Optional[str] = None,
    plaintiff: str = "",
    defendant: str = "",
    cause: str = "",
    court: str = "",
    year: Optional[int] = None,
    result: str = "",
    source_path: str = "",
    source_files: str = "",
    notes: str = "",
    entry_method: str = "CLI",
    scene: str = "",
    plaintiff_auth_level: str = "",
    defendant_auth_status: str = "",
    quality: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """注册新案件，返回案件记录 dict（含 id）。"""
    now = datetime.now(timezone.utc).isoformat()
    case_id = str(uuid.uuid4())
    try:
        with _write(db_path) as conn:
            conn.execute(
                """
                INSERT INTO cases
                  (id, case_number, case_name, plaintiff, defendant, cause, court,
                   year, result, source_path, source_files, status, notes, created_at,
                   entry_method, scene, plaintiff_auth_level, defendant_auth_status, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, case_number, case_name, plaintiff, defendant, cause, court,
                 year, result, source_path, source_files, notes, now,
                 entry_method, scene, plaintiff_auth_level, defendant_auth_status, quality),
            )
    except sqlite3.IntegrityError as e:
        raise ValueError(f"案号冲突或数据错误: {e}")
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


def list_cases(
    status: Optional[str] = None,
    db_path: Optional[Path] = None,
    year: Optional[int] = None,
    quality: Optional[str] = None,
    cause: Optional[str] = None,
) -> list[dict]:
    """列出案件（可选 status / year / quality / cause 精确过滤）。"""
    conn = _get_conn(db_path)
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if year:
        clauses.append("year = ?")
        params.append(year)
    if quality:
        clauses.append("quality = ?")
        params.append(quality)
    if cause:
        clauses.append("cause = ?")
        params.append(cause)
    sql = "SELECT * FROM cases"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_case_status(
    case_id: str, status: str, db_path: Optional[Path] = None
) -> None:
    """更新案件状态。"""
    now = datetime.now(timezone.utc).isoformat()
    with _write(db_path) as conn:
        conn.execute(
            "UPDATE cases SET status = ?, extracted_at = ? WHERE id = ?",
            (status, now, case_id),
        )


# update_case 白名单（防止任意列注入）
CASE_UPDATABLE_FIELDS = (
    "case_number", "case_name", "plaintiff", "defendant", "cause", "court",
    "year", "result", "source_path", "source_files", "status", "notes",
    "entry_method", "scene", "plaintiff_auth_level", "defendant_auth_status",
    "quality",
)


def update_case(
    case_id: str, db_path: Optional[Path] = None, **fields
) -> Optional[dict]:
    """按白名单更新案件字段，返回更新后的记录（无有效字段则原样返回）。"""
    updates = {k: v for k, v in fields.items() if k in CASE_UPDATABLE_FIELDS}
    if not updates:
        return get_case(case_id, db_path)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [case_id]
    try:
        with _write(db_path) as conn:
            conn.execute(f"UPDATE cases SET {assignments} WHERE id = ?", params)
    except sqlite3.IntegrityError as e:
        raise ValueError(f"案号冲突或数据错误: {e}")
    return get_case(case_id, db_path)


def delete_case(case_id: str, db_path: Optional[Path] = None) -> None:
    """删除案件及其全部提取物记录（级联）；文件层由调用方清理。"""
    with _write(db_path) as conn:
        conn.execute("DELETE FROM artifacts WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))


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
    parent_id: str = None,
    generation_method: str = None,
    model_version: str = None,
) -> dict:
    """创建提取物，返回 dict（含 id）。
    
    Args:
        parent_id: 上一个版本的 artifact_id（用于版本链）
        generation_method: 生成方式（'llm' / 'template+llm' / 'manual'）
        model_version: 模型版本（如 'MiniMax-Text-01'）
    """
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(
            f"无效 artifact_type: {artifact_type}，有效值: {ARTIFACT_TYPES}"
        )
    now = datetime.now(timezone.utc).isoformat()
    artifact_id = str(uuid.uuid4())

    with _write(db_path) as conn:
        # 版本号在写事务内计算，避免并发下读旧值
        version = 1
        if parent_id:
            parent = conn.execute(
                "SELECT version FROM artifacts WHERE id = ?", (parent_id,)
            ).fetchone()
            if parent:
                version = parent[0] + 1
        conn.execute(
            """
            INSERT INTO artifacts
              (id, case_id, artifact_type, title, content, source_ref, version, created_at, parent_id, generation_method, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, case_id, artifact_type, title, content, source_ref, version, now, parent_id, generation_method, model_version),
        )
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
    with _write(db_path) as conn:
        row = conn.execute(
            "SELECT version FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        if not row:
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
    return get_artifact(artifact_id, db_path)


def delete_artifact(artifact_id: str, db_path: Optional[Path] = None) -> None:
    """删除提取物。"""
    with _write(db_path) as conn:
        conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))


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
    now = datetime.now(timezone.utc).isoformat()
    import json
    template_id = str(uuid.uuid4())
    with _write(db_path) as conn:
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
    with _write(db_path) as conn:
        conn.execute(
            "UPDATE templates SET usage_count = usage_count + 1 WHERE id = ?",
            (template_id,),
        )


# update_template 白名单
TEMPLATE_UPDATABLE_FIELDS = ("name", "category", "content")


def update_template(
    template_id: str, db_path: Optional[Path] = None, **fields
) -> Optional[dict]:
    """按白名单更新模板（None 值忽略），返回更新后的记录。"""
    updates = {
        k: v for k, v in fields.items()
        if k in TEMPLATE_UPDATABLE_FIELDS and v is not None
    }
    if "category" in updates and updates["category"] not in TEMPLATE_CATEGORIES:
        raise ValueError(f"无效 category: {updates['category']}")
    if not updates:
        return get_template(template_id, db_path)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    with _write(db_path) as conn:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE templates SET {assignments} WHERE id = ?",
            list(updates.values()) + [template_id],
        )
    return get_template(template_id, db_path)


def delete_template(
    template_id: str, db_path: Optional[Path] = None
) -> None:
    """删除模板。"""
    with _write(db_path) as conn:
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))


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


# =============================================
# Bot 审计（写入 / 生成必录，SPEC-feishu-bot §8）
# =============================================

def record_audit(
    action: str,
    open_id: str = "",
    role: str = "",
    case_id: str = "",
    result: str = "",
    db_path: Optional[Path] = None,
) -> None:
    """记录一条 Bot 写操作审计（失败不抛，避免审计影响主流程）。"""
    from datetime import datetime
    with _write(db_path) as conn:
        conn.execute(
            "INSERT INTO bot_audit (ts, open_id, role, action, case_id, result) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), open_id, role, action, case_id, result),
        )


def list_audit(limit: int = 50, db_path: Optional[Path] = None) -> list[dict]:
    """最近审计记录（倒序）。"""
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT ts, open_id, role, action, case_id, result FROM bot_audit "
            "ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
