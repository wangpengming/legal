#!/usr/bin/env python3
# =============================================
# legal_kb.py - 本地法律知识层（法条 / 裁判要点；纯 stdlib、离线可用）
#
# 定位：Bot 需要**具体法条**时，先查本地库（不外传，守「本地优先」红线）；
#   未命中再由调用方回落联网检索（lark_websearch）。
#
# 语料格式（knowledge/legal/<name>.md）：
#   ---
#   topic: 著作权法
#   ---
#   ### 著作权法 第10条
#   著作权包括下列人身权和财产权……
#
# 🔴 红线：**不臆造法条原文**。语料由用户提供 / 确认后经
#   `scripts/import_law_text.py` 导入；空库时如实回「本地库暂无该条目」。
#
# 见 docs/SPEC-feishu-bot.md §5.6。
# =============================================
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "legal"
MAX_TEXT = 1200                       # 单条正文截断（防卡片 / 上下文爆炸）

_FRONT_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---\s*\n", re.S)
_TOPIC_RE = re.compile(r"^topic\s*[:：]\s*(?P<topic>.+)$", re.M)
_HEAD_RE = re.compile(r"^#{2,4}\s+(?P<title>.+?)\s*$", re.M)
_ART_NO_RE = re.compile(r"第\s*[0-9〇零一二三四五六七八九十百千]+\s*条")

_CACHE: dict = {}                     # dir → (signature, articles)


@dataclass(frozen=True)
class Article:
    topic: str
    article: str
    text: str
    source: str = ""


def dir_path(path=None) -> Path:
    """知识库目录：显式参数 > env LEGAL_KB_DIR > 模块默认 knowledge/legal。"""
    return Path(path or os.environ.get("LEGAL_KB_DIR") or DEFAULT_DIR)


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…（已截断）"


def _parse_file(f: Path) -> list[Article]:
    raw = f.read_text(encoding="utf-8", errors="replace")
    topic = f.stem
    m = _FRONT_RE.match(raw)
    if m:
        t = _TOPIC_RE.search(m.group("body"))
        if t:
            topic = t.group("topic").strip()
        raw = raw[m.end():]
    heads = list(_HEAD_RE.finditer(raw))
    if not heads:
        body = _clip(raw)
        return [Article(topic, topic, body, str(f))] if body else []
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
        body = _clip(raw[h.end():end])
        out.append(Article(topic, h.group("title").strip(), body, str(f)))
    return out


def _signature(d: Path) -> tuple:
    if not d.is_dir():
        return ()
    return tuple(
        (f.name, f.stat().st_mtime_ns, f.stat().st_size)
        for f in sorted(d.glob("*.md")) if f.name.lower() != "readme.md"
    )


def load(path=None) -> list[Article]:
    """解析知识库目录下所有 .md（跳过 README）→ Article 列表；无目录 / 无文件 → []。

    按目录签名（文件名 + mtime + 大小）缓存，语料变更自动失效。
    """
    d = dir_path(path)
    sig = _signature(d)
    cached = _CACHE.get(str(d))
    if cached and cached[0] == sig:
        return cached[1]
    articles: list[Article] = []
    if sig:
        for f in sorted(d.glob("*.md")):
            if f.name.lower() == "readme.md":
                continue
            articles.extend(_parse_file(f))
    _CACHE[str(d)] = (sig, articles)
    return articles


def _terms(query: str) -> tuple:
    """查询 → (条号集合, 关键词集合)。中文取原文 + 2/3/4 字滑窗，兼顾召回与精度。"""
    q = (query or "").strip()
    arts = {re.sub(r"\s+", "", m.group(0)) for m in _ART_NO_RE.finditer(q)}
    kws = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", q):
        kws.add(run)
        for n in (2, 3, 4):
            for i in range(len(run) - n + 1):
                kws.add(run[i:i + n])
    for w in re.findall(r"[A-Za-z0-9]{2,}", q):
        kws.add(w.lower())
    return arts, kws


def _score(article: Article, arts: set, kws: set) -> int:
    head = article.article.replace(" ", "")
    hay = f"{article.article} {article.text}".lower()
    score = 0
    for art in arts:                                   # 条号命中权重最高
        if art in head:
            score += 8
        elif art in hay:
            score += 4
    for kw in kws:
        if kw.lower() in hay:
            score += 2 if len(kw) >= 3 else 1
    return score


def search(query: str, limit: int = 5, path=None) -> list[Article]:
    """关键词 / 条号检索 → Top-N（按分降序；同分按条号排序，保证确定性）。"""
    arts, kws = _terms(query)
    if not arts and not kws:
        return []
    scored = [(s, a) for s, a in ((_score(a, arts, kws), a) for a in load(path)) if s > 0]
    scored.sort(key=lambda p: (-p[0], p[1].article))
    return [a for _s, a in scored[:limit]]


def lookup(query: str, limit: int = 5, path=None) -> dict:
    """检索结果结构体：{query, hits:[{topic, article, text}], source("local"|"")}。"""
    hits = search(query, limit=limit, path=path)
    return {
        "query": (query or "").strip(),
        "hits": [{"topic": a.topic, "article": a.article, "text": a.text} for a in hits],
        "source": "local" if hits else "",
    }


__all__ = ["Article", "DEFAULT_DIR", "dir_path", "load", "search", "lookup"]