"""元数据端点（docs/03 §6.2 / SPEC §6.5）。

- GET /metadata ...... 字段元数据（驱动前端动态渲染）+ 枚举字典 + 口径版本 +
                       规则版本 + 同步状态 + 基线（前端 /api/v1/metadata 一次拉取）；
- GET /enums/{field} .. 单字段枚举（含别名/颜色，aliases 表驱动）。

CASE_FIELD_META 为全站字段权威元数据（search 白名单 / export 列名 / 详情序列化共用），
与 models.fact.Case 列一一对应；filterable 列进 SEARCH_FILTER_TYPES 白名单。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ok
from app.core.config import get_settings
from app.core.database import get_db
from app.models.meta import CleanRule, EnumDict, MetricDef
from app.models.ops import Setting, SyncJob

router = APIRouter(tags=["metadata"])

# 字段元数据（key=Case 列名；label=中文展示名；type: str/num/date/json/bool）
CASE_FIELD_META: dict[str, dict] = {
    "id": {"key": "id", "label": "内部 ID", "type": "num", "filterable": False, "sortable": True},
    "record_id": {"key": "record_id", "label": "同步键", "type": "str", "filterable": False, "sortable": True},
    "case_no": {"key": "case_no", "label": "案号", "type": "str", "filterable": True, "sortable": True},
    "case_no_raw": {"key": "case_no_raw", "label": "案号（原始）", "type": "str", "filterable": False, "sortable": False},
    "case_no_ext": {"key": "case_no_ext", "label": "合并拆分案号", "type": "json", "filterable": False, "sortable": False},
    "related_case_no": {"key": "related_case_no", "label": "关联案号", "type": "str", "filterable": False, "sortable": False},
    "case_status": {"key": "case_status", "label": "案件状态", "type": "str", "filterable": True, "sortable": True},
    "court_date": {"key": "court_date", "label": "最近开庭", "type": "date", "filterable": True, "sortable": True},
    "merged_count": {"key": "merged_count", "label": "合并案件数", "type": "num", "filterable": True, "sortable": True},
    "year": {"key": "year", "label": "收案年份", "type": "num", "filterable": True, "sortable": True},
    "year_raw": {"key": "year_raw", "label": "收案年份（原始）", "type": "str", "filterable": False, "sortable": False},
    "accept_date": {"key": "accept_date", "label": "收案时间", "type": "date", "filterable": True, "sortable": True},
    "plaintiff": {"key": "plaintiff", "label": "原告", "type": "str", "filterable": True, "sortable": True},
    "plaintiff_raw": {"key": "plaintiff_raw", "label": "原告（原始）", "type": "str", "filterable": False, "sortable": False},
    "defendant": {"key": "defendant", "label": "被告", "type": "json", "filterable": True, "sortable": False},
    "defendant_raw": {"key": "defendant_raw", "label": "被告（原始）", "type": "json", "filterable": False, "sortable": False},
    "other_parties": {"key": "other_parties", "label": "其他当事人", "type": "str", "filterable": False, "sortable": False},
    "cause": {"key": "cause", "label": "案由", "type": "str", "filterable": True, "sortable": True},
    "court": {"key": "court", "label": "管辖法院", "type": "json", "filterable": True, "sortable": False},
    "arbitration_org": {"key": "arbitration_org", "label": "仲裁机构", "type": "json", "filterable": False, "sortable": False},
    "court_raw": {"key": "court_raw", "label": "法院（原始）", "type": "json", "filterable": False, "sortable": False},
    "amount": {"key": "amount", "label": "标的金额", "type": "num", "filterable": True, "sortable": True},
    "song_count": {"key": "song_count", "label": "涉案歌曲数", "type": "num", "filterable": True, "sortable": True},
    "artist": {"key": "artist", "label": "艺人", "type": "json", "filterable": True, "sortable": False},
    "per_song_amount": {"key": "per_song_amount", "label": "单曲判赔", "type": "num", "filterable": True, "sortable": True},
    "doc1_date": {"key": "doc1_date", "label": "一审文书时间", "type": "date", "filterable": True, "sortable": True},
    "doc2_date": {"key": "doc2_date", "label": "二审文书时间", "type": "date", "filterable": True, "sortable": True},
    "resolve": {"key": "resolve", "label": "结案原因", "type": "str", "filterable": True, "sortable": True},
    "resolve_detail": {"key": "resolve_detail", "label": "具体结案原因", "type": "str", "filterable": False, "sortable": False},
    "payer": {"key": "payer", "label": "支付主体", "type": "str", "filterable": True, "sortable": True},
    "support_rate": {"key": "support_rate", "label": "对方诉求支持率", "type": "num", "filterable": True, "sortable": True},
    "pay_date": {"key": "pay_date", "label": "支付时间", "type": "date", "filterable": True, "sortable": True},
    "pay_amount": {"key": "pay_amount", "label": "支付总金额", "type": "num", "filterable": True, "sortable": True},
    "case_owner": {"key": "case_owner", "label": "负责人 id", "type": "str", "filterable": False, "sortable": True},
    "case_owner_name": {"key": "case_owner_name", "label": "案件负责人", "type": "str", "filterable": False, "sortable": True},
    "lawyer_fee": {"key": "lawyer_fee", "label": "律师代理费", "type": "str", "filterable": False, "sortable": False},
    "notes": {"key": "notes", "label": "办案笔记", "type": "str", "filterable": False, "sortable": False},
    "close_date": {"key": "close_date", "label": "结案日期", "type": "date", "filterable": True, "sortable": True},
    "exec_case_no": {"key": "exec_case_no", "label": "执行案号", "type": "str", "filterable": False, "sortable": False},
    "judge_info": {"key": "judge_info", "label": "承办法官", "type": "str", "filterable": False, "sortable": False},
    "judge_name": {"key": "judge_name", "label": "法官（提取）", "type": "str", "filterable": False, "sortable": False},
    "biz_line": {"key": "biz_line", "label": "业务线", "type": "str", "filterable": True, "sortable": True},
    "parent_record_id": {"key": "parent_record_id", "label": "系列案父记录", "type": "str", "filterable": True, "sortable": False},
    "remark": {"key": "remark", "label": "备注", "type": "str", "filterable": False, "sortable": False},
    "withdraw_user": {"key": "withdraw_user", "label": "撤卷申请人", "type": "str", "filterable": False, "sortable": False},
    "synced_at": {"key": "synced_at", "label": "同步时间", "type": "date", "filterable": False, "sortable": True},
    "dirty_flags": {"key": "dirty_flags", "label": "脏标记", "type": "json", "filterable": False, "sortable": False},
    "created_at": {"key": "created_at", "label": "创建时间", "type": "date", "filterable": False, "sortable": True},
    "updated_at": {"key": "updated_at", "label": "更新时间", "type": "date", "filterable": False, "sortable": True},
}

# 检索/导出默认展示列（02-search 表格 + 导出默认全列引用）
DEFAULT_COLUMNS: tuple[str, ...] = (
    "record_id", "case_no", "plaintiff", "defendant", "court", "cause",
    "biz_line", "case_status", "year", "resolve", "amount", "pay_amount",
    "song_count", "per_song_amount", "support_rate", "court_date",
    "close_date", "case_owner_name",
)

_FIELD_VIEW = (
    "case_no", "case_status", "court_date", "year", "plaintiff", "cause",
    "biz_line", "resolve", "payer", "support_rate", "pay_amount", "court",
)


def _setting_json(db: Session, key: str) -> dict | None:
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        return None
    try:
        return json.loads(row.value)
    except (TypeError, ValueError):
        return None


@router.get("/metadata")
def get_metadata(db: Session = Depends(get_db)) -> dict:
    """前端 /metadata 一次拉取：字段 + 枚举 + 口径/规则版本 + 同步状态 + 基线。"""
    enums: dict[str, list[dict]] = {}
    for ed in db.scalars(select(EnumDict).order_by(EnumDict.field, EnumDict.sort, EnumDict.enum_key)).all():
        item = {
            "enum_key": ed.enum_key,
            "label": ed.label,
            "color": ed.color,
            "aliases": _load(ed.aliases),
            "version": ed.version,
        }
        enums.setdefault(ed.field, []).append(item)
    rules = db.scalars(select(CleanRule).order_by(CleanRule.priority, CleanRule.rule_tag)).all()
    latest_job = db.scalar(select(SyncJob).order_by(SyncJob.id.desc()).limit(1))
    return ok(
        {
            "fields": [
                {**meta, "in_default": meta["key"] in DEFAULT_COLUMNS}
                for meta in CASE_FIELD_META.values()
            ],
            "view_fields": list(_FIELD_VIEW),
            "enums": enums,
            "rules": [
                {
                    "rule_tag": r.rule_tag, "version": r.version,
                    "target_field": r.target_field, "rule_type": r.rule_type,
                    "priority": r.priority, "enabled": r.enabled,
                    "description": r.description,
                }
                for r in rules
            ],
            "metric_defs": [
                {
                    "key": m.key, "title": m.title, "version": m.version,
                    "definition": m.definition, "footnote": m.footnote,
                    "sample_n": m.sample_n, "enabled": m.enabled,
                }
                for m in db.scalars(select(MetricDef).order_by(MetricDef.key)).all()
            ],
            "versions": {
                "metric": _setting_json(db, "current_metric_versions"),
                "clean_rules": _setting_json(db, "clean_rule_version"),
                "schema": _setting_json(db, "schema_version"),
                "baseline": _setting_json(db, "baseline"),
            },
            "feishu_configured": get_settings().feishu_configured,
            "latest_sync": {
                "id": latest_job.id, "type": latest_job.job_type,
                "status": latest_job.status, "total": latest_job.total,
                "upserted": latest_job.upserted, "skipped": latest_job.skipped,
                "finished_at": latest_job.finished_at, "error_brief": latest_job.error_brief,
                "last_sync_at": latest_job.last_sync_at,
            } if latest_job else None,
        },
        footnote="口径/规则版本指针见 versions（11-dicts、08-metrics 页版本切换依据）",
    )


@router.get("/enums/{field}")
def get_enums(field: str, db: Session = Depends(get_db)) -> dict:
    """单字段枚举列表（别名/颜色/版本；aliases 为 原始选项→规范值 映射）。"""
    rows = db.scalars(
        select(EnumDict).where(EnumDict.field == field).order_by(EnumDict.sort, EnumDict.enum_key)
    ).all()
    data = [
        {"enum_key": e.enum_key, "label": e.label, "color": e.color,
         "aliases": _load(e.aliases), "version": e.version}
        for e in rows
    ]
    return ok(data, total=len(data), footnote=f"枚举字典 field={field}（别名合并项按 aliases 表驱动）")


def _load(value) -> object | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value