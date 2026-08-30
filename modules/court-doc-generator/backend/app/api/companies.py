"""公司 CRUD API + 文件上传。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

from app.core.config import settings


def _company_dir(ws_id: str, company_id: int | None = None) -> Path:
    """获取公司文件目录。"""
    if company_id:
        p = settings.DATA_DIR / "workspaces" / ws_id / "companies" / str(company_id)
    else:
        p = settings.DATA_DIR / "workspaces" / ws_id / "companies" / "temp"
    p.mkdir(parents=True, exist_ok=True)
    return p


class CompanyIn(BaseModel):
    name: str
    credit_code: str = ""
    legal_rep_name: str = ""
    legal_rep_position: str = ""
    legal_rep_id_card: str = ""
    address: str = ""
    phone: str = ""


class CompanyOut(BaseModel):
    id: int
    name: str
    credit_code: str = ""
    legal_rep_name: str = ""
    legal_rep_position: str = ""
    legal_rep_id_card: str = ""
    address: str = ""
    phone: str = ""
    business_license_path: str = ""
    legal_rep_id_card_path: str = ""
    legal_rep_cert_path: str = ""
    power_of_attorney_path: str = ""
    recommendation_path: str = ""


def _get_ws_id(x_workspace_id: str = Header(...)) -> str:
    return x_workspace_id


@router.get("", response_model=list[CompanyOut])
def list_companies(x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    with get_conn(x_workspace_id) as conn:
        import sqlite3
        conn.row_factory = sqlite3.Row
        # 动态检测表结构（兼容新旧 schema）
        cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
        # 新字段映射
        file_fields = {
            "business_license_path": "business_license_path",
            "legal_rep_id_card_path": "legal_rep_id_card_path",
            "legal_rep_cert_path": "legal_rep_cert_path",
        }
        rows = conn.execute("SELECT * FROM companies").fetchall()
        return [CompanyOut(**dict(r)) for r in rows]


@router.post("", response_model=CompanyOut)
def upsert_company(body: CompanyIn, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    import sqlite3
    with get_conn(x_workspace_id) as conn:
        conn.execute(
            """INSERT INTO companies
               (name, credit_code, legal_rep_name, legal_rep_position,
                legal_rep_id_card, address, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   credit_code = excluded.credit_code,
                   legal_rep_name = excluded.legal_rep_name,
                   legal_rep_position = excluded.legal_rep_position,
                   legal_rep_id_card = excluded.legal_rep_id_card,
                   address = excluded.address,
                   phone = excluded.phone""",
            (body.name, body.credit_code, body.legal_rep_name,
             body.legal_rep_position, body.legal_rep_id_card,
             body.address, body.phone),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM companies WHERE name = ?", (body.name,)
        ).fetchone()
        return CompanyOut(**dict(row))


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    credit_code: Optional[str] = None
    legal_rep_name: Optional[str] = None
    legal_rep_position: Optional[str] = None
    legal_rep_id_card: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    business_license_path: Optional[str] = None
    legal_rep_cert_path: Optional[str] = None
    legal_rep_id_card_path: Optional[str] = None
    power_of_attorney_path: Optional[str] = None
    recommendation_path: Optional[str] = None


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    body: CompanyUpdate,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """按 ID 更新公司信息（字段不传则不更新）"""
    from app.core.database import get_conn
    import sqlite3

    fields = {}
    for k, v in body.model_dump().items():
        if v is not None:
            fields[k] = v

    if not fields:
        raise HTTPException(400, "没有要更新的字段")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [company_id]
    with get_conn(x_workspace_id) as conn:
        conn.execute(
            f"UPDATE companies SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "公司不存在")
        return CompanyOut(**dict(row))


@router.put("/{company_id}/files")
def update_company_files(
    company_id: int,
    field: str,
    path: str,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """更新公司文件路径（营业执照/法人身份证/法定代表人证明）。
    
    field: "business_license" | "legal_rep_id_card" | "legal_rep_cert"
    """
    from app.core.database import get_conn
    
    field_map = {
        "business_license": "business_license_path",
        "legal_rep_id_card": "legal_rep_id_card_path",
        "legal_rep_cert": "legal_rep_cert_path",
    }
    if field not in field_map:
        raise HTTPException(400, f"未知字段: {field}")
    
    col_name = field_map[field]
    
    with get_conn(x_workspace_id) as conn:
        conn.execute(
            f"UPDATE companies SET {col_name} = ? WHERE id = ?",
            (path, company_id),
        )
        conn.commit()
    
    return {"ok": True, "field": col_name, "path": path}


@router.delete("/{company_id}")
def delete_company(company_id: int, x_workspace_id: str = Header(alias="X-Workspace-Id")):
    from app.core.database import get_conn
    # 清理文件
    company_dir = _company_dir(x_workspace_id, company_id)
    shutil.rmtree(company_dir, ignore_errors=True)
    with get_conn(x_workspace_id) as conn:
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        conn.commit()
    return {"ok": True}


@router.put("/{company_id}/upload")
def upload_company_files(
    company_id: int,
    business_license: UploadFile | None = File(None),
    legal_rep_id_card: UploadFile | None = File(None),
    legal_rep_cert: UploadFile | None = File(None),
    power_of_attorney: UploadFile | None = File(None),
    recommendation: UploadFile | None = File(None),
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    """上传公司文件：营业执照 + 法人身份证 + 法定代表人证明 + 授权委托书 + 推荐信。
    
    所有文件均为可选，上传则保存到公司目录并更新数据库路径。
    """
    from app.core.database import get_conn
    company_dir = _company_dir(x_workspace_id, company_id)
    updates = {}

    # 文件名 → 字段名映射
    file_mappings = [
        ("01_营业执照.pdf", business_license, "business_license_path"),
        ("02_法人身份证.pdf", legal_rep_id_card, "legal_rep_id_card_path"),
        ("02_法定代表人证明.pdf", legal_rep_cert, "legal_rep_cert_path"),
        ("04_授权委托书.pdf", power_of_attorney, "power_of_attorney_path"),
        ("05_推荐信.pdf", recommendation, "recommendation_path"),
    ]

    for fname, upload, field_name in file_mappings:
        if upload:
            path = company_dir / fname
            with open(path, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            updates[field_name] = str(path)

    if updates:
        with get_conn(x_workspace_id) as conn:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE companies SET {set_clause} WHERE id = ?",
                (*updates.values(), company_id),
            )
            conn.commit()

    return {"ok": True, "updated": list(updates.keys())}
