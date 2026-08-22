"""案件 CRUD API。"""
from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CaseIn(BaseModel):
    case_number: str
    court: str = ""
    cause: str = ""
    hearing_date: str = ""
    opposing_party: str = ""
    our_role: str = "原告"
    company_id: int | None = None
    agent_id: int | None = None


class CaseOut(BaseModel):
    id: int
    case_number: str
    court: str
    cause: str
    hearing_date: str
    opposing_party: str
    our_role: str
    company_id: int | None
    agent_id: int | None
    status: str | None = None
    created_at: str | None = None


# 案件列表/导出的公共过滤条件（动态兼容各 schema 列）。
def _build_case_where(cols: set, search: str, status: str, hearing_from: str, hearing_to: str):
    cause_col = "case_cause" if "case_cause" in cols else "cause"
    status_col = "status" if "status" in cols else None
    where, args = [], []
    if search:
        where.append(f"(case_number LIKE ? OR court LIKE ? OR {cause_col} LIKE ?)")
        kw = f"%{search}%"
        args.extend([kw, kw, kw])
    if status and status_col:
        where.append(f"{status_col} = ?")
        args.append(status)
    if hearing_from:
        where.append("hearing_date >= ?")
        args.append(hearing_from)
    if hearing_to:
        where.append("hearing_date != '' AND hearing_date <= ?")
        args.append(hearing_to)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return where_sql, args, cause_col, status_col


@router.get("", response_model=list[CaseOut])
def list_cases(
    search: str = "",
    status: str = "",
    hearing_from: str = "",
    hearing_to: str = "",
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    from app.core.database import get_conn
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
        # 兼容不同 schema
        cause_col = "case_cause" if "case_cause" in cols else "cause"
        created_col = "created_at" if "created_at" in cols else ("updated_at" if "updated_at" in cols else None)
        status_col = "status" if "status" in cols else None
        sel_cols = f"id, case_number, court, {cause_col} as cause, hearing_date, opposing_party, our_role, company_id, agent_id"
        if created_col:
            sel_cols += f", {created_col} as created_at"
        if status_col:
            sel_cols += f", {status_col} as status"
        order_col = created_col or "id"
        # 搜索/筛选（全参数可选，不传 = 全部）
        where_sql, args, _, _ = _build_case_where(
            cols, search, status, hearing_from, hearing_to
        )
        rows = conn.execute(
            f"SELECT {sel_cols} FROM cases{where_sql} ORDER BY {order_col} DESC", args
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            results.append(CaseOut(
                id=d["id"], case_number=d["case_number"], court=d["court"],
                cause=d.get("cause", ""), hearing_date=d.get("hearing_date", ""),
                opposing_party=d.get("opposing_party", ""), our_role=d.get("our_role", ""),
                company_id=d.get("company_id"), agent_id=d.get("agent_id"),
                status=d.get("status"), created_at=d.get("created_at"),
            ))
        return results


@router.post("", response_model=CaseOut)
def create_case(body: CaseIn, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    from app.api.presets import register_preset
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
        cause_col = "case_cause" if "case_cause" in cols else "cause"
        # 自动注册预设库（新法院/案由入库，已有则频次 +1）
        register_preset(conn, x_workspace_id, "court", body.court)
        register_preset(conn, x_workspace_id, "cause", body.cause)
        conn.execute(
            f"""INSERT INTO cases
               (case_number, court, {cause_col}, hearing_date, opposing_party,
                our_role, company_id, agent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.case_number, body.court, body.cause, body.hearing_date,
             body.opposing_party, body.our_role, body.company_id, body.agent_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cases WHERE id = last_insert_rowid()").fetchone()
        conn.row_factory = sqlite3.Row
        d = dict(row)
        # F6 操作日志
        from app.api.audit import log_action
        log_action(x_workspace_id, "case_create", f"case {d['id']} {d['case_number']}")
        return CaseOut(
            id=d["id"], case_number=d["case_number"], court=d.get("court", ""),
            cause=d.get("cause") or d.get("case_cause", ""),
            hearing_date=d.get("hearing_date", ""), opposing_party=d.get("opposing_party", ""),
            our_role=d.get("our_role", ""), company_id=d.get("company_id"),
            agent_id=d.get("agent_id"), status=d.get("status"),
            created_at=d.get("created_at") or d.get("updated_at"),
        )


@router.delete("/{case_id}")
def delete_case(case_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    with get_conn(x_workspace_id) as conn:
        row = conn.execute("SELECT case_number FROM cases WHERE id = ?", (case_id,)).fetchone()
        case_number = row["case_number"] if row else ""
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        conn.commit()
    # F6 操作日志
    from app.api.audit import log_action
    log_action(x_workspace_id, "case_delete", f"case {case_id} {case_number}")
    return {"ok": True}


# ── F4 CSV 导出 ───────────────────────────────────────────────────────────
_CSV_COLUMNS = [
    "case_number", "court", "cause", "hearing_date", "opposing_party",
    "our_role", "status", "created_at", "company_name", "agent_name",
]


def _csv_safe(row: list) -> list:
    """CSV 注入防护：首字符 = + - @ 时前缀 '。"""
    dangerous = ("=", "+", "-", "@")
    return [f"'{v}" if v.startswith(dangerous) else v for v in row]


@router.get("/export")
def export_cases(
    search: str = "",
    status: str = "",
    hearing_from: str = "",
    hearing_to: str = "",
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    import csv
    import io
    import sqlite3

    from fastapi.responses import Response
    from app.core.database import get_conn
    from app.api.audit import log_action

    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
        cause_col = "case_cause" if "case_cause" in cols else "cause"
        status_col = "status" if "status" in cols else None
        created_col = "created_at" if "created_at" in cols else ("updated_at" if "updated_at" in cols else None)
        where_sql, args, _, _ = _build_case_where(
            cols, search, status, hearing_from, hearing_to
        )
        created_expr = f"cases.{created_col}" if created_col else "''"
        status_expr = status_col or "''"
        sel = (
            f"cases.id, case_number, court, {cause_col} as cause, hearing_date, "
            f"opposing_party, our_role, {status_expr} as status, "
            f"{created_expr} as created_at, "
            "COALESCE(c.name, '') as company_name, COALESCE(a.name, '') as agent_name"
        )
        from_sql = (
            "FROM cases LEFT JOIN companies c ON c.id = cases.company_id "
            "LEFT JOIN agents a ON a.id = cases.agent_id"
        )
        order_col = created_col or "id"
        rows = conn.execute(
            f"SELECT {sel} {from_sql}{where_sql} ORDER BY {order_col} DESC", args
        ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    for r in rows:
        d = dict(r)
        writer.writerow(_csv_safe([str(d.get(c) or "") for c in _CSV_COLUMNS]))

    log_action(x_workspace_id, "export", f"cases {len(rows)} 条")
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8-bom",
        headers={"Content-Disposition": 'attachment; filename="cases_export.csv"'},
    )
