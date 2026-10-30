#!/usr/bin/env python3
# =============================================
# lark_websearch.py - 业务相关的联网检索（无密钥、stdlib、fail-soft）
#
# 定位：Bot 需要**外部**信息时（法律法规 / 司法解释 / 赔偿标准 / 裁判规则 / 公开判例）
#   才走这里；翻查本地案件**不用**它。
#
# 原则：
#   · 零第三方依赖（urllib + 正则），可注入 fetcher → 单测不出网
#   · fail-soft：任何网络/解析异常一律返回 []，由上层给友好提示，不报错
#   · 敏感拦截：查询含身份证/手机号形态 → 不外发，直接返回 []
#   · 开关：WEB_SEARCH_ENABLED=0 可整体关闭；WEB_SEARCH_ENDPOINT 可换检索端点
#
# 见 docs/SPEC-feishu-bot.md §5.5。
# =============================================
from __future__ import annotations

import html
import os
import re
import urllib.parse
import urllib.request

DEFAULT_ENDPOINT = "https://html.duckduckgo.com/html/"
DEFAULT_TIMEOUT = 8.0
MAX_RESULTS = 5

# 敏感形态（身份证 / 手机号）：命中则拒绝外发
_PII_RE = re.compile(r"(?<!\d)\d{15,18}[\dXx](?!\d)|(?<!\d)1[3-9]\d{9}(?!\d)")

_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.S,
)
_SNIPPET_RE = re.compile(r'class="result__snippet"[^>]*>(?P<snip>.*?)</a>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def enabled() -> bool:
    return os.environ.get("WEB_SEARCH_ENABLED", "1") not in ("0", "false", "False")


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _unwrap(href: str) -> str:
    """解 DuckDuckGo 跳转链：//duckduckgo.com/l/?uddg=<urlencoded> → 真实 URL。"""
    if "uddg=" in href:
        if href.startswith("//"):
            href = "https:" + href
        target = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg")
        if target:
            return target[0]
    return href


def _fetch(endpoint: str, query: str, timeout: float) -> str:
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; LegalCaseBot/1.0)",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, "replace")


def parse(body: str, *, limit: int = MAX_RESULTS) -> list[dict]:
    """HTML → 结构化结果（title / url / snippet）。纯函数，便于单测。"""
    titles = list(_RESULT_RE.finditer(body or ""))
    snippets = [m.group("snip") for m in _SNIPPET_RE.finditer(body or "")]
    out: list[dict] = []
    for i, m in enumerate(titles[:limit]):
        out.append({
            "title": _clean(m.group("title")),
            "url": _unwrap(m.group("href")),
            "snippet": _clean(snippets[i]) if i < len(snippets) else "",
        })
    return out


def search(query: str, *, limit: int = MAX_RESULTS, timeout=None, fetcher=None) -> list[dict]:
    """联网检索；任何失败返回 []（调用方给友好提示）。fetcher 可注入以离线单测。"""
    q = (query or "").strip()
    if not q or not enabled() or _PII_RE.search(q):
        return []
    endpoint = os.environ.get("WEB_SEARCH_ENDPOINT") or DEFAULT_ENDPOINT
    to = float(timeout or os.environ.get("WEB_SEARCH_TIMEOUT") or DEFAULT_TIMEOUT)
    try:
        body = (fetcher or _fetch)(endpoint, q, to)
    except Exception:  # noqa: BLE001 — 联网失败一律降级
        return []
    try:
        return parse(body, limit=limit)
    except Exception:  # noqa: BLE001
        return []


__all__ = ["search", "parse", "enabled", "DEFAULT_ENDPOINT", "MAX_RESULTS"]