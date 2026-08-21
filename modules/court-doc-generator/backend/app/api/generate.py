"""出庭材料生成 API（复用 generator._generate_to_dir 核心逻辑）。"""
import sys
from pathlib import Path

from fastapi import APIRouter, Header
from pydantic import BaseModel

router = APIRouter()


class GenerateIn(BaseModel):
    case_id: int
    company_id: int
    agent_id: int


class GenerateOut(BaseModel):
    output_dir: str
    files: list[str]
    merged_pdf: str | None = None


@router.post("")
def generate_court_matters(
    body: GenerateIn,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
):
    from app.core.database import get_conn
    import sqlite3
    from app.core.config import settings

    with get_conn(x_workspace_id) as conn:
        conn.row_factory = sqlite3.Row
        case = conn.execute("SELECT * FROM cases WHERE id = ?", (body.case_id,)).fetchone()
        company = conn.execute("SELECT * FROM companies WHERE id = ?", (body.company_id,)).fetchone()
        agent = conn.execute("SELECT * FROM agents WHERE id = ?", (body.agent_id,)).fetchone()
        if not (case and company and agent):
            raise ValueError("case/company/agent not found")

    case = dict(case)
    company = dict(company)
    agent = dict(agent)

    # 输出目录
    case_number = case["case_number"]
    output_dir = (
        settings.DATA_DIR
        / "workspaces"
        / x_workspace_id
        / "outputs"
        / case_number
    )

    # 调 generator._generate_to_dir（完整 7 份材料 + 合并 + zip）
    sys.path.insert(0, str(settings.MODULE_ROOT))
    from generator import _generate_to_dir

    _generate_to_dir(case, company, agent, output_dir)

    # 收集输出文件
    files = sorted(str(p) for p in output_dir.iterdir() if p.suffix in (".pdf", ".docx", ".zip"))
    merged_pdf = output_dir / f"00_合并出庭手续_{case_number}.pdf"
    merged_str = str(merged_pdf) if merged_pdf.exists() else None

    # 记录历史（覆盖：一个案件只保留一条记录）
    with get_conn(x_workspace_id) as conn:
        conn.execute("DELETE FROM generation_history WHERE case_id = ?", (body.case_id,))
        conn.commit()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(generation_history)")}
        insert_cols = ["case_id", "output_dir"]
        insert_vals: list = [body.case_id, str(output_dir)]
        if "workspace_id" in cols:
            insert_cols.append("workspace_id")
            insert_vals.append(x_workspace_id)
        if "case_number" in cols:
            insert_cols.append("case_number")
            insert_vals.append(case_number)
        if "file_count" in cols:
            insert_cols.append("file_count")
            insert_vals.append(len(files))
        conn.execute(
            f"INSERT INTO generation_history ({', '.join(insert_cols)}) VALUES ({', '.join('?' * len(insert_cols))})",
            insert_vals,
        )
        conn.commit()

    return GenerateOut(output_dir=str(output_dir), files=files, merged_pdf=merged_str)
