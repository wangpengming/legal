#!/usr/bin/env python3
# =============================================
# backfill_cases.py - 回填 cases 派生字段（court / year / scene / quality）
# 默认 dry-run：只打印将变更的行；显式 --apply 才写库。
# 只写 court / year / scene / quality 四列，不改其他字段。
# quality 由 D1-D5 artifact 覆盖度派生（与 src/extractor.derive_quality 同口径）。
# 无法从现有数据派生的字段（如真实 scene/result）会统计出来，供异地回传补录。
# 运行：python3 scripts/backfill_cases.py [--apply]
# =============================================
import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
DB_PATH = DATA_DIR / "case_registry.db"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from court_resolver import resolve_court, year_from_case_number  # noqa: E402
from database import DIMENSION_ARTIFACT_TYPES  # noqa: E402

_DIM_TYPES = set(DIMENSION_ARTIFACT_TYPES.values())


def _dims_covered(con, case_id: str) -> int:
    """该案 D1-D5 中有实质内容（content 非空）的 artifact_type 数。"""
    types = {
        r[0]
        for r in con.execute(
            "select artifact_type from artifacts "
            "where case_id=? and coalesce(content,'')<>''",
            (case_id,),
        )
    }
    return len(types & _DIM_TYPES)


def _quality_from_dims(filled: int, case_number: str) -> str:
    """与 extractor.derive_quality 同口径：A=5 维全，B=≥3 维或案号已识别，C=其余。"""
    if filled >= 5:
        return "A"
    if filled >= 3 or (case_number or "").strip():
        return "B"
    return "C"

_SCENE_RULES = [
    ("车载KTV", ("车载", "车机", "汽车KTV")),
    ("线上平台", ("线上", "网站", "APP", "app", "小程序", "网络平台")),
    ("实体KTV", ("KTV", "ktv", "歌房", "包厢")),
    ("实体场所", ("门店", "商场", "酒吧", "酒店")),
]


def _scene(case_name: str) -> str:
    for scene, keys in _SCENE_RULES:
        if any(k in (case_name or "") for k in keys):
            return scene
    return ""


def main():
    ap = argparse.ArgumentParser(description="回填 court / year / scene")
    ap.add_argument("--apply", action="store_true", help="实际写库（默认仅预览）")
    args = ap.parse_args()

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, case_number, case_name, court, year, scene, quality from cases"
    ).fetchall()

    # 非破坏回填：仅在列为空（NULL/''）时写入派生值；已有值一律不覆盖（宁缺毋滥）。
    # 派生值与已有值不一致者单列「差异」供人工核对，不自动改写。
    updates = []          # (id, court, year, scene, case_number)
    quality_updates = []  # (id, quality, case_number)
    diffs = []            # (id, case_number, field, existing, derived)
    for r in rows:
        court = resolve_court(r["case_number"])
        year = year_from_case_number(r["case_number"])
        scene = _scene(r["case_name"])

        filled = []
        if court and not (r["court"] or "").strip():
            filled.append("court")
        if year and not (r["year"] or None):
            filled.append("year")
        if scene and not (r["scene"] or "").strip():
            filled.append("scene")
        if filled:
            updates.append((r["id"],
                            court or r["court"],
                            year or r["year"],
                            scene or r["scene"],
                            r["case_number"],
                            "+".join(filled)))

        # 差异（已有非空但 != 派生）→ 仅报告
        if court and (r["court"] or "").strip() and (r["court"] or "") != court:
            diffs.append((r["id"], r["case_number"], "court", r["court"], court))
        if year and (r["year"] or None) and (r["year"] or None) != year:
            diffs.append((r["id"], r["case_number"], "year", r["year"], year))
        if scene and (r["scene"] or "").strip() and (r["scene"] or "") != scene:
            diffs.append((r["id"], r["case_number"], "scene", r["scene"], scene))

        if not (r["quality"] or "").strip():
            quality_updates.append((r["id"],
                                    _quality_from_dims(_dims_covered(con, r["id"]), r["case_number"]),
                                    r["case_number"]))

    resolvable = sum(1 for r in rows if resolve_court(r["case_number"]))
    scene_derivable = sum(1 for r in rows if _scene(r["case_name"]))
    print(f"案件总数: {len(rows)} | court 可派生: {resolvable} | scene 可派生: {scene_derivable} | 待填空行: {len(updates)}")
    for cid, court, year, scene, cn, need in updates[:20]:
        print(f"  {cid[:8]}  {cn or '(空)':30s} [{need}] → court={court or '(空)'} year={year} scene={scene or '(空)'}")
    if len(updates) > 20:
        print(f"  … 其余 {len(updates) - 20} 行")

    from collections import Counter
    qdist = Counter(q for _, q, _ in quality_updates)
    print(f"quality 待回填: {len(quality_updates)} 行 | 分布 {dict(sorted(qdist.items()))}")
    for cid, q, cn in quality_updates[:10]:
        print(f"  {cid[:8]}  {cn or '(空)':30s} quality={q}")
    if len(quality_updates) > 10:
        print(f"  … 其余 {len(quality_updates) - 10} 行")

    print(f"差异（已有值≠派生值，不自动改写，供人工核对）: {len(diffs)} 处")
    for cid, cn, field, old, new in diffs[:20]:
        print(f"  {cid[:8]}  {cn or '(空)':30s} {field}: 现有={old!r} ≠ 派生={new!r}")
    if len(diffs) > 20:
        print(f"  … 其余 {len(diffs) - 20} 处")

    if args.apply:
        for cid, court, year, scene, _, _ in updates:
            con.execute("update cases set court=?, year=?, scene=? where id=?",
                        (court, year, scene, cid))
        for cid, q, _ in quality_updates:
            con.execute("update cases set quality=? where id=?", (q, cid))
        con.commit()
        print(f"✅ 已填空 court/year/scene {len(updates)} 行 + quality {len(quality_updates)} 行（差异 {len(diffs)} 处未改写）")
    else:
        print("（dry-run；加 --apply 实际写入）")
    con.close()


if __name__ == "__main__":
    main()