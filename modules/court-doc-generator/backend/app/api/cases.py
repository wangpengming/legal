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


@router.get("", response_model=list[CaseOut])
def list_cases(x_workspace_id: str = Header(alias="X-Workspace-Id")):
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
        rows = conn.execute(f"SELECT {sel_cols} FROM cases ORDER BY {order_col} DESC").fetchall()
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
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        conn.commit()
    return {"ok": True}
