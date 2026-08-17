"""检索与案件详情端点（docs/03 §6.2 / SPEC §6.5）。

- POST /search ...... FTS5 检索 + 白名单筛选/排序 + 分页 + 口径脚注；
- GET  /cases/{id} ...... 详情五区（基础列 / raw 留档 / audit 摘要 / 关联歌曲 / 系列案树）；
- GET  /cases/{id}/raw .. 原始值整包（原始视图）；
- POST /cases/batch .... 批量打标签 / 导出审计（导出本体走 POST /export）。

查询构建函数（build_case_query / apply_filters）同时供 /export 复用，
筛选字段白名单见 app.api.metadata.CASE_FIELD_META（filterable 标记）。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.metadata import CASE_FIELD_META, DEFAULT_COLUMNS
from app.api.schemas import CaseBatchRequest, SearchRequest, audit, ok
from app.core.database import get_db
from app.models.fact import Case, RawCase, Song, SongCase
from app.models.fts import search_cases
from app.models.ops import AuditLog, Tag, TagLink

router = APIRouter(tags=["search"])

# 检索/筛选白名单：字段 → 值类型（防御：类型非法即忽略该条件，不报错）。
# JSON 数组列（defendant/court/artist）按「序列化文本包含」匹配；
# 日期列接受 epoch_ms 数字；金额列接受数字。
SEARCH_FILTER_TYPES: dict[str, type] = {
    "case_no": str, "plaintiff": str, "defendant": str, "court": str,
    "artist": str, "cause": str, "resolve": str, "payer": str,
    "biz_line": str, "case_status": str, "parent_record_id": str,
    "year": int, "merged_count": int, "song_count": int,
    "amount": float, "pay_amount": float, "per_song_amount": float,
    "support_rate": float, "accept_date": int, "court_date": int,
    "close_date": int, "pay_date": int, "doc1_date": int, "doc2_date": int,
}
_JSON_COLS = {"defendant", "court", "artist"}


def apply_filters(filters: list, where: list[str], params: dict, prefix: str = "cases") -> None:
    """SearchFilter 列表 → SQL 条件（命名参数 p{n}；ftp 白名单外字段直接忽略）。"""
    for i, f in enumerate(filters):
        col = f.field
        if col not in SEARCH_FILTER_TYPES:
            continue
        typed = SEARCH_FILTER_TYPES[col]
        p = f"{prefix}_p{i}"
        if f.op in ("eq", "ne"):
            v = f.value
            if v in (None, ""):
                continue
            try:
                val = typed(v)
            except (TypeError, ValueError):
                continue
            target = f"{prefix}.{col}"
            if typed is str and col in _JSON_COLS:
                target, val = f"{prefix}.{col}", f'%"{val}"%'
                where.append(f"{target} NOT LIKE :{p}" if f.op == "ne" else f"{target} LIKE :{p}")
            else:
                where.append(f"{target} != :{p}" if f.op == "ne" else f"{target} = :{p}")
            params[p] = val
        elif f.op in ("in", "nin"):
            vals = f.values or []
            if not vals:
                continue
            try:
                vals = [typed(v) for v in vals if v not in (None, "")]
            except (TypeError, ValueError):
                continue
            if not vals:
                continue
            key = f"{prefix}.{col}"
            if typed is str and col in _JSON_COLS:
                # JSON 数组列 in/nin：转逐值 OR（JSON 串包含）
                key = f"{prefix}.{col}"
                placeholders = " OR ".join(f"{key} LIKE :{p}x{j}" for j in range(len(vals)))
                params.update({f"{p}x{j}": f'%"{v}"%' for j, v in enumerate(vals)})
                where.append(f"NOT ({placeholders})" if f.op == "nin" else f"({placeholders})")
            else:
                placeholders = ", ".join(f":{p}x{j}" for j in range(len(vals)))
                params.update({f"{p}x{j}": v for j, v in enumerate(vals)})
                where.append(f"{key} NOT IN ({placeholders})" if f.op == "nin" else f"{key} IN ({placeholders})")
        elif f.op == "contains":
            v = f.value
            if v in (None, "") or not isinstance(v, str):
                continue
            where.append(f"{prefix}.{col} LIKE :{p}")
            params[p] = f"%{v}%"
        elif f.op == "range":
            lo, hi = f.min, f.max
            if lo is None and hi is None:
                continue
            try:
                lo = typed(lo) if lo is not None else None
                hi = typed(hi) if hi is not None else None
            except (TypeError, ValueError):
                continue
            key = f"{prefix}.{col}"
            if lo is not None:
                where.append(f"{key} >= :{p}lo")
                params[f"{p}lo"] = lo
            if hi is not None:
                where.append(f"{key} <= :{p}hi")
                params[f"{p}hi"] = hi


def build_case_query(db: Session, q: str | None, filters: list,
                     sorts: list | None = None, columns: list[str] | None = None,
                     limit: int | None = None, offset: int = 0) -> tuple[list[dict], int]:
    """通用案件查询（/search 与 /export 共用）。

    返回 (rows, total)；rows 元素为选列 dict（JSON 列已解析）。q 走 FTS5
    （search_cases 返回 case_id 列表）与筛选条件 AND 合并。
    """
    cols = _pick_columns(columns or DEFAULT_COLUMNS)
    where: list[str] = []
    params: dict = {}
    if q and q.strip():
        ids, _ = search_cases(db, q, limit=50000, offset=0)
        if not ids:
            return [], 0
        # SQLite 不绑定 list 参数：json_each 展开（无 999 占位符上限，10 万行兜底）
        where.append("cases.id IN (SELECT value FROM json_each(:qids))")
        params["qids"] = json.dumps([r["case_id"] for r in ids])
    apply_filters(filters, where, params)
    where_sql = " AND ".join(where) if where else "1=1"

    total = db.execute(text(f"SELECT COUNT(*) FROM cases WHERE {where_sql}"), params).scalar() or 0
    order_sql = _build_order(sorts)
    sql = (
        f"SELECT {', '.join('cases.' + c for c in cols)} FROM cases "
        f"WHERE {where_sql} {order_sql}"
    )
    if limit is not None:
        sql += " LIMIT :plim OFFSET :poff"
        params["plim"] = limit
        params["poff"] = offset
    rows = db.execute(text(sql), params).mappings().all()
    return [_parse_row(r) for r in rows], total


def _pick_columns(columns: list[str]) -> list[str]:
    if not columns:
        return list(DEFAULT_COLUMNS)
    return [c for c in columns if c in CASE_FIELD_META]


def _build_order(sorts: list | None) -> str:
    if not sorts:
        return "ORDER BY cases.id"
    parts: list[str] = []
    for s in sorts:
        field = s.field if isinstance(s.field, str) else ""
        if field not in CASE_FIELD_META:
            continue
        parts.append(f"cases.{field} {'DESC' if s.desc else 'ASC'}")
    return ("ORDER BY " + ", ".join(parts)) if parts else "ORDER BY cases.id"


def _parse_row(r) -> dict:
    out = dict(r)
    for k in _JSON_COLS | {"case_no_ext", "dirty_flags", "defendant_raw", "court_raw", "arbitration_org"}:
        if k in out and isinstance(out[k], str):
            try:
                out[k] = json.loads(out[k])
            except (TypeError, ValueError):
                out[k] = None
    return out


# ---------------------------------------------------------------- POST /search

@router.post("/search")
def search_cases_api(payload: SearchRequest, db: Session = Depends(get_db)) -> dict:
    """检索（FTS + 筛选 + 排序 + 分页）。footnote 输出口径 v1.0 声明。"""
    page = max(1, payload.page)
    page_size = min(max(1, payload.page_size), 100)
    rows, total = build_case_query(
        db,
        q=payload.q,
        filters=payload.filters,
        sorts=payload.sorts,
        columns=payload.columns,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return ok(
        rows,
        total=total,
        page=page,
        page_size=page_size,
        footnote="检索口径 v1.0：命中数 = FTS5 与筛选条件的交集行数（支持率/单曲判赔为公式值）",
    )


# ---------------------------------------------------------------- GET /cases/{case_id}

def _resolve_case(db: Session, case_id: str) -> Case:
    q = select(Case)
    if case_id.isdigit():
        q = q.where(Case.id == int(case_id))
    else:
        q = q.where(Case.record_id == case_id)
    case = db.scalar(q)
    if case is None:
        raise HTTPException(status_code=404, detail=f"案件不存在：{case_id}")
    return case


def _case_basic(case: Case) -> dict:
    data: dict = {}
    for meta in CASE_FIELD_META.values():
        if hasattr(case, meta["key"]):
            data[meta["key"]] = getattr(case, meta["key"])
    return _parse_row(data)


def _case_songs(db: Session, case_id: int) -> list[dict]:
    rows = (
        db.execute(
            select(Song.record_id, Song.song_name, Song.artist, SongCase.role)
            .join(SongCase, SongCase.song_id == Song.id)
            .where(SongCase.case_id == case_id)
            .order_by(Song.id)
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def _case_raw(db: Session, record_id: str) -> dict | None:
    raw = db.scalar(select(RawCase).where(RawCase.record_id == record_id, RawCase.table_name == "cases"))
    if raw is None:
        return None
    try:
        payload = json.loads(raw.fields_json)
    except (TypeError, ValueError):
        payload = {}
    return {"record_id": record_id, "fields": payload, "synced_at": raw.synced_at}


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    """案件详情五区：基础 / 关联歌曲 / raw 留档 / audit 摘要 / 系列案树。"""
    case = _resolve_case(db, case_id)
    # 系列案树：父记录 + 兄弟（parent_record_id 指向本记录）+ related_case_no
    siblings = db.scalars(
        select(Case).where(Case.parent_record_id == case.record_id).order_by(Case.id).limit(50)
    ).all()
    audits = db.scalars(
        select(AuditLog).where(AuditLog.record_id == case.record_id).order_by(AuditLog.id.desc()).limit(20)
    ).all()
    data = {
        "base": _case_basic(case),
        "songs": _case_songs(db, case.id),
        "raw": _case_raw(db, case.record_id),
        "audit": [
            {
                "id": a.id, "op_type": a.op_type, "rule_tag": a.rule_tag,
                "rule_version": a.rule_version, "field": a.field,
                "action": a.action, "old_value": a.old_value, "new_value": a.new_value,
                "detail": a.detail, "operator": a.operator, "created_at": a.created_at,
            }
            for a in audits
        ],
        "series": {
            "parent_record_id": case.parent_record_id,
            "related_case_no": case.related_case_no,
            "siblings": [{"record_id": s.record_id, "case_no": s.case_no, "year": s.year, "resolve": s.resolve} for s in siblings],
        },
    }
    return ok(data, footnote="详情口径 v1.0：raw 为飞书原始值整包留档，base 为清洗后规范值")


@router.get("/cases/{case_id}/raw")
def get_case_raw(case_id: str, db: Session = Depends(get_db)) -> dict:
    """原始值整包（原始视图；清洗回放数据源）。"""
    case = _resolve_case(db, case_id)
    raw = _case_raw(db, case.record_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"无原始留档：{case.record_id}")
    return ok(raw)


# ---------------------------------------------------------------- POST /cases/batch

@router.post("/cases/batch")
def batch_cases(payload: CaseBatchRequest, db: Session = Depends(get_db)) -> dict:
    """批量操作：tag（打标签 幂等）| export（导出审计，导出本体走 /export）。"""
    record_ids: list[str] = []
    for cid in payload.ids:
        try:
            case = _resolve_case(db, cid)
        except HTTPException:
            continue
        record_ids.append(case.record_id)
    if not record_ids:
        raise HTTPException(status_code=404, detail="ids 均未命中案件")

    if payload.action == "tag":
        tag_name = (payload.tag or "").strip()
        if not tag_name:
            raise HTTPException(status_code=422, detail="action=tag 时 tag 必填")
        tag = db.scalar(select(Tag).where(Tag.name == tag_name))
        if tag is None:
            tag = Tag(name=tag_name, kind="manual")
            db.add(tag)
            db.flush()
        linked = 0
        for rid in record_ids:
            dup = db.scalar(
                select(TagLink).where(TagLink.tag_id == tag.id, TagLink.target_type == "case", TagLink.target_id == rid)
            )
            if dup is None:
                db.add(TagLink(tag_id=tag.id, target_type="case", target_id=rid))
                linked += 1
        db.commit()
        audit(db, op_type="api", table_name="tag_links", action="tag",
              detail={"tag": tag_name, "ids": record_ids, "linked": linked})
        return ok({"tag": tag_name, "linked": linked, "ids": record_ids})
    # action=export：仅审计（导出文件由 POST /export 生成）
    audit(db, op_type="api", table_name="cases", action="export_batch", detail={"ids": record_ids})
    return ok({"count": len(record_ids), "ids": record_ids})