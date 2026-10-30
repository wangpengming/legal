#!/usr/bin/env python3
# =============================================
# audit_extraction.py - 提取质量只读审计（机读回传）
# 用途：异地测试环境执行，产出 JSON + Markdown 指标，供本机（修复方）诊断。
# 只读：不写业务数据、不改 DB。
# 运行：python3 scripts/audit_extraction.py [--out docs/handoff/artifacts/R1-audit.json]
# 说明：stdlib only（不依赖 pytest / 第三方）。
# =============================================
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
DB_PATH = DATA_DIR / "case_registry.db"
ARTIFACTS_DIR = DATA_DIR / "artifacts"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
try:
    from court_resolver import extract_court_token, resolve_court  # noqa: E402
except Exception:  # noqa: BLE001
    def extract_court_token(_):  # type: ignore
        return ""
    def resolve_court(_):  # type: ignore
        return ""
try:
    from markdown_utils import has_substance  # noqa: E402
except Exception:  # noqa: BLE001
    def has_substance(body_lines):  # type: ignore
        return len("".join(body_lines).strip()) > 0

_SEC_HDR = re.compile(r"(?m)^##\s")


def _empty_section_rate(contents):
    """返回 (小节总数, 近乎空的小节数)。与 importer 的空小节判定同源。"""
    total = empty = 0
    for text in contents:
        parts = _SEC_HDR.split(text or "")
        for p in parts[1:]:
            total += 1
            if not has_substance(p.split("\n")[1:]):
                empty += 1
    return total, empty


def _len_bucket(n):
    if n == 0:
        return "0(空)"
    if n < 200:
        return "<200"
    if n < 1000:
        return "200-1k"
    if n < 5000:
        return "1k-5k"
    return ">=5k"


def collect() -> dict:
    if not DB_PATH.exists():
        return {"ok": False, "error": f"数据库不存在: {DB_PATH}"}

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    rep: dict = {"ok": True, "db_path": str(DB_PATH)}

    # ---- 计数 ----
    counts = {}
    for t in ("cases", "artifacts", "templates"):
        try:
            counts[t] = con.execute(f"select count(*) from {t}").fetchone()[0]
        except sqlite3.Error:
            counts[t] = None
    rep["counts"] = counts

    # ---- cases 字段缺失 ----
    case_cols = ("case_number", "case_name", "plaintiff", "defendant", "cause",
                 "court", "result", "scene", "quality", "year")
    missing = {}
    for col in case_cols:
        try:
            missing[col] = con.execute(
                f"select count(*) from cases where {col} is null or {col}=''"
            ).fetchone()[0]
        except sqlite3.Error:
            missing[col] = None
    rep["case_missing"] = missing
    rep["case_total"] = counts.get("cases") or 0

    # ---- artifacts 长度 + 命名 + 治理字段 ----
    rows = con.execute(
        "select artifact_type, content, generation_method from artifacts"
    ).fetchall()
    lens = defaultdict(list)
    for r in rows:
        lens[r["artifact_type"]].append(len(r["content"] or ""))
    rep["artifact_len"] = {
        t: {"n": len(v), "avg": (sum(v) // len(v)) if v else 0,
            "min": min(v) if v else 0, "max": max(v) if v else 0}
        for t, v in sorted(lens.items())
    }
    rep["artifact_type_distinct"] = sorted(lens.keys())
    rep["artifact_len_buckets"] = dict(Counter(_len_bucket(len(r["content"] or "")) for r in rows))
    rep["generation_method_dist"] = dict(
        Counter(str(r["generation_method"]) for r in rows)
    )

    # ---- 空小节率 ----
    sec_total, sec_empty = _empty_section_rate([r["content"] for r in rows])
    rep["empty_sections"] = {
        "total": sec_total, "empty": sec_empty,
        "rate_pct": (100 * sec_empty // sec_total) if sec_total else 0,
    }

    # ---- 孤儿：文件层 vs DB ----
    case_ids = {r["id"] for r in con.execute("select id from cases")}
    file_dirs = []
    if ARTIFACTS_DIR.exists():
        file_dirs = [d.name for d in ARTIFACTS_DIR.iterdir() if d.is_dir()]
    orphan_dirs = [d for d in file_dirs if d not in case_ids]
    cases_with_files = sum(1 for cid in case_ids if (ARTIFACTS_DIR / cid).is_dir())
    rep["orphans"] = {
        "artifact_dirs": len(file_dirs),
        "orphan_dirs": len(orphan_dirs),
        "orphan_ids": orphan_dirs,
        "cases_with_md_files": cases_with_files,
        "cases_total": len(case_ids),
    }

    # ---- court 代字清单（映射/未映射） ----
    codes = Counter()
    for r in con.execute("select case_number from cases where case_number is not null and case_number!=''"):
        tok = extract_court_token(r["case_number"])
        if tok:
            codes[tok] += 1
    rep["court_tokens"] = {
        tok: {"n": n, "mapped": bool(resolve_court(f"（2024）{tok}民初1号"))}
        for tok, n in codes.most_common()
    }
    rep["court_resolvable_cases"] = sum(1 for r in con.execute(
        "select case_number from cases") if resolve_court(r["case_number"]))

    con.close()
    return rep


def render_md(rep: dict) -> str:
    if not rep.get("ok"):
        return f"❌ 审计失败: {rep.get('error')}"
    L = ["# 提取质量审计报告", "", f"DB: `{rep['db_path']}`", ""]
    c = rep["counts"]
    L.append(f"## 计数\ncases={c.get('cases')} / artifacts={c.get('artifacts')} / templates={c.get('templates')}\n")
    es = rep["empty_sections"]
    L.append(f"## 空小节率\n{es['empty']}/{es['total']} = **{es['rate_pct']}%**\n")
    tot = rep["case_total"] or 1
    L.append("## cases 字段缺失")
    for k, v in rep["case_missing"].items():
        L.append(f"- {k}: {v}/{tot} ({100*(v or 0)//tot}%)")
    L.append("\n## 提取物长度（按类型）")
    for t, s in rep["artifact_len"].items():
        L.append(f"- {t}: n={s['n']} avg={s['avg']} min={s['min']} max={s['max']}")
    L.append(f"\n长度分桶: {rep['artifact_len_buckets']}")
    L.append(f"artifact_type 取值: {rep['artifact_type_distinct']}")
    L.append(f"generation_method: {rep['generation_method_dist']}")
    o = rep["orphans"]
    L.append(f"\n## 孤儿/文件层\n文件目录={o['artifact_dirs']} 孤儿={o['orphan_dirs']} "
             f"有MD的案件={o['cases_with_md_files']}/{o['cases_total']}")
    if o["orphan_ids"]:
        L.append(f"孤儿 case_id: {', '.join(x[:8] for x in o['orphan_ids'])}")
    L.append(f"\n## court 代字（mapped=可从案号派生）")
    for tok, s in rep["court_tokens"].items():
        L.append(f"- {tok}: n={s['n']} mapped={s['mapped']}")
    L.append(f"\ncourt 可派生案件数: {rep['court_resolvable_cases']}/{tot}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="提取质量只读审计")
    ap.add_argument("--out", help="JSON 输出路径（如 docs/handoff/artifacts/R1-audit.json）")
    ap.add_argument("--json", action="store_true", help="stdout 输出 JSON（默认输出 Markdown）")
    args = ap.parse_args()

    rep = collect()
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render_md(rep))


if __name__ == "__main__":
    main()