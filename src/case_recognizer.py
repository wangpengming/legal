# =============================================
# case_recognizer.py - 案件识别器
# 通过案号 / 当事人指纹 判断新案件是否与已有案件重复
# =============================================
import re
import sqlite3
from pathlib import Path
from typing import Optional

from .database import get_case_by_number, search_cases, _get_conn


def normalize_case_number(case_number: str) -> str:
    """标准化案号（去空格/全角转半角/统一括号）。"""
    s = case_number.strip()
    # 全角转半角
    s = s.translate(str.maketrans("（）", "()"))
    # 去所有空格
    s = re.sub(r"\s+", "", s)
    return s


def extract_parties_key(plaintiff: str, defendant: str) -> str:
    """生成当事人指纹 key（排序后拼接）。"""
    a = sorted([plaintiff.strip(), defendant.strip()])
    return "|".join(a)


def check_case_number(
    case_number: str,
    db_path: Optional[Path] = None,
) -> dict:
    """检查案号是否已存在，返回匹配结果。"""
    normalized = normalize_case_number(case_number)
    existing = get_case_by_number(normalized, db_path)
    if existing:
        return {
            "match": True,
            "type": "case_number",
            "case_id": existing["id"],
            "case_name": existing["case_name"],
            "case_number": existing["case_number"],
            "status": existing["status"],
            "confidence": 1.0,
        }
    return {
        "match": False,
        "type": "case_number",
        "case_number": normalized,
    }


def check_parties_fuzzy(
    plaintiff: str,
    defendant: str,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """模糊匹配当事人组合（可能的多案由同一方）。"""
    conn = _get_conn(db_path)
    key = extract_parties_key(plaintiff, defendant)
    candidates = search_cases(plaintiff, db_path) + search_cases(defendant, db_path)
    results = []
    seen = set()
    for c in candidates:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        p_key = extract_parties_key(c["plaintiff"] or "", c["defendant"] or "")
        if p_key == key:
            results.append(
                {
                    "case_id": c["id"],
                    "case_name": c["case_name"],
                    "case_number": c["case_number"],
                    "cause": c["cause"],
                    "status": c["status"],
                    "match_type": "exact_parties",
                    "confidence": 0.9,
                }
            )
    return results


def check_cause_fuzzy(
    cause: str,
    plaintiff: str = "",
    db_path: Optional[Path] = None,
) -> list[dict]:
    """按案由关键词模糊匹配。"""
    if not cause:
        return []
    conn = _get_conn(db_path)
    q = f"%{cause}%"
    rows = conn.execute(
        """
        SELECT id, case_name, case_number, cause, plaintiff, defendant, status
        FROM cases
        WHERE cause LIKE ? OR case_name LIKE ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (q, q),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        confidence = 0.7
        if plaintiff and r["plaintiff"] and plaintiff in r["plaintiff"]:
            confidence = 0.8
        results.append(
            {
                "case_id": r["id"],
                "case_name": r["case_name"],
                "case_number": r["case_number"],
                "cause": r["cause"],
                "status": r["status"],
                "match_type": "cause",
                "confidence": confidence,
            }
        )
    return results


def recognize_case(
    case_number: Optional[str] = None,
    plaintiff: str = "",
    defendant: str = "",
    cause: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """综合识别：先案号精确 → 当事人精确 → 案由模糊。"""
    results = {"exact": None, "partial": [], "cause_fuzzy": []}

    # Step 1: 案号精确匹配
    if case_number:
        r = check_case_number(case_number, db_path)
        if r["match"]:
            results["exact"] = r
            return results

    # Step 2: 当事人精确匹配
    if plaintiff or defendant:
        partial = check_parties_fuzzy(plaintiff, defendant, db_path)
        results["partial"] = partial

    # Step 3: 案由模糊匹配（仅在无精确匹配时）
    if not results["exact"] and cause:
        results["cause_fuzzy"] = check_cause_fuzzy(cause, plaintiff, db_path)

    return results
