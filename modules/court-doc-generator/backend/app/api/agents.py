"""代理人 CRUD API（含文件上传）。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

from app.core.config import settings


def _agent_dir(ws_id: str, agent_id: int | None = None) -> Path:
    if agent_id:
        p = settings.DATA_DIR / "workspaces" / ws_id / "agents" / str(agent_id)
    else:
        p = settings.DATA_DIR / "workspaces" / ws_id / "agents" / "temp"
    p.mkdir(parents=True, exist_ok=True)
    return p


class AgentIn(BaseModel):
    name: str
    position: str = ""
    phone: str = ""
    id_card: str = ""
    gender: str = ""
    company_id: int | None = None
    is_default: bool = False


class AgentOut(BaseModel):
    id: int
    name: str
    position: str
    phone: str
    id_card: str | None = None        # 身份证号
    id_card_pdf_path: str | None = None  # 身份证 PDF 路径（F-066 修复）
    labor_contract: str | None = None  # 劳动合同 PDF 路径
    company_id: int | None
    is_default: int
    gender: str | None = None
    company_name: str | None = None


@router.get("", response_model=list[AgentOut])
def list_agents(x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    with get_conn(x_workspace_id) as conn:
        import sqlite3
        conn.row_factory = sqlite3.Row
        # 检测表结构（兼容旧表: id_card/labor_contract，新表: id_card_pdf_path/contract_pdf_path）
        cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)")}
        labor_col = "contract_pdf_path" if "contract_pdf_path" in cols else "labor_contract"
        id_card_col = "id_card_pdf_path" if "id_card_pdf_path" in cols else None
        rows = conn.execute(
            f"""SELECT a.id, a.name, a.position, a.phone,
                      a.company_id, a.is_default, a.created_at,
                      a.gender, a.id_card,
                      c.name as company_name,
                      a.{labor_col} as labor_contract
                      {f', a.{id_card_col} as id_card_pdf_path' if id_card_col else ''}
               FROM agents a
               LEFT JOIN companies c ON a.company_id = c.id"""
        ).fetchall()
        return [AgentOut(
            id=r["id"], name=r["name"], position=r["position"],
            phone=r["phone"],
            id_card=r["id_card"] or "",
            id_card_pdf_path=r["id_card_pdf_path"] if id_card_col else None,
            labor_contract=r["labor_contract"],
            company_id=r["company_id"],
            is_default=r["is_default"],
            gender=r["gender"] or "",
            company_name=r["company_name"],
        ) for r in rows]


@router.post("", response_model=AgentOut)
def upsert_agent(body: AgentIn, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        conn.execute(
            """INSERT INTO agents
               (name, position, phone, id_card, gender, company_id, is_default)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name, company_id) DO UPDATE SET
                   position = excluded.position,
                   phone = excluded.phone,
                   id_card = excluded.id_card,
                   gender = excluded.gender,
                   is_default = excluded.is_default""",
            (body.name, body.position, body.phone,
             body.id_card, body.gender,
             body.company_id, int(body.is_default)),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agents WHERE name = ? AND (company_id IS ? OR (company_id IS NULL AND ? IS NULL))",
            (body.name, body.company_id, body.company_id),
        ).fetchone()
        d = dict(row)
        return AgentOut(
            id=d["id"], name=d["name"], position=d["position"],
            phone=d["phone"],
            id_card=d.get("id_card_pdf_path") or d.get("id_card"),
            labor_contract=d.get("contract_pdf_path") or d.get("labor_contract"),
            company_id=d.get("company_id"),
            is_default=d.get("is_default", 0),
            gender=d["gender"] or "",
            company_name=None,
        )


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    id_card: Optional[str] = None
    gender: Optional[str] = None
    company_id: Optional[int] = None
    is_default: Optional[bool] = None


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int,
    body: AgentUpdate,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """按 ID 更新代理人信息（不含文件路径）"""
    from app.core.database import get_conn
    import sqlite3

    fields = {}
    for k, v in body.model_dump().items():
        if v is not None:
            fields[k] = v

    if not fields:
        raise HTTPException(400, "没有要更新的字段")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [agent_id]

    with get_conn(x_workspace_id) as conn:
        conn.execute(
            f"UPDATE agents SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)")}
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not row:
            raise HTTPException(404, "代理人不存在")
        row_dict = dict(row)
        return AgentOut(
            id=row["id"], name=row["name"], position=row["position"],
            phone=row["phone"],
            id_card=row["id_card"] or "",
            id_card_pdf_path=row_dict.get("id_card_pdf_path"),
            labor_contract=row_dict.get("contract_pdf_path") or row_dict.get("labor_contract", ""),
            company_id=row["company_id"],
            is_default=row["is_default"],
            gender=row["gender"] or "",
            company_name=None,
        )


@router.put("/{agent_id}/upload")
@router.put("/{agent_id}/files")
def upload_agent_files(
    agent_id: int,
    id_card: UploadFile | None = File(None),
    labor_contract: UploadFile | None = File(None),
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    from app.core.database import get_conn
    agent_dir = _agent_dir(x_workspace_id, agent_id)
    updates = {}

    # 列名映射：文件名 → 数据库列名（不要依赖字符串替换，列名与文件名不对应）
    _fname_to_col = {
        "id_card.pdf": "id_card_pdf_path",
        "labor_contract.pdf": "contract_pdf_path",
    }

    for fname, upload in [("id_card.pdf", id_card), ("labor_contract.pdf", labor_contract)]:
        if upload:
            path = agent_dir / fname
            with open(path, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            updates[_fname_to_col[fname]] = str(path)

    if updates:
        with get_conn(x_workspace_id) as conn:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE agents SET {set_clause} WHERE id = ?",
                (*updates.values(), agent_id),
            )
            conn.commit()

    return {"ok": True}


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    # 清理文件
    agent_dir = _agent_dir(x_workspace_id, agent_id)
    shutil.rmtree(agent_dir, ignore_errors=True)
    with get_conn(x_workspace_id) as conn:
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        conn.commit()
    return {"ok": True}
