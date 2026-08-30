"""
Thunderbox Console — 审计日志中间件
====================================

FastAPI 中间件：拦截所有写操作端点（POST/PATCH/DELETE），
将操作记录写入 `data/audit.db`（SQLite）。

数据库表：
  audit_events(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT        NOT NULL,        -- ISO 8601 时间戳
    action      TEXT        NOT NULL,        -- 操作类型
    app_id      TEXT,                      -- 应用 ID
    app_name    TEXT,                      -- 应用名称
    operator    TEXT,                      -- 操作人（预留）
    method      TEXT        NOT NULL,        -- HTTP 方法
    path        TEXT        NOT NULL,        -- 请求路径
    detail_json TEXT,                      -- 请求体（不含敏感字段）
    result      TEXT        NOT NULL,        -- success / error
    message     TEXT,                      -- 结果描述
    duration_ms INTEGER                       -- 耗时（毫秒）
  )

API 端点：
  GET /api/audit  — 查询审计日志（分页）
    ?page=1&page_size=50&action=&app_id=

写入时机：
  中间件在响应发送前拦截，记录请求+响应结果。
  敏感字段（git_token, manager_email, password 等）自动过滤。
"""

from __future__ import annotations

import json
import os
import time
import re
from pathlib import Path
from typing import Optional

import aiosqlite


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).parent.resolve()
_DATA_DIR = os.environ.get("THUNDERBOX_DATA_DIR", str(_BACKEND_DIR.parent / "data"))
_DB_PATH = os.path.join(_DATA_DIR, "audit.db")

# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------

_SENTINEL = object()


async def _init_db():
    """初始化 SQLite 表（如不存在）"""
    os.makedirs(_DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT        NOT NULL,
                action      TEXT        NOT NULL,
                app_id      TEXT,
                app_name    TEXT,
                operator    TEXT,
                method      TEXT        NOT NULL,
                path        TEXT        NOT NULL,
                detail_json TEXT,
                result      TEXT        NOT NULL,
                message     TEXT,
                duration_ms INTEGER
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(ts DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_app ON audit_events(app_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action)
        """)
        await db.commit()


# ---------------------------------------------------------------------------
# 审计记录写入
# ---------------------------------------------------------------------------

async def write_audit(
    action: str,
    method: str,
    path: str,
    result: str,
    app_id: str | None = None,
    app_name: str | None = None,
    operator: str | None = None,
    detail_json: str | None = None,
    message: str | None = None,
    duration_ms: int | None = None,
):
    """写入一条审计记录"""
    import datetime
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO audit_events
                (ts, action, app_id, app_name, operator, method, path, detail_json, result, message, duration_ms)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, action, app_id, app_name, operator, method, path,
             detail_json, result, message, duration_ms),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# 审计查询（分页）
# ---------------------------------------------------------------------------

async def query_audit(
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
    app_id: str | None = None,
    result: str | None = None,
) -> dict:
    """查询审计日志"""
    conditions = []
    params = []
    if action:
        conditions.append("action = ?")
        params.append(action)
    if app_id:
        conditions.append("app_id = ?")
        params.append(app_id)
    if result:
        conditions.append("result = ?")
        params.append(result)
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # 总数
        cur = await db.execute(f"SELECT COUNT(*) AS total FROM audit_events {where_clause}", params)
        row = await cur.fetchone()
        total = row["total"] if row else 0

        # 分页
        offset = (page - 1) * page_size
        cur = await db.execute(
            f"""
            SELECT id, ts, action, app_id, app_name, operator, method, path, detail_json, result, message, duration_ms
            FROM audit_events
            {where_clause}
            ORDER BY ts DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        rows = await cur.fetchall()
        items = [dict(r) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


# ---------------------------------------------------------------------------
# 敏感字段过滤
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = re.compile(
    r"(git_token|password|secret|token|api_key|apikey|auth|credential|private_key|manager_email)",
    re.IGNORECASE,
)


def sanitize_body(body: bytes | None) -> str | None:
    """从请求体中过滤敏感字段"""
    if not body:
        return None
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    if not text.strip():
        return None
    # 尝试解析 JSON 并过滤
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            filtered = {
                k: ("***REDACTED***" if _SENSITIVE_KEYS.search(k) else v)
                for k, v in data.items()
            }
            return json.dumps(filtered, ensure_ascii=False)
        return text[:500]
    except Exception:
        return text[:500]


# ---------------------------------------------------------------------------
# FastAPI 中间件
# ---------------------------------------------------------------------------

_AUDIT_ROUTES = re.compile(
    r"^/api/(apps|domains|audit)"
)


def _route_key(method: str, path: str) -> str | None:
    """从路径提取操作类型"""
    if method in ("POST", "PATCH", "DELETE"):
        m = _AUDIT_ROUTES.match(path)
        if m:
            prefix = m.group(1)
            if prefix == "apps":
                # /api/apps[/<id>[/<action>]]
                parts = path.split("/")
                if len(parts) >= 4 and parts[3]:
                    resource = parts[3]
                    sub = parts[4] if len(parts) >= 5 else None
                    if resource == "domains":
                        return "check_domain"
                    # app 操作
                    action_map = {
                        None: "create_app",
                        "deploy": "deploy",
                        "control": "control",
                        "rollback": "rollback",
                        "config": "update_config",
                        "database": "update_database",
                        "sql": "execute_sql",
                        "migrations": "apply_migration",
                    }
                    return action_map.get(sub, f"app_{sub or 'write'}")
                return "create_app"
            elif prefix == "domains":
                return "check_domain"
    return None


def _extract_app_id(path: str) -> str | None:
    """从路径提取 app_id"""
    parts = path.split("/")
    # /api/apps/<app_id>/...
    if len(parts) >= 4 and parts[2]:
        return parts[3]
    return None


async def audit_middleware(request, call_next):
    """审计中间件：拦截所有请求，记录写操作"""
    t0 = time.monotonic()
    method = request.method
    path = request.url.path

    action = _route_key(method, path)
    app_id = _extract_app_id(path) if method in ("POST", "PATCH", "DELETE") else None

    # 读取请求体（用于记录 detail）
    body_bytes = None
    if method in ("POST", "PATCH"):
        body_bytes = await request.body()
        # 重置 body 以便后续处理
        async def receive():
            return {"type": "http.request", "body": body_bytes}
        request._receive = receive

    # 调用实际处理函数
    response = await call_next(request)
    duration_ms = int((time.monotonic() - t0) * 1000)

    # 仅记录写操作（DB 错误不影响正常请求）
    if action:
        result = "success" if response.status_code < 400 else "error"
        message = None
        if response.status_code >= 500:
            message = f"HTTP {response.status_code}"
        elif response.status_code >= 400:
            message = f"HTTP {response.status_code}"

        detail_json = sanitize_body(body_bytes)
        try:
            await write_audit(
                action=action,
                method=method,
                path=path,
                result=result,
                app_id=app_id,
                detail_json=detail_json,
                message=message,
                duration_ms=duration_ms,
            )
        except Exception:
            pass  # 审计失败不影响请求

    return response
