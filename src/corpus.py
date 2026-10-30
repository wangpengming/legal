#!/usr/bin/env python3
# =============================================
# corpus.py - 本地案例语料检索（案例库的「知识层」）
#
# 定位：让**本地案例数据**成为智能体的主要知识来源——
#   用户问「这类案子一般判多少钱」「有没有类似的判决」「法条怎么规定的」时，
#   先在 167 件案件 + 838 份提取物正文里找**有出处的证据**，再作答。
#
# 原则：
#   · 纯 stdlib + SQL LIKE，无外部依赖、无网络
#   · 返回**带出处**的片段（案件名 / 案号 / 提取物维度 / 原文摘录）
#   · 命中为空即返回空——**不臆造**（上层据此如实告知「本地无据」）
#
# 见 docs/SPEC-feishu-bot.md §5.6。
# =============================================
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from . import database as db

# 领域词表：法律概念优先命中（精度高），避免把整句当检索词
LEXICON = (
    "惩罚性赔偿", "法定赔偿", "赔偿标准", "赔偿数额", "损害赔偿", "停止侵害", "赔偿",
    "信息网络传播权", "著作权", "侵权", "作品", "合理使用", "授权", "独家", "许可",
    "复制权", "传播权", "表演权", "发行权", "信息网络权", "举证", "举证责任", "证据",
    "诉讼时效", "管辖", "法院", "判决", "裁判", "抗辩", "答辩", "争议焦点", "侵权行为",
    "音集协", "音乐", "视频", "直播", "会员", "平台", "用户", "商户", "服务商",
    "不正当竞争", "商标", "专利", "劳动争议", "合同", "违约", "损失", "获利",
    "惩罚", "恶意", "情节严重", "故意", "主观过错", "过错", "因果关系",
)

# 疑问 / 泛词：做关键词抽取时剔除
STOPWORDS = (
    "请问", "麻烦", "我想", "我要", "帮我", "帮忙", "能不能", "可以吗", "是否", "有没有",
    "一般", "通常", "这类", "这类案件", "这种", "这种案件", "此类", "那类",
    "怎么", "如何", "怎样", "多少", "什么", "哪些", "哪个", "为什么", "怎么样",
    "后来", "结果", "情况", "案子", "案件", "案例", "判决书", "本院", "本所",
    "一下", "一个", "这些", "那些", "这个", "那个", "我们", "他们", "咱们",
)

_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万元|元)")
_CJK_RE = re.compile(r"[一-鿿]{2,}")
_SPLIT_RE = re.compile(r"[，。！？、；：,.!?;:\s（）()「」“”\"'’]+")
# 无实义字符：只有这些字构成的片段不是检索词（“样了”“的呢”）
_EMPTY_CHARS = set("了的呢吗吧啊呀哦嘛着过吧嗯给让被就都还也很和与及等了吗呢样")


def _meaningful_seg(seg: str) -> bool:
    return len(seg) >= 2 and any(ch not in _EMPTY_CHARS for ch in seg)



def _terms(query: str) -> list[str]:
    """从自然语言问题里抽检索词：领域词优先 + 清洗后的中文短语。

    · 领域词命中 → 直接用（精度最高）
    · 否则 → 取去掉疑问词后的中文短语（≤8 字），过长再滑窗切 4 字词
    """
    q = (query or "").strip()
    if not q:
        return []
    hits = [t for t in LEXICON if t in q]
    if not hits:
        # 隐含概念：「判多少钱 / 赔了多少」→ 走「赔偿」维度
        if re.search(r"(多少钱|多少钱|赔偿|判赔|金额|损失|获利)", q):
            hits = ["赔偿"]
    if hits:
        # 领域词按长度倒序（长词更具体），并去掉被更长词包含的短词
        hits.sort(key=len, reverse=True)
        kept: list[str] = []
        for t in hits:
            if not any(t in k for k in kept):
                kept.append(t)
        return kept[:6]

    text = q
    for w in STOPWORDS:
        text = text.replace(w, " ")
    segs = [s for s in _SPLIT_RE.split(text) if s]
    out: list[str] = []
    for seg in segs:
        seg = seg.strip()
        if not _meaningful_seg(seg):
            continue
        if len(seg) <= 8:
            out.append(seg)
        else:
            for i in range(0, len(seg) - 3, 4):
                piece = seg[i:i + 4]
                if _meaningful_seg(piece):
                    out.append(piece)
    return [t for t in dict.fromkeys(out) if len(t) >= 2][:6]


def _snippet(text: str, term: str, width: int = 140) -> str:
    """截取命中词附近的原文片段（作为可核查的证据）。"""
    body = (text or "").strip()
    if not body:
        return ""
    pos = body.find(term) if term else -1
    if pos < 0:
        return body[:width].replace("\n", " ")
    start = max(0, pos - width // 3)
    frag = body[start:start + width].replace("\n", " ")
    return ("…" if start else "") + frag + ("…" if start + width < len(body) else "")


def search(query: str, *, limit: int = 8, db_path: Optional[Path] = None) -> list[dict]:
    """在案件字段 + 提取物正文里检索，返回带出处的证据列表。

    返回项：{case_id, case_name, case_number, cause, year, artifact_title,
             artifact_type, snippet, score, field}
    """
    terms = _terms(query)
    if not terms:
        return []
    conn = db._get_conn(db_path)
    hits: dict[str, dict] = {}
    try:
        for term in terms:
            like = f"%{term}%"
            rows = conn.execute(
                "SELECT id, case_name, case_number, cause, year FROM cases WHERE "
                "case_name LIKE ? OR case_number LIKE ? OR cause LIKE ? OR "
                "plaintiff LIKE ? OR defendant LIKE ? OR result LIKE ? OR notes LIKE ?",
                (like, like, like, like, like, like, like),
            ).fetchall()
            for cid, cname, cnum, cause, year in rows:
                hit = hits.setdefault(f"case:{cid}", {
                    "case_id": cid, "case_name": cname or "", "case_number": cnum or "",
                    "cause": cause or "", "year": year, "artifact_title": "",
                    "artifact_type": "", "snippet": "", "score": 0, "field": "案件信息",
                })
                hit["score"] += 3
                hit["snippet"] = hit["snippet"] or f"{cause or ''} {cname or ''}".strip()

            arows = conn.execute(
                "SELECT a.id, a.case_id, a.title, a.artifact_type, a.content, "
                "c.case_name, c.case_number, c.cause, c.year FROM artifacts a "
                "LEFT JOIN cases c ON c.id = a.case_id "
                "WHERE a.title LIKE ? OR a.content LIKE ? LIMIT 200",
                (like, like),
            ).fetchall()
            for aid, cid, title, atype, content, cname, cnum, cause, year in arows:
                key = f"art:{aid}"
                hit = hits.setdefault(key, {
                    "case_id": cid or "", "case_name": cname or "", "case_number": cnum or "",
                    "cause": cause or "", "year": year, "artifact_title": title or "",
                    "artifact_type": atype or "", "snippet": "", "score": 0, "field": "提取物",
                    "artifact_id": aid or "",
                })
                hit["score"] += 2 if (title and term in title) else 1
                hit["snippet"] = hit["snippet"] or _snippet(content or "", term)
    finally:
        conn.close()

    out = sorted(hits.values(), key=lambda h: (-h["score"], h["case_name"] or ""))
    return out[:limit]


def _amount_stats(texts: list[str]) -> dict:
    """从命中文本里统计金额（元 / 万元）→ {count, min, max, median, unit}。"""
    values: list[float] = []
    for text in texts:
        for num, unit in _AMOUNT_RE.findall(text or ""):
            try:
                val = float(num)
            except ValueError:
                continue
            values.append(val * 10000 if unit == "万元" else val)
    if not values:
        return {}
    values.sort()
    mid = len(values) // 2
    median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
    return {
        "count": len(values),
        "min": values[0],
        "max": values[-1],
        "median": median,
    }


def amount_profile(*, limit: int = 1000, db_path: Optional[Path] = None) -> dict:
    """全库**金额画像**：所有提取物正文中的金额分布（回答「这类案子一般判多少钱」类问题）。

    返回 {count, min, max, median, by_case}；库内无金额则返回 {}。
    """
    conn = db._get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT content FROM artifacts WHERE content IS NOT NULL AND content != '' LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    stats = _amount_stats([r[0] for r in rows])
    if not stats:
        return {}
    conn = db._get_conn(db_path)
    try:
        crows = conn.execute(
            "SELECT COUNT(DISTINCT case_id) FROM artifacts WHERE content IS NOT NULL "
            "AND content LIKE '%元%'"
        ).fetchone()
    finally:
        conn.close()
    stats["by_case"] = int(crows[0]) if crows else 0
    return stats


def evidence(query: str, *, limit: int = 6, db_path: Optional[Path] = None) -> dict:
    """检索 + 汇总成**可核查的证据包**（供 LLM 作答 / 直接展示）。

    返回：{query, terms, hits, case_count, amounts, cases}
    """
    hits = search(query, limit=limit, db_path=db_path)
    cases = []
    seen = set()
    for h in hits:
        cid = h.get("case_id") or ""
        if cid and cid not in seen:
            seen.add(cid)
            cases.append({
                "case_id": cid, "case_name": h.get("case_name") or "",
                "case_number": h.get("case_number") or "", "cause": h.get("cause") or "",
                "year": h.get("year"),
            })
    texts = [h.get("snippet") or "" for h in hits]
    art_ids = [h.get("artifact_id") for h in hits if h.get("artifact_id")]
    if art_ids:
        conn = db._get_conn(db_path)
        try:
            q = ",".join("?" for _ in art_ids)
            rows = conn.execute(
                f"SELECT content FROM artifacts WHERE id IN ({q})", tuple(art_ids)
            ).fetchall()
            texts.extend(r[0] or "" for r in rows)
        finally:
            conn.close()
    amounts = _amount_stats(texts)
    return {
        "query": (query or "").strip(),
        "terms": _terms(query),
        "hits": hits,
        "cases": cases,
        "case_count": len(cases),
        "amounts": amounts,
    }


def evidence_text(ev: dict, *, max_chars: int = 2400) -> str:
    """证据包 → 纯文本（喂给 LLM / 展示），每条标注出处。"""
    if not ev or not ev.get("hits"):
        return ""
    lines: list[str] = []
    for i, h in enumerate(ev.get("hits") or [], 1):
        src = " ".join(x for x in (h.get("case_name") or "", h.get("case_number") or "") if x)
        src = src or "（未命名案件）"
        dim = h.get("artifact_title") or ""
        lines.append(
            f"[{i}] 来源：{src}" + (f" · {dim}" if dim else "") + "\n"
            f"    {(h.get('snippet') or '').strip()}"
        )
    amt = ev.get("amounts") or {}
    if amt.get("count"):
        lines.append(
            f"[金额统计] 命中文本中共出现 {amt['count']} 处金额："
            f"最低 {amt['min']/10000:.1f} 万元，中位 {amt['median']/10000:.1f} 万元，"
            f"最高 {amt['max']/10000:.1f} 万元"
        )
    text = "\n".join(lines)
    return text[:max_chars]


__all__ = [
    "LEXICON", "STOPWORDS", "search", "evidence", "evidence_text",
    "amount_profile", "_terms",
]
