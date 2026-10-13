#!/usr/bin/env python3
# =============================================
# relink_artifacts.py - 归位"孤儿"提取物（文件层有、DB 无）
# 场景：手工精提炼的提取物写成了 data/artifacts/<case_id>/*.md，但其 case_id
#       不在 cases 表（历史迁移遗留），导致检索/生成/Bot 全链不可见。
# 默认 dry-run：报告孤儿 + 匹配候选；--apply 才写库。
# 匹配分级（宁可漏挂，不可错挂）：
#   exact     case_name 完全一致              → --apply 自动重挂
#   strong    bigram 覆盖率≥0.6 且领先次优≥0.2 → 仅提示，需 --map 确认
#   ambiguous 有候选但证据不足                → 仅提示，需 --map 确认
#   none      无候选                          → 需 --create-missing 才新建
# 写库策略：
#   --apply                        ：重挂 exact 命中的孤儿
#   --map <orphan>=<target>        ：强制把某孤儿重挂到指定案件（可重复）
#   --apply --create-missing       ：对 none 孤儿新建案件（entry_method=manual）
# 运行：python3 scripts/relink_artifacts.py [--apply] [--create-missing] [--map A=B]
# =============================================
import argparse
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
DB_PATH = DATA_DIR / "case_registry.db"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str):
    m = _FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def _collect_orphans(con):
    case_ids = {r[0] for r in con.execute("select id from cases")}
    known_art_ids = {r[0] for r in con.execute("select id from artifacts")}
    orphans = []
    if not ARTIFACTS_DIR.exists():
        return orphans
    for d in sorted(ARTIFACTS_DIR.iterdir()):
        if not d.is_dir() or d.name in case_ids:
            continue
        items = []
        for f in sorted(d.glob("*.md")):
            meta, body = _parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            items.append({
                "file": f.name,
                "artifact_id": meta.get("artifact_id") or str(uuid.uuid4()),
                "artifact_type": meta.get("artifact_type", ""),
                "title": meta.get("title", f.stem),
                "case_name": meta.get("case_name", ""),
                "source_ref": meta.get("source_ref", ""),
                "extracted_at": meta.get("extracted_at", ""),
                "in_db": (meta.get("artifact_id") or "") in known_art_ids,
                "content": body.strip(),
            })
        orphans.append({"case_id": d.name, "items": items})
    return orphans


_CJK = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")
_SUFFIXES = ("权属侵权纠纷案", "信息网络传播权纠纷", "侵权纠纷案", "纠纷案", "案件", "一案", "纠纷", "案")


def _bigrams(name: str) -> set:
    """案件名的字符 bigram 集（仅保留 CJK/字母数字连续段），用于覆盖率匹配。"""
    s = (name or "").strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    grams = set()
    for run in _CJK.findall(s):
        if len(run) == 1:
            grams.add(run)
        for i in range(len(run) - 1):
            grams.add(run[i:i + 2])
    return grams


def _coverage(orphan_grams: set, cand_name: str) -> float:
    """孤儿名 bigram 在候选名中的命中率（非对称覆盖，长候选名不稀释）。"""
    if not orphan_grams:
        return 0.0
    cand = _bigrams(cand_name)
    return len(orphan_grams & cand) / len(orphan_grams)


def _suggest_match(con, case_name: str):
    """按 case_name 精确 / bigram 覆盖率分级匹配已存在案件。"""
    if not case_name:
        return {"mode": "none", "candidates": []}
    row = con.execute("select id, case_name from cases where case_name=?",
                      (case_name,)).fetchone()
    if row:
        return {"mode": "exact", "id": row[0], "case_name": row[1],
                "candidates": [(1.0, row[0], row[1])]}

    og = _bigrams(case_name)
    rows = con.execute("select id, case_name from cases").fetchall()
    scored = sorted(
        ((_coverage(og, n), i, n) for i, n in rows),
        key=lambda x: x[0], reverse=True,
    )
    cands = [(round(c, 3), i, n) for c, i, n in scored[:3] if c > 0]
    if not cands:
        return {"mode": "none", "candidates": []}
    best = cands[0][0]
    second = cands[1][0] if len(cands) > 1 else 0.0
    if best >= 0.6 and (best - second) >= 0.2:
        return {"mode": "strong", "id": cands[0][1], "case_name": cands[0][2],
                "candidates": cands}
    if best >= 0.3:
        return {"mode": "ambiguous", "candidates": cands}
    return {"mode": "none", "candidates": cands}


def _move_orphan_files(orphan_id: str, target_id: str) -> int:
    """把孤儿目录下的 .md 迁到目标案件目录，并改写 frontmatter 的 case_id。"""
    src = ARTIFACTS_DIR / orphan_id
    dst = ARTIFACTS_DIR / target_id
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in sorted(src.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"^case_id:.*$", f"case_id: {target_id}", text, count=1, flags=re.M)
        (dst / f.name).write_text(text, encoding="utf-8")
        f.unlink()
        moved += 1
    try:
        src.rmdir()
    except OSError:
        pass
    return moved


def main():
    ap = argparse.ArgumentParser(description="归位孤儿提取物（文件层→DB）")
    ap.add_argument("--apply", action="store_true", help="实际写库（默认仅预览）")
    ap.add_argument("--create-missing", action="store_true", help="无匹配案件时为孤儿新建")
    ap.add_argument("--map", action="append", default=[], metavar="ORPHAN=TARGET",
                    help="强制把某孤儿重挂到指定案件（可重复）")
    args = ap.parse_args()

    overrides = {}
    for spec in args.map:
        if "=" not in spec:
            ap.error(f"--map 需形如 <orphan>=<target>，收到: {spec}")
        a, b = (x.strip() for x in spec.split("=", 1))
        overrides[a] = b

    con = sqlite3.connect(str(DB_PATH))
    orphans = _collect_orphans(con)
    print(f"孤儿案件目录: {len(orphans)}")
    plan = []
    for o in orphans:
        cname = o["items"][0]["case_name"] if o["items"] else ""
        match = _suggest_match(con, cname)
        plan.append((o, match))
        print(f"\n● {o['case_id'][:8]}  name={cname or '(未知)'}  提取物={len(o['items'])}")
        print(f"  匹配: {match['mode']}   其中已在DB={sum(1 for i in o['items'] if i['in_db'])}")
        for cov, cid, cn in match.get("candidates", []):
            mark = " ←" if match.get("id") == cid else ""
            print(f"    · cov={cov:.2f} {cid[:8]} {cn}{mark}")
        for i in o["items"]:
            print(f"    - [{i['artifact_type']:16s}] {i['title']} ({len(i['content'])}字)")

    if not args.apply:
        print("\n（dry-run；--apply 写入；ambiguous 用 --map 指定；none 用 --create-missing）")
        con.close()
        return

    written = 0
    for o, match in plan:
        oid = o["case_id"]
        target = overrides.get(oid) or overrides.get(oid[:8])
        if target:
            row = con.execute("select id from cases where id=?", (target,)).fetchone()
            if not row:
                print(f"跳过 {oid[:8]}（--map 目标不存在: {target}）")
                continue
        elif match["mode"] == "exact":
            target = match["id"]
        else:
            if match["mode"] in ("strong", "ambiguous"):
                print(f"跳过 {oid[:8]}（{match['mode']}：需 --map 确认，避免错挂）")
                continue
            elif args.create_missing:
                cname = o["items"][0]["case_name"] if o["items"] else f"孤儿案件-{oid[:8]}"
                target = str(uuid.uuid4())
                con.execute(
                    "insert into cases (id, case_name, status, entry_method, created_at) "
                    "values (?, ?, 'extracted', 'manual', datetime('now'))",
                    (target, cname),
                )
                print(f"新建案件 {target[:8]} name={cname}")
            else:
                print(f"跳过 {oid[:8]}（无匹配案件，未指定 --create-missing）")
                continue
        for i in o["items"]:
            if i["in_db"]:
                continue
            con.execute(
                "insert into artifacts (id, case_id, artifact_type, title, content, "
                "source_ref, version, created_at, generation_method) "
                "values (?, ?, ?, ?, ?, ?, 1, ?, 'manual')",
                (i["artifact_id"], target, i["artifact_type"] or "note", i["title"],
                 i["content"], i["source_ref"], i["extracted_at"] or "2026-09-22T00:00:00+00:00"),
            )
            written += 1
        moved = _move_orphan_files(oid, target)
        if moved:
            print(f"文件层已迁移 {moved} 个 → {target[:8]}/")
    con.commit()
    print(f"✅ 写入提取物 {written} 条")
    con.close()


if __name__ == "__main__":
    main()