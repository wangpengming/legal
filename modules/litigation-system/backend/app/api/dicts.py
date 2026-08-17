"""字典与规则端点（docs/03 §6.2 + §4.3：11-dicts 页）。

- GET  /dicts ............... 枚举 + 规则 + 公司归一 + 指标口径 + 版本指针（只读快照）；
- POST /dicts ............... enum（维护 aliases 别名合并）/ rule_toggle（R 规则启停，
                            同步 clean_rule_version 版本指针；UI 保存重跑前提）；
- POST /dicts/test .......... 清洗规则模拟：内存 Case + CleanPipeline._apply 不落库，
                            返回命中事件预览（保存重跑前的「试算」）；
- GET/POST /dicts/dirty-items 脏标记治理：聚合清单（含 mark_dirty 追溯）→
                            adopt（采纳为 CompanyMap）/ edit（改名归一）/ ignore（仅审计）。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.metadata import CASE_FIELD_META
from app.api.schemas import DictTestRequest, DictWriteRequest, DirtyItemAction, audit, ok
from app.clean.pipeline import CleanPipeline
from app.clean.rules import build_ctx
from app.core.database import get_db
from app.models.fact import Case
from app.models.meta import CleanRule, CompanyMap, EnumDict, MetricDef
from app.models.ops import Setting

router = APIRouter(tags=["dicts"])

# 脏标记治理适用「公司/主体类」字段（对齐 CompanyMap 归一语义；其余字段仅审计）
_COMPANY_FIELDS = ("defendant", "plaintiff", "court", "payer", "artist")


def _load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- GET /dicts

@router.get("/dicts")
def get_dicts(db: Session = Depends(get_db)) -> dict:
    """字典页只读快照：枚举（按 field 分组）+ 规则 + 公司映射 + 指标定义 + 版本指针。"""
    enums: dict[str, list[dict]] = {}
    for ed in db.scalars(select(EnumDict).order_by(EnumDict.field, EnumDict.sort, EnumDict.enum_key)).all():
        enums.setdefault(ed.field, []).append(
            {"enum_key": ed.enum_key, "label": ed.label, "color": ed.color,
             "aliases": _load(ed.aliases), "version": ed.version}
        )
    rules = db.scalars(select(CleanRule).order_by(CleanRule.priority, CleanRule.rule_tag)).all()
    company_map = db.scalars(select(CompanyMap).order_by(CompanyMap.company_raw)).all()
    metrics = db.scalars(select(MetricDef).order_by(MetricDef.key)).all()
    versions = {
        "clean_rule": _load(db.scalar(select(Setting).where(Setting.key == "clean_rule_version")).value) if db.scalar(select(Setting).where(Setting.key == "clean_rule_version")) else None,
        "metric": _load(db.scalar(select(Setting).where(Setting.key == "current_metric_versions")).value) if db.scalar(select(Setting).where(Setting.key == "current_metric_versions")) else None,
    }
    return ok(
        {
            "enums": enums,
            "rules": [
                {"rule_tag": r.rule_tag, "version": r.version, "target_field": r.target_field,
                 "rule_type": r.rule_type, "pattern": r.pattern, "replacement": r.replacement,
                 "mapped": _load(r.mapped), "priority": r.priority, "enabled": r.enabled,
                 "description": r.description}
                for r in rules
            ],
            "company_map": [
                {"id": c.id, "company_raw": c.company_raw, "canonical": c.canonical,
                 "source": c.source, "enabled": c.enabled}
                for c in company_map
            ],
            "metric_defs": [
                {"key": m.key, "title": m.title, "version": m.version,
                 "definition": m.definition, "footnote": m.footnote, "enabled": m.enabled}
                for m in metrics
            ],
            "versions": versions,
        },
        footnote="版本指针：clean_rule 为规则启停状态快照（保存重跑依据），metric 为指标口径当前版本映射",
    )


# ---------------------------------------------------------------- POST /dicts

@router.post("/dicts")
def write_dicts(payload: DictWriteRequest, db: Session = Depends(get_db)) -> dict:
    """字典/规则写操作：enum（枚举维护）| rule_toggle（R 规则启停）。"""
    if payload.action == "rule_toggle":
        rule = db.scalar(select(CleanRule).where(CleanRule.rule_tag == payload.rule_tag))
        if rule is None:
            raise HTTPException(status_code=404, detail=f"规则不存在：{payload.rule_tag}")
        new_enabled = payload.enabled if payload.enabled is not None else not rule.enabled
        if new_enabled == rule.enabled:
            return ok({"rule_tag": rule.rule_tag, "enabled": rule.enabled, "changed": False})
        rule.enabled = new_enabled
        # 同步版本指针 clean_rule_version.enabled_rules（seed 权威格式 {"version","enabled_rules"}）
        row = db.scalar(select(Setting).where(Setting.key == "clean_rule_version"))
        if row is not None:
            snap = _load(row.value, {}) or {}
            enabled_rules = list(snap.get("enabled_rules") or [])
            if new_enabled and rule.rule_tag not in enabled_rules:
                enabled_rules.append(rule.rule_tag)
            elif not new_enabled and rule.rule_tag in enabled_rules:
                enabled_rules.remove(rule.rule_tag)
            snap["enabled_rules"] = enabled_rules
            row.value = json.dumps(snap, ensure_ascii=False)
        db.commit()
        audit(db, op_type="api", table_name="clean_rules", action="rule_toggle",
              detail={"rule_tag": rule.rule_tag, "enabled": new_enabled})
        return ok({"rule_tag": rule.rule_tag, "enabled": new_enabled, "changed": True})

    # action == "enum"
    if not payload.field or not payload.enum_key:
        raise HTTPException(status_code=422, detail="action=enum 时 field/enum_key 必填")
    ed = db.scalar(
        select(EnumDict).where(EnumDict.field == payload.field, EnumDict.enum_key == payload.enum_key)
    )
    if ed is None:
        ed = EnumDict(field=payload.field, enum_key=payload.enum_key, version="v1")
        db.add(ed)
        db.flush()
    if payload.label is not None:
        ed.label = payload.label
    if payload.color is not None:
        ed.color = payload.color
    if payload.aliases:
        merged = _load(ed.aliases, {}) or {}
        merged.update(payload.aliases)  # 追加原始选项 → 规范值（合并项去重）
        ed.aliases = json.dumps(merged, ensure_ascii=False)
    db.commit()
    audit(db, op_type="api", table_name="enum_dicts", action="upsert",
          detail={"field": payload.field, "enum_key": payload.enum_key,
                  "label": ed.label, "aliases": payload.aliases})
    return ok({"field": payload.field, "enum_key": payload.enum_key,
               "label": ed.label, "color": ed.color,
               "aliases": _load(ed.aliases)}, footnote="枚举维护：aliases 为 原始选项→规范值 映射（合并项在此追加）")


# ---------------------------------------------------------------- POST /dicts/test

@router.post("/dicts/test")
def test_dicts_rules(payload: DictTestRequest, db: Session = Depends(get_db)) -> dict:
    """清洗规则模拟：样本逐条走启用规则链（内存 Case，不落库）。

    返回每样本：changed / dirty_flags / 事件列表（rule_tag+field+action+前后值）。
    """
    stmt = select(CleanRule).where(CleanRule.enabled.is_(True))
    if payload.rule_tags:
        stmt = stmt.where(CleanRule.rule_tag.in_(payload.rule_tags))
    enabled = list(db.scalars(stmt.order_by(CleanRule.priority, CleanRule.rule_tag)).all())
    if not enabled:
        raise HTTPException(status_code=422, detail="无启用规则（规则全禁用或 rule_tags 未命中）")
    ctx = build_ctx(db)
    pipeline = CleanPipeline(db)
    results = []
    for i, sample in enumerate(payload.samples):
        case = Case()
        for k, v in sample.items():
            if k in CASE_FIELD_META or k in ("record_id", "dirty_flags", "hash"):
                setattr(case, k, v)
        case.record_id = sample.get("record_id") or f"__test_{i}__"
        start = len(ctx.events)
        try:
            changed = pipeline._apply(case, enabled, ctx)
        except Exception as exc:  # noqa: BLE001 单样本失败不阻断整体（防御）
            results.append({"index": i, "error": str(exc), "changed": False, "events": []})
            continue
        events = []
        for e in ctx.events[start:]:
            item = {k: v for k, v in e.items() if k != "record_id"}
            item["record_id"] = case.record_id
            events.append(item)
        results.append(
            {
                "index": i,
                "record_id": case.record_id,
                "changed": changed,
                "dirty_flags": _load(case.dirty_flags, []),
                "events": events,
            }
        )
    return ok(
        results,
        total=len(results),
        footnote="清洗模拟口径 v1.0：内存对象执行启用规则链（R01~R08/R10），不落库不审计；命中即 dirty_flags 字段级标记",
    )


# ---------------------------------------------------------------- dirty-items 治理

def _raw_value(case: Case, field: str) -> str | None:
    """脏字段的原始取值（优先 *_raw 列；无则规范值；JSON 数组 join 展示）。"""
    raw_key = f"{field}_raw"
    if hasattr(case, raw_key):
        v = getattr(case, raw_key)
        if v:
            parsed = _load(v)
            return ", ".join(parsed) if isinstance(parsed, list) else str(parsed)
    v = getattr(case, field, None)
    parsed = _load(v)
    return ", ".join(parsed) if isinstance(parsed, list) else (str(parsed) if parsed is not None else None)


@router.get("/dicts/dirty-items")
def list_dirty_items(db: Session = Depends(get_db)) -> dict:
    """脏标记聚合清单：案件 × 字段级标记 + mark_dirty 审计追溯（规则/时间/原因）。"""
    rows = db.execute(
        text("SELECT id, record_id, case_no, dirty_flags FROM cases WHERE dirty_flags IS NOT NULL")
    ).mappings().all()
    # 追溯：最近 mark_dirty 事件按 (record_id, field) 分组
    audits = db.execute(
        text(
            "SELECT record_id, field, rule_tag, created_at, detail FROM audit_logs "
            "WHERE op_type = 'clean' AND action = 'mark_dirty' ORDER BY id DESC LIMIT 500"
        )
    ).mappings().all()
    by_key: dict[str, list[dict]] = {}
    for a in audits:
        key = f"{a['record_id']}:{a['field']}"
        by_key.setdefault(key, []).append(
            {"rule_tag": a["rule_tag"], "created_at": a["created_at"], "reason": _load(a["detail"], {})}
        )
    items: list[dict] = []
    for r in rows:
        flags = _load(r["dirty_flags"], [])
        if not isinstance(flags, list):
            continue
        for f in flags:
            if not isinstance(f, str):
                continue
            key = f"{r['record_id']}:{f}"
            case = db.scalar(select(Case).where(Case.record_id == r["record_id"]))
            raw = _raw_value(case, f) if case else None
            items.append(
                {
                    "key": key,
                    "record_id": r["record_id"],
                    "case_no": r["case_no"],
                    "field": f,
                    "raw_value": raw,
                    "trace": by_key.get(key, [])[:3],
                }
            )
    items.sort(key=lambda x: (x["field"], x["record_id"]))
    total = len(items)
    return ok(items, total=total, footnote="脏标记口径 v1.0：字段级标记（47 处基线），adopt/edit 可归入 CompanyMap 后清除")


@router.post("/dicts/dirty-items/{key}")
def handle_dirty_item(key: str, payload: DirtyItemAction, db: Session = Depends(get_db)) -> dict:
    """脏标记处置：adopt（采纳）/ edit（改名归一）/ ignore（仅审计）。

    key = "{record_id}:{field}"；adopt/edit 需 value（目标规范值），
    CompanyMap 按 原始值→规范值 写入（source=人工采纳），并清除该字段脏标记。
    """
    if ":" not in key:
        raise HTTPException(status_code=422, detail="key 格式应为 record_id:field")
    record_id, field = key.rsplit(":", 1)
    case = db.scalar(select(Case).where(Case.record_id == record_id))
    if case is None:
        raise HTTPException(status_code=404, detail=f"案件不存在：{record_id}")
    flags = _load(case.dirty_flags, [])
    if not isinstance(flags, list) or field not in flags:
        raise HTTPException(status_code=404, detail=f"该字段无脏标记：{field}（key={key}）")

    raw_value = _raw_value(case, field)
    if payload.action in ("adopt", "edit"):
        canonical = (payload.value or "").strip()
        if not canonical:
            raise HTTPException(status_code=422, detail=f"action={payload.action} 时 value（规范值）必填")
        if field in _COMPANY_FIELDS and raw_value:
            existing = db.scalar(select(CompanyMap).where(CompanyMap.company_raw == raw_value))
            if existing is None:
                db.add(CompanyMap(company_raw=raw_value, canonical=canonical, source="人工采纳"))
            else:
                existing.canonical = canonical
                existing.source = "人工采纳"
    # 清除该字段脏标记（重跑语义：下次管道重建时按新 CompanyMap 不再标记）
    flags.remove(field)
    if flags:
        case.dirty_flags = json.dumps(flags, ensure_ascii=False)
    else:
        case.dirty_flags = None
    db.commit()
    audit(db, op_type="api", table_name="cases", action=f"dirty_{payload.action}",
          record_id=record_id,
          detail={"key": key, "raw_value": raw_value, "canonical": payload.value,
                  "field": field, "remaining": len(flags)})
    return ok(
        {"key": key, "action": payload.action, "field": field,
         "raw_value": raw_value, "canonical": payload.value if payload.action != "ignore" else None,
         "remaining_flags": flags},
        footnote=f"处置语义：{payload.action}（{'写入 CompanyMap 原始值→规范值并清除脏标记' if payload.action != 'ignore' else '仅审计记录，标记保留'}）",
    )