"""Mode B 报告端点（docs/03 §7.3 / 需求 F5.2：模板生成 + 报告存档）。

POST /reports/generate 调用 app.ai.reports.render_report 渲染 T1~T7 Markdown，
组装三源交叉脚注（local=cases 表、cases=external_cases 表、law=法规库）后
落库 reports 表；GET /reports 分页列表 / GET /reports/{id} 详情 / DELETE 删除。
生成口径与 /stats/*、/metrics 引擎同构（render_report 内部单一口径源）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.reports import render_report, triple_sources
from app.api.schemas import ReportGenerateRequest, audit, ok
from app.core.database import get_db
from app.models.ops import Report

router = APIRouter(tags=["reports"])

TEMPLATE_KEYS = {"T1", "T2", "T3", "T4", "T5", "T6", "T7"}


def _report_dict(r: Report) -> dict:
    params = {}
    if r.params_json:
        try:
            params = json.loads(r.params_json)
        except (TypeError, ValueError):
            params = {}
    created = ""
    if hasattr(r, "created_at") and r.created_at:
        try:
            created = datetime.fromtimestamp(r.created_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            created = ""
    return {
        "id": r.id,
        "template_key": r.template_key,
        "title": r.title,
        "params": params,
        "created_by": r.created_by,
        "created_at": created,
        "body": r.body,
    }


@router.post("/reports/generate")
def generate_report(payload: ReportGenerateRequest, db: Session = Depends(get_db)) -> dict:
    """生成并落库报告（Mode B T1~T7；幂等约束：同模板+同参数不重复生成）。"""
    key = (payload.template_key or "").strip().upper()
    if key not in TEMPLATE_KEYS:
        raise HTTPException(status_code=400, detail=f"未知报告模板：{payload.template_key}")
    duplicate = db.scalar(
        select(Report).where(
            Report.template_key == key,
            Report.params_json == json.dumps(payload.params, ensure_ascii=False),
        ).order_by(Report.id.desc())
    )
    if duplicate is not None:
        r = duplicate
    else:
        try:
            title, body = render_report(db, key, payload.params)
        except Exception as e:  # noqa: BLE001 渲染容错为 HTTP 400
            raise HTTPException(status_code=400, detail=f"报告渲染失败：{e}") from e
        r = Report(
            template_key=key,
            title=title,
            body=body,
            params_json=json.dumps(payload.params, ensure_ascii=False),
            created_by=payload.created_by or "api",
        )
        db.add(r)
        db.commit()
        db.refresh(r)
    audit(db, op_type="ai", table_name="reports", action="generate",
          detail={"template_key": key, "params": payload.params}, record_id=str(r.id))
    result = _report_dict(r)
    result["sources"] = triple_sources(db, key, payload.params)
    return ok(result, footnote="Mode B 报告：render_report 单一口径生成；三源脚注与 G10 交叉验证一致")


@router.get("/reports")
def list_reports(page: int = 1, page_size: int = 20, template_key: str | None = None,
                 db: Session = Depends(get_db)) -> dict:
    """报告存档列表（倒序，可选模板过滤；列表不含 body 正文）。"""
    stmt = select(Report).order_by(Report.id.desc())
    if template_key:
        stmt = stmt.where(Report.template_key == template_key.strip().upper())
    total = len(db.scalars(stmt).all())
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    data = [{k: v for k, v in _report_dict(r).items() if k != "body"} for r in rows]
    return ok(data, total=total, page=page, page_size=page_size)


@router.get("/reports/{report_id}")
def report_detail(report_id: int, db: Session = Depends(get_db)) -> dict:
    """报告详情（含正文 Markdown + 三源脚注重算）。"""
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"报告不存在：{report_id}")
    params = {}
    if r.params_json:
        try:
            params = json.loads(r.params_json)
        except (TypeError, ValueError):
            params = {}
    result = _report_dict(r)
    result["sources"] = triple_sources(db, r.template_key, params)
    return ok(result, footnote="报告详情：正文为生成时快照；三源脚注按当前数据重算")


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)) -> dict:
    """删除存档报告（审计记录动作）。"""
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"报告不存在：{report_id}")
    audit(db, op_type="ai", table_name="reports", action="delete",
          detail={"template_key": r.template_key, "title": r.title}, record_id=str(r.id))
    db.delete(r)
    db.commit()
    return ok({"id": report_id, "deleted": True}, footnote="已删除存档报告")