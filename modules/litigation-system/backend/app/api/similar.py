"""同质案类推端点（docs/02 §6.2 / 需求 F4.2：同质案件类推）。

相似度权重（F4.2）：案由 40% + 业务线 20% + 结案原因 15% + 标的区间 10%
+ 对手方 10% + 办案笔记关键词 5%；对候选案件（任一维度与目标重叠）计算加权
得分，输出 Top10 相似案 + 风险提示卡（结案原因分布 / 判赔区间 P25~P75 /
笔记要点 Top3）。数据量维持千级，Python 层全量计算无性能问题。
"""
from __future__ import annotations

import json
import statistics
from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.search import _case_basic, _resolve_case
from app.api.schemas import ok
from app.core.database import get_db
from app.models.fact import Case

router = APIRouter(tags=["similar"])

_W_CAUSE = 0.40
_W_BIZ = 0.20
_W_RESOLVE = 0.15
_W_AMOUNT = 0.10
_W_PARTY = 0.10
_W_NOTES = 0.05

_TOP_N = 10


def _amount_bucket(amount: float | None) -> str:
    """标的区间分桶（F4.2 标的区间相似）。"""
    if amount is None:
        return "无"
    if amount < 10_000:
        return "1万以下"
    if amount < 50_000:
        return "1万~5万"
    if amount < 100_000:
        return "5万~10万"
    return "10万以上"


def _defendants(case: Case) -> list[str]:
    try:
        raw = json.loads(case.defendant) if isinstance(case.defendant, str) else case.defendant
        return [d for d in (raw or []) if isinstance(d, str)]
    except (TypeError, ValueError):
        return []


def _notes_keywords(notes: str | None, top: int = 3) -> list[str]:
    """笔记要点 Top3：中文二元组合词频（简单去停用词）。"""
    if not notes:
        return []
    stops = {"以及", "一个", "本案", "该案", "案件", "相关", "进行", "已经", "没有", "通过",
             "作为", "根据", "对于", "其中", "以及", "等"}
    words = [notes[i - 1] + notes[i] for i in range(1, len(notes)) if notes[i - 1].strip() and notes[i].strip()]
    counter = Counter(w for w in words if w not in stops and not w[0].isdigit())
    return [w for w, _ in counter.most_common(top)]


def _bigram_set(text: str | None) -> set[str]:
    if not text:
        return set()
    return {text[i - 1] + text[i] for i in range(1, len(text)) if text[i - 1].strip() and text[i].strip()}


class SimilarRequest(BaseModel):
    case_id: str


@router.post("/similar")
def similar_cases(payload: SimilarRequest, db: Session = Depends(get_db)) -> dict:
    """给定案件 → Top10 相似案 + 风险提示卡（F4.2 权重算法）。"""
    target = _resolve_case(db, payload.case_id)
    target_def = set(_defendants(target))
    target_notes = _bigram_set(target.notes)

    candidates = db.scalars(
        select(Case).where(Case.id != target.id, Case.record_id != target.record_id)
    ).all()

    scored: list[tuple[float, Case]] = []
    for c in candidates:
        score = 0.0
        hits = 0
        if target.cause and c.cause == target.cause:
            score += _W_CAUSE
            hits += 1
        if target.biz_line and c.biz_line == target.biz_line:
            score += _W_BIZ
            hits += 1
        if target.resolve and c.resolve == target.resolve:
            score += _W_RESOLVE
            hits += 1
        if _amount_bucket(c.amount) == _amount_bucket(target.amount):
            score += _W_AMOUNT
            hits += 1
        if target_def and set(_defendants(c)) & target_def:
            score += _W_PARTY
            hits += 1
        if target_notes and c.notes:
            shared = len(target_notes & _bigram_set(c.notes))
            if shared > 0:
                score += _W_NOTES * min(1.0, shared / max(1, len(target_notes)))
                hits += 1
        if hits == 0:
            continue
        scored.append((round(score * 100, 1), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_TOP_N]
    items = []
    resolve_dist: Counter = Counter()
    pay_amounts: list[float] = []
    for score, c in top:
        base = _case_basic(c)
        items.append({
            "record_id": base.get("record_id"),
            "case_no": base.get("case_no"),
            "cause": base.get("cause"),
            "resolve": base.get("resolve"),
            "biz_line": base.get("biz_line"),
            "amount": base.get("amount"),
            "pay_amount": base.get("pay_amount"),
            "defendant": _defendants(c),
            "similarity": score,
            "notes": c.notes,
        })
        if c.resolve:
            resolve_dist[c.resolve] += 1
        if isinstance(c.pay_amount, (int, float)):
            pay_amounts.append(float(c.pay_amount))

    pay_range = {}
    if pay_amounts:
        pay_range = {
            "n": len(pay_amounts),
            "p25": round(statistics.quantiles(pay_amounts, n=4)[0], 2),
            "p50": round(statistics.median(pay_amounts), 2),
            "p75": round(statistics.quantiles(pay_amounts, n=4)[2], 2),
        }

    # 相似案共享笔记要点（Top3 合并统计）
    note_pool = "".join(c.notes or "" for _, c in top)
    note_points = _notes_keywords(note_pool or None)

    return ok(
        {
            "target": {
                k: _case_basic(target).get(k)
                for k in ("record_id", "case_no", "cause", "resolve", "biz_line",
                          "amount", "pay_amount", "defendant", "case_status")
            },
            "items": items,
            "risk": {
                "resolve_dist": [{"resolve": k, "count": v} for k, v in resolve_dist.most_common()],
                "pay_range": pay_range,
                "note_points": note_points,
            },
            "weights": {
                "cause": _W_CAUSE, "biz_line": _W_BIZ, "resolve": _W_RESOLVE,
                "amount": _W_AMOUNT, "party": _W_PARTY, "notes": _W_NOTES,
            },
        },
        total=len(scored),
        footnote=(
            "相似度权重（F4.2）：案由 40% / 业务线 20% / 结案原因 15% / 标的区间 10% / "
            "对手方 10% / 办案笔记关键词 5%；候选 = 至少一维与目标重叠的案件",
        ),
    )