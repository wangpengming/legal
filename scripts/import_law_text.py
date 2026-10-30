#!/usr/bin/env python3
# =============================================
# import_law_text.py - 把法条文本（TXT/MD）切条导入本地法律知识库
#
# 用途：用户提供法规原文后，按「第N条」切条写入 `knowledge/legal/<name>.md`
#   （格式见 knowledge/legal/README.md，检索见 src/legal_kb.py）。
# 🔴 不臆造法条原文：只做切分与落盘，正文原样保留。
# 幂等：同条号覆盖，重复导入不产生重复条目。
#
# 运行：
#   python3 scripts/import_law_text.py --in 著作权法.txt --topic 著作权法            # 预览
#   python3 scripts/import_law_text.py --in 著作权法.txt --topic 著作权法 --write   # 写入
# 说明：stdlib only。
# =============================================
import argparse
import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "knowledge" / "legal"

_ART_SPLIT_RE = re.compile(r"(第\s*[0-9〇零一二三四五六七八九十百千]+\s*条)")
_HEAD_RE = re.compile(r"^#{2,4}\s+(?P<title>.+?)\s*$", re.M)


def split_articles(text: str) -> list:
    """按「第N条」切条 → [(条号, 正文)]；无条号则整体作为一条（"" 作标题）。"""
    body = (text or "").strip()
    if not body:
        return []
    parts = _ART_SPLIT_RE.split(body)
    out = []
    if parts and parts[0].strip():                      # 条号前的序言（如法规标题）
        out.append(("", parts[0].strip()))
    for i in range(1, len(parts), 2):
        art = re.sub(r"\s+", "", parts[i])
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        out.append((art, content))
    return out


def _slug(topic: str, name: str = "") -> str:
    """文件名：优先显式 --name；拉丁主题名直接用；中文主题名 → law-<sha1 前 8 位>。"""
    if name:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "law"
    s = re.sub(r"[^A-Za-z0-9]+", "-", topic or "").strip("-").lower()
    if s:
        return s
    return "law-" + hashlib.sha1((topic or "").encode("utf-8")).hexdigest()[:8]


def _read_existing(path: Path) -> dict:
    """读已有文件 → {条号: 正文}（便于同条号覆盖）。"""
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8", errors="replace")
    heads = list(_HEAD_RE.finditer(raw))
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
        out[h.group("title").strip()] = raw[h.end():end].strip()
    return out


def write_topic(topic: str, items: list, out_dir=None, name: str = "") -> Path:
    """把 (条号, 正文) 合入 knowledge/legal/<slug>.md（同条号覆盖），返回文件路径。"""
    d = Path(out_dir or DEFAULT_OUT)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_slug(topic, name)}.md"
    merged = _read_existing(path)
    for art, content in items:
        title = f"{topic} {art}".strip() if art else (topic or path.stem)
        merged[title] = content
    lines = ["---", f"topic: {topic}", "---", ""]
    for title in sorted(merged):
        lines += [f"### {title}", merged[title], ""]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="导入法条文本到本地法律知识库")
    ap.add_argument("--in", dest="src", required=True, help="源文件（TXT/MD）")
    ap.add_argument("--topic", required=True, help="法规主题名（如 著作权法）")
    ap.add_argument("--name", default="", help="输出文件名（英文，缺省自动生成）")
    ap.add_argument("--out", default="", help="输出目录（缺省 knowledge/legal）")
    ap.add_argument("--write", action="store_true", help="真正写入（缺省仅预览）")
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.is_file():
        print(f"❌ 源文件不存在: {src}")
        return 2
    items = split_articles(src.read_text(encoding="utf-8", errors="replace"))
    if not items:
        print("❌ 未解析出任何内容")
        return 2
    print(f"解析到 {len(items)} 条（主题：{args.topic}）：")
    for art, content in items:
        print(f"  · {art or '（序言）'}　{content[:40]}…")
    if not args.write:
        print("\n（预览模式，未写入；加 --write 落盘）")
        return 0
    path = write_topic(args.topic, items, out_dir=args.out or None, name=args.name)
    print(f"\n✅ 已写入 {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())