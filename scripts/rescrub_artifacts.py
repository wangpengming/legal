#!/usr/bin/env python3
# =============================================
# rescrub_artifacts.py - 存量提取物"空壳小节"回洗
# 背景：批量 AI 提取的存量提取物含大量"只有标题、没有内容"的小节（实测空小节率
#       ~49%），下游文书生成取不到料。本脚本对 DB 中已有提取物套用
#       markdown_utils.strip_empty_sections（宁缺毋滥：无实质内容的小节整节删除），
#       并顺带回填治理字段 generation_method（NULL → ai，存量均为批量 AI 提取）。
# 默认 dry-run：报告将变更的行；显式 --apply 才写库。
# 文件层：若 data/artifacts/<case_id>/<id8>_<title>.md 存在，同步刷新其正文。
# 运行：python3 scripts/rescrub_artifacts.py [--apply]
# =============================================
import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
DB_PATH = DATA_DIR / "case_registry.db"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from markdown_utils import strip_empty_sections  # noqa: E402

_LEGACY_GEN_METHOD = "ai"


def _sync_file(case_id: str, artifact_id: str, title: str, new_content: str) -> bool:
    """若文件层存在该提取物，刷新其正文（保留 frontmatter）。"""
    d = ARTIFACTS_DIR / (case_id or "")
    if not d.is_dir():
        return False
    for f in d.glob("*.md"):
        if f.name.startswith(artifact_id[:8]):
            text = f.read_text(encoding="utf-8", errors="replace")
            fm_end = text.find("\n---", 3)
            if fm_end == -1:
                return False
            head = text[: fm_end + 4]
            f.write_text(f"{head}\n\n{new_content}\n", encoding="utf-8")
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="存量提取物空壳小节回洗")
    ap.add_argument("--apply", action="store_true", help="实际写库（默认仅预览）")
    args = ap.parse_args()

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, case_id, title, content, generation_method from artifacts"
    ).fetchall()

    scrubbed = 0
    gen_filled = 0
    file_synced = 0
    samples = []
    for r in rows:
        old = r["content"] or ""
        new = strip_empty_sections(old)
        changed = new != old
        if changed:
            scrubbed += 1
            if len(samples) < 10:
                samples.append((r["id"][:8], r["title"], len(old), len(new)))
        need_gen = not r["generation_method"]
        if need_gen:
            gen_filled += 1
        if args.apply and (changed or need_gen):
            if changed:
                con.execute("update artifacts set content=? where id=?", (new, r["id"]))
                if _sync_file(r["case_id"], r["id"], r["title"], new):
                    file_synced += 1
            if need_gen:
                con.execute("update artifacts set generation_method=? where id=?",
                            (_LEGACY_GEN_METHOD, r["id"]))

    total = len(rows)
    print(f"提取物总数: {total}")
    print(f"将被回洗（含空壳）: {scrubbed} | generation_method 待回填: {gen_filled}")
    for aid, title, lo, ln in samples:
        print(f"  {aid} {title}: {lo}字 → {ln}字")
    if scrubbed > 10:
        print(f"  … 其余 {scrubbed - 10} 条")

    if args.apply:
        con.commit()
        print(f"✅ 已回洗 {scrubbed} 条；回填 generation_method {gen_filled} 条；文件层同步 {file_synced} 个")
    else:
        print("（dry-run；加 --apply 实际写入）")
    con.close()


if __name__ == "__main__":
    main()