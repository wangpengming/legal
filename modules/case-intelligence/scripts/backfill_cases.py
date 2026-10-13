#!/usr/bin/env python3
# =============================================
# backfill_cases.py - 回填 cases 派生字段（court / year / scene）
# 默认 dry-run：只打印将变更的行；显式 --apply 才写库。
# 只写 court / year / scene 三列，不改其他字段。
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
        "select id, case_number, case_name, court, year, scene from cases"
    ).fetchall()

    updates = []
    for r in rows:
        court = resolve_court(r["case_number"])
        year = year_from_case_number(r["case_number"])
        scene = _scene(r["case_name"])
        new_court, new_year, new_scene = r["court"], r["year"], r["scene"]
        need = []
        if court and (r["court"] or "") != court:
            new_court = court
            need.append("court")
        if year and (r["year"] or None) != year:
            new_year = year
            need.append("year")
        if scene and (r["scene"] or "") != scene:
            new_scene = scene
            need.append("scene")
        if need:
            updates.append((r["id"], new_court, new_year, new_scene, r["case_number"], "+".join(need)))

    resolvable = sum(1 for r in rows if resolve_court(r["case_number"]))
    scene_derivable = sum(1 for r in rows if _scene(r["case_name"]))
    print(f"案件总数: {len(rows)} | court 可派生: {resolvable} | scene 可派生: {scene_derivable} | 待更新行: {len(updates)}")
    for cid, court, year, scene, cn, need in updates[:20]:
        print(f"  {cid[:8]}  {cn or '(空)':30s} [{need}] → court={court or '(空)'} year={year} scene={scene or '(空)'}")
    if len(updates) > 20:
        print(f"  … 其余 {len(updates) - 20} 行")

    if args.apply:
        for cid, court, year, scene, _, _ in updates:
            con.execute(
                "update cases set court=?, year=?, scene=? where id=?",
                (court, year, scene, cid),
            )
        con.commit()
        print(f"✅ 已写入 {len(updates)} 行")
    else:
        print("（dry-run；加 --apply 实际写入）")
    con.close()


if __name__ == "__main__":
    main()