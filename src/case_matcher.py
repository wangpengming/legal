# =============================================
# case_matcher.py - 相似案件匹配
# 规则打分（无向量检索，见 SPEC-feature-completion §4.2）：
#   案由 40 / D1–D5 覆盖 30 / 年份 15 / 场景 15，封顶 100
# =============================================
from pathlib import Path
from typing import Optional

from . import database as db

# D1–D5 语义提取物类型（唯一真值来自 database）
CORE_TYPES = set(db.DIMENSION_ARTIFACT_TYPES.values())


def _to_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _artifact_types(case_id: str, db_path: Optional[Path]) -> set:
    return {a["artifact_type"] for a in db.list_artifacts_by_case(case_id, db_path)} & CORE_TYPES


def _score(target: dict, target_types: set, cand: dict, db_path: Optional[Path]):
    """返回 (score, reasons)。"""
    reasons = []
    score = 0

    tc = (target.get("cause") or "").strip()
    cc = (cand.get("cause") or "").strip()
    if tc and cc:
        if tc == cc:
            score += 40
            reasons.append(f"案由一致：{tc}")
        elif tc in cc or cc in tc:
            score += 20
            reasons.append(f"案由相近：{tc} ≈ {cc}")

    ty, cy = _to_int(target.get("year")), _to_int(cand.get("year"))
    if ty and cy:
        diff = abs(ty - cy)
        if diff == 0:
            score += 15
            reasons.append(f"同年份：{ty}")
        elif diff <= 1:
            score += 10
            reasons.append(f"年份邻近：{ty} / {cy}")
        elif diff <= 2:
            score += 5
            reasons.append(f"年份较近：{ty} / {cy}")

    ts = (target.get("scene") or "").strip()
    cs = (cand.get("scene") or "").strip()
    if ts and cs and ts == cs:
        score += 15
        reasons.append(f"场景一致：{ts}")

    if target_types:
        overlap = target_types & _artifact_types(cand["id"], db_path)
        if overlap:
            score += int(30 * len(overlap) / len(target_types))
            reasons.append(f"D 维度重合 {len(overlap)}/{len(target_types)}")

    return min(score, 100), reasons


def match_cases(
    case_id: str, limit: int = 5, db_path: Optional[Path] = None
) -> list[dict]:
    """返回与 case_id 最相似的 Top-N 案件（含 score / reasons）。"""
    target = db.get_case(case_id, db_path)
    if not target:
        return []
    target_types = _artifact_types(case_id, db_path)
    scored = []
    for cand in db.list_cases(db_path=db_path):
        if cand["id"] == case_id:
            continue
        score, reasons = _score(target, target_types, cand, db_path)
        if score > 0:
            scored.append({**cand, "score": score, "reasons": reasons})
    scored.sort(key=lambda x: (x["score"], x.get("created_at") or ""), reverse=True)
    return scored[:limit]