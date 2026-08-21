"""出庭材料生成 API（复用现有 generator.py 逻辑）。"""
import shutil
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
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []

    # 01 营业执照（静态）
    biz = settings.STATIC_DIR / "1.营业执照复印件.pdf"
    if biz.exists():
        shutil.copy2(biz, output_dir / "01_营业执照.pdf")
        files.append(str(output_dir / "01_营业执照.pdf"))

    # 02 法定代表人证明（动态）
    _fill_02(company, case, output_dir, settings.TEMPLATES_DIR)
    if (output_dir / "02_法定代表人证明_1.pdf").exists():
        files.append(str(output_dir / "02_法定代表人证明_1.pdf"))

    # 03 法人身份证（静态）
    legal_id = settings.STATIC_DIR / "法人身份证.pdf"
    if legal_id.exists():
        shutil.copy2(legal_id, output_dir / "03_法人身份证.pdf")
        files.append(str(output_dir / "03_法人身份证.pdf"))

    # 04 授权委托书（动态）
    _fill_04(company, agent, case, output_dir, settings.TEMPLATES_DIR)
    if (output_dir / "04_授权委托书_1.pdf").exists():
        files.append(str(output_dir / "04_授权委托书_1.pdf"))

    # 05 推荐信（动态）
    _fill_05(company, agent, case, output_dir, settings.TEMPLATES_DIR)
    if (output_dir / "05_推荐信_1.pdf").exists():
        files.append(str(output_dir / "05_推荐信_1.pdf"))

    # 06 代理人劳动合同（静态）
    labor = settings.STATIC_DIR / "代理人劳动合同.pdf"
    if labor.exists():
        shutil.copy2(labor, output_dir / "06_代理人劳动合同.pdf")
        files.append(str(output_dir / "06_代理人劳动合同.pdf"))

    # 07 代理人身份证（从 DB 路径）
    agent_id_path = agent.get("id_card", "")
    if agent_id_path and Path(agent_id_path).exists():
        shutil.copy2(agent_id_path, output_dir / "07_代理人身份证.pdf")
        files.append(str(output_dir / "07_代理人身份证.pdf"))

    # 00 合并 PDF
    merged = output_dir / f"00_合并出庭手续_{case_number}.pdf"
    _merge_pdfs([f for f in files if f.endswith(".pdf")], str(merged))
    if merged.exists():
        files.insert(0, str(merged))

    # 记录历史（动态兼容新旧 schema）
    with get_conn(x_workspace_id) as conn:
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

    return GenerateOut(output_dir=str(output_dir), files=files, merged_pdf=str(merged) if merged.exists() else None)


def _fill_02(company, case, output_dir, templates_dir):
    """法定代表人证明（placeholder 替换）。"""
    tpl = templates_dir / "2.法定代表人证明.pdf"
    out = output_dir / "02_法定代表人证明_1.pdf"
    if not tpl.exists():
        return
    try:
        import fitz
        doc = fitz.open(str(tpl))
        for page in doc:
            for annot in page.annots():
                page.delete_annotation(annot)
            text = page.get_text()
            text = text.replace("{公司名称}", company["name"])
            text = text.replace("{法定代表人}", company["legal_rep_name"])
            text = text.replace("{职务}", company["legal_rep_position"])
            text = text.replace("{案号}", case["case_number"])
            if "{公司名称}" in page.get_text():
                page.insert_text(fitz.Point(100, 400), text[:200], fontsize=11)
        doc.save(str(out))
        doc.close()
    except Exception:
        pass


def _fill_04(company, agent, case, output_dir, templates_dir):
    """授权委托书（DOCX → PDF）。"""
    tpl = templates_dir / "4.授权委托书.docx"
    out = output_dir / "04_授权委托书_1.pdf"
    if not tpl.exists():
        return
    try:
        import subprocess
        # 简单复制占位（完整实现复用 generator.py 的 docx 替换逻辑）
        shutil.copy2(tpl, output_dir / "04_授权委托书.docx")
        # DOCX → PDF（依赖系统工具，后续完善）
    except Exception:
        pass


def _fill_05(company, agent, case, output_dir, templates_dir):
    """推荐信（DOCX → PDF）。"""
    tpl = templates_dir / "5.推荐信.docx"
    if not tpl.exists():
        return
    try:
        shutil.copy2(tpl, output_dir / "05_推荐信.docx")
    except Exception:
        pass


def _merge_pdfs(pdf_paths: list[str], output: str):
    """合并多个 PDF。"""
    try:
        import fitz
        doc = fitz.open()
        for p in pdf_paths:
            if not Path(p).exists():
                continue
            src = fitz.open(p)
            doc.insert_pdf(src)
            src.close()
        doc.save(output)
        doc.close()
    except Exception:
        pass
