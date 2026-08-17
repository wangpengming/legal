"""AI 端点（docs/03 §6.2：/ai/query + /ai/chat + /ai/report-templates）。

- /ai/query：Phase 0 本地检索 v1（兼容保留）；
- /ai/chat（Phase 3 Mode A/B 切换）：Mode A = 意图分类 → 三源交叉检索
  （local=FTS5 案件 / cases=external_cases / law=法规常量库）→ 规则生成 Markdown
  回答（G10：结论强制带来源脚注）；Mode B = 报告意图识别 → T1~T7 模板与参数
  抽取 → render_report 生成落库（与 /reports/generate 同口径）。
- 模型抽象层：当前为规则内核（无外部模型调用），接口预留 $OPENAI_BASE 升级位。
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.laws import search_laws
from app.ai.reports import render_report, triple_sources
from app.api.schemas import AiChatRequest, AiQueryRequest, AiReportTemplateResult, audit, ok
from app.api.search import _case_basic, _resolve_case
from app.core.database import get_db
from app.models.fact import Case, Song, SongCase
from app.models.fts import search_cases
from app.models.ops import ExternalCase, Report
from app.stats.metrics import compute_overview

router = APIRouter(tags=["ai"])

# 证据卡片展示字段（_case_basic 子集，按口径元数据取 label）
_EVIDENCE_COLUMNS = ("case_no", "case_status", "biz_line", "cause", "resolve",
                     "plaintiff", "defendant", "court", "accept_date", "close_date",
                     "amount", "pay_amount", "support_rate", "dirty_flags")

# Mode B 报告模板 T1~T7（静态注册；与 app/ai/reports.render_report 一一对应）
_REPORT_TEMPLATES: list[dict] = [
    {"key": "T1", "title": "案件全景报告", "description": "给定案件/当事人的全维度画像：基础信息、诉讼地位、金额、关联歌曲、系列案、状态时间线",
     "params": ["case_no"], "output": "markdown"},
    {"key": "T2", "title": "胜诉率分析", "description": "按业务线/年份/案由维度拆解胜诉率A/B、支持率，定位低谷原因",
     "params": ["biz_line?", "year?", "cause?"], "output": "markdown+table"},
    {"key": "T3", "title": "判赔与费用分析", "description": "判赔率、单曲判赔、获赔/支出/净费用四值与月度趋势，存疑金额标注",
     "params": ["year?"], "output": "markdown+table"},
    {"key": "T4", "title": "对手方画像", "description": "指定被告的涉诉规模、判赔均值、异地管辖表现与典型案由",
     "params": ["party"], "output": "markdown"},
    {"key": "T5", "title": "歌曲使用统计", "description": "曲目使用频次、单曲判赔、在办/结案分布与高频歌曲清单",
     "params": ["song?"], "output": "markdown+table"},
    {"key": "T6", "title": "同步健康报告", "description": "增量/全量同步历史、脏数据清单、规则启停状态与待治理项",
     "params": [], "output": "markdown"},
    {"key": "T7", "title": "口径复核报告", "description": "8 项指标当前值 + formula_sql 对照 + 版本历史，审计复核用",
     "params": ["metric_key?"], "output": "markdown"},
]

_FOOTNOTE_V1 = (
    "AI 检索 v1（Phase 0 本地内核）：证据 = FTS5 2-gram 检索命中的案件摘要；"
    "指标 = 8 项口径 v1.0 实时计算（见 08-metrics）；无外部模型参与，Phase 3 升级对话"
)
_FOOTNOTE_A = (
    "Mode A 对话（规则内核 v2）：三源交叉验证 = local（FTS5 案件）/ cases（external_cases "
    "外部案例库）/ law（法规常量库）；结论基于上述来源，未命中源会显式标注缺源。"
)
_FOOTNOTE_B = (
    "Mode B 报告生成（规则内核 v2）：问题 → T1~T7 模板 + 参数抽取；口径与 /stats/* 单一口径源，"
    "产物落库 reports 表（详见 10-reports 存档）。"
)

# 意图关键词（Mode A）：数据类词优先，避免含「案件」的数据长句误判为单案检索
_DATA_HINTS = ("判赔", "胜诉", "获赔", "金额", "费用", "支出", "净额", "统计", "分布",
               "趋势", "汇总", "月度", "多少", "占比", "均值", "单曲", "排行", "清单", "率")
_DOC_HINTS = ("案号", "详情", "当事人", "单案", "案卷", "判决书", "卷宗")
_REPORT_HINTS = ("报告", "分析", "模板", "生成", "T1", "T2", "T3", "T4", "T5", "T6", "T7")
# 案号样式（2023）京0105民初8888号：提问含案号 → 单案意图
_CASE_NO_RE = re.compile(r"[（(]\s*20\d{2}\s*[）)]")
# 疑问/虚词停用词：检索回退时剔除，避免整句 2-gram AND 零命中
_STOPWORDS = (
    "如何", "怎样", "怎么", "什么", "哪些", "这些", "那些", "哪里", "多少",
    "查一下", "查询", "检索", "请问", "一下", "看看", "了解", "关于", "相关",
    "有关", "情况", "帮我", "告诉", "说明", "知道", "可以", "能不能", "是否",
    "吗", "呢", "啊", "吧", "哦", "了", "的", "请", "该", "等",
)

# Mode B 模板意图（顺序匹配，先命中先取）
_B_INTENT: list[tuple[str, tuple[str, ...]]] = [
    ("T6", ("同步", "健康", "脏数据", "治理")),
    ("T7", ("口径", "复核", "审计", "指标", "公式")),
    ("T1", ("案件全景", "单案", "全维度", "画像报告")),
    ("T2", ("胜诉", "胜诉率", "败诉", "支持率")),
    ("T3", ("判赔", "费用", "获赔", "四值", "月度")),
    ("T4", ("对手方", "对手画像", "被告画像", "涉诉规模")),
    ("T5", ("歌曲", "曲目", "单曲", "高频歌曲")),
]

# 业务线 8 枚举（seed.py）
_BIZ_LINES = ("VOD", "IPTV·OTT", "车载", "雷客", "人力", "哇屋", "研发", "默霆")

_QUOTE_RE = re.compile(r"[「“\"']([^」”\"']+)[」”\"']")
_YEAR_RE = re.compile(r"(20\d{2})\s*年")


def _intent(q: str) -> str:
    """Mode A 意图三分类：report / query_doc（单案）/ query_data（统计量）。

    数据词优先：长句「音集协相关案件判赔情况如何？」含「案件」但语义是统计，
    只要同时含数据词即归 query_data；纯单案（含案号/当事人/详情且无数据词）才归 query_doc。
    """
    if any(h in q for h in _REPORT_HINTS):
        return "report"
    has_doc = any(h in q for h in _DOC_HINTS) or _CASE_NO_RE.search(q) is not None
    has_data = any(h in q for h in _DATA_HINTS)
    if has_doc and not has_data:
        return "query_doc"
    return "query_data"


def _strip_noise(q: str) -> str:
    """剔除疑问/虚词停用词，保留实体与指标词（检索回退用）。"""
    out = q
    for w in _STOPWORDS:
        out = out.replace(w, "")
    return out.strip()


def _hint_anchored(core: str) -> list[str]:
    """以已知词为锚的候选膨胀：核心词 + 数据词前缀实体段逐级收缩。

    例「音集协案件判赔」→ 判赔 / 音集协案件 → 音集协（2-gram 可命中原告简称）。
    """
    out: list[str] = []
    pool = sorted(set(_DATA_HINTS) | set(_DOC_HINTS) | set(_BIZ_LINES), key=len, reverse=True)
    for w in pool:
        if len(w) >= 2 and w in core and w not in out:
            out.append(w)
    for w in _DATA_HINTS + ("案件",):
        if len(w) >= 2 and w not in out:
            idx = core.find(w)
            if idx > 0:
                prefix = core[:idx]
                if prefix not in out:
                    out.append(prefix)
                for doc in ("案件", "详情"):
                    if doc in prefix:
                        head = prefix.split(doc)[0]
                        if head and head not in out:
                            out.append(head)
    return out


def _best_query(db: Session, q: str, limit: int = 8) -> tuple[str, list[dict], int]:
    """逐级回退检索：案号段 → 整句 → 去停用词核心 → 最长实义词 → hint 锚定词。

    长句 2-gram AND 整句展开通常零命中，回退可显著提升 Mode A/B 召回；
    返回首个有命中的检索词与结果（无命中时返回原句 + 空结果）。
    """
    candidates: list[str] = []
    cm = re.search(r"[（(]\s*20\d{2}[^）)]*[）)]\s*[\u4e00-\u9fff0-9A-Za-z]{2,60}号", q)
    if cm:
        candidates.append(cm.group(0))
    candidates.append(q)
    core = _strip_noise(q)
    if core and core != q:
        candidates.append(core)
    tokens = [t for t in re.split(r"[\s，。！？、,.;:：·—\-/\\（）()「」《》]+", core) if len(t) >= 2]
    if tokens:
        # 中文实义词优先于数字/英文token（如「VOD 2024 判赔」应取「判赔」而非「2024」）
        zh_terms = [t for t in tokens if re.search(r"[\u4e00-\u9fff]", t)]
        longest = max(zh_terms or tokens, key=len)
        if longest not in candidates:
            candidates.append(longest)
    candidates.extend(w for w in _hint_anchored(core or q) if w not in candidates)
    for term in candidates:
        hits, total = search_cases(db, term, limit=limit)
        if hits:
            return term, hits, total
    # 歌曲域兜底：case 文本不含歌名（如「可可西里」），经 song_case 关联补召回
    for term in candidates:
        ids = _song_linked_cases(db, term, limit=limit)
        if ids:
            return term, [{"case_id": i} for i in ids], len(ids)
    # 开放歌单问句（如「哪首歌被起诉次数最多」）：无精确实体 → 默认聚焦关联案件最多的歌曲
    if any(w in (core or q) for w in ("歌", "曲")):
        top_row = db.execute(
            text(
                "SELECT s.song_name FROM song_case sc JOIN songs s ON s.id = sc.song_id "
                "GROUP BY s.id ORDER BY COUNT(*) DESC, s.id LIMIT 1"
            )
        ).fetchone()
        if top_row:
            top = top_row[0]
            ids = _song_linked_cases(db, top, limit=limit)
            if ids:
                return top, [{"case_id": i} for i in ids], len(ids)
    return q, [], 0


def _song_linked_cases(db: Session, term: str, limit: int = 8) -> list[int]:
    """song_name LIKE → 关联案件 id（覆盖案件正文不含歌名的场景，保底召回）。"""
    pattern = f"%{term}%"
    rows = db.execute(
        text(
            "SELECT DISTINCT sc.case_id FROM song_case sc "
            "JOIN songs s ON s.id = sc.song_id "
            "WHERE s.song_name LIKE :p OR s.song_name_raw LIKE :p LIMIT :lim"
        ),
        {"p": pattern, "lim": limit},
    ).fetchall()
    return [r[0] for r in rows]


def _evidence_cards(db: Session, q: str, limit: int = 8) -> tuple[str, list[dict], int, list[int]]:
    used, hits, total = _best_query(db, q)
    cards: list[dict] = []
    ids: list[int] = []
    for h in hits[:limit]:
        try:
            case = _resolve_case(db, str(h["case_id"]))
        except Exception:  # noqa: BLE001 检索与详情一致，防御跳变
            continue
        base = _case_basic(case)
        cards.append({c: base.get(c) for c in _EVIDENCE_COLUMNS if c in base})
        ids.append(h["case_id"])
    return used, cards, total, ids


def _external_hits(db: Session, q: str, limit: int = 5) -> list[dict]:
    rows = db.scalars(
        select(ExternalCase)
        .where(
            ExternalCase.case_no.contains(q)
            | ExternalCase.cause.contains(q)
            | ExternalCase.defendant.contains(q)
            | ExternalCase.song.contains(q)
            | ExternalCase.summary.contains(q)
        )
        .limit(limit)
    ).all()
    return [
        {"case_no": r.case_no, "court": r.court, "cause": r.cause, "defendant": r.defendant,
         "song": r.song, "amount": r.amount, "verdict": r.verdict, "url": r.url}
        for r in rows
    ]


def _markdown_response(q: str, intent: str, cards: list[dict], total: int,
                       ext: list[dict], laws: list[dict], used: str | None = None) -> str:
    """规则生成回答（G10：结论强制带来源，Markdown 输出）。"""
    lines = [f"### 关于「{q}」的检索结果", ""]
    if used and used != q:
        lines.append(f"> 整句未命中，已自动聚焦检索词：`{used}`")
        lines.append("")
    if intent == "query_doc":
        if cards:
            top = cards[0]
            lines.append(
                f"- **命中 {total} 件案件**；与本问题最相关的案件："
                f"**{top.get('case_no') or '—'}**（{top.get('biz_line') or '—'} · "
                f"{top.get('cause') or '—'}，结案 {top.get('resolve') or '—'}，"
                f"标的 ¥{top.get('amount') or 0:,.2f}）。"
            )
        else:
            lines.append(f"- 本地库未检索到与「{q}」相关的案件（local 源缺命中）。")
    else:
        lines.append(f"- 本地库命中 **{total} 件案件**（证据卡片 {len(cards)} 条，见下方表格）。")
        if ext:
            lines.append(f"- 外部案例库命中 **{len(ext)} 条**可参照判决（见外部案例区）。")
        if laws:
            lines.append(f"- 法规命中 **{len(laws)} 条**相关条文（判赔/管辖/取证等，见法规引用区）。")
        else:
            lines.append("- 法规未命中相关条文（law 源缺命中，请核实检索词）。")
    lines.append("")
    if cards:
        lines.append("#### 证据卡片（local 源）")
        lines.append("")
        lines.append("| 案号 | 业务线 | 案由 | 结案原因 | 标的 | 支付额 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for c in cards[:6]:
            lines.append(
                f"| {c.get('case_no') or '—'} | {c.get('biz_line') or '—'} | "
                f"{c.get('cause') or '—'} | {c.get('resolve') or '—'} | "
                f"¥{c.get('amount') or 0:,.2f} | ¥{c.get('pay_amount') or 0:,.2f} | "
                f"{c.get('case_status') or '—'} |"
            )
        lines.append("")
    if ext:
        lines.append("#### 外部案例（cases 源）")
        lines.append("")
        lines.append("| 案号 | 法院 | 案由 | 被告 | 歌曲 | 判赔额 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for e in ext:
            lines.append(
                f"| {e['case_no'] or '—'} | {e['court'] or '—'} | {e['cause'] or '—'} | "
                f"{e['defendant'] or '—'} | {e['song'] or '—'} | ¥{e['amount'] or 0:,.2f} |"
            )
        lines.append("")
    if laws:
        lines.append("#### 法规引用（law 源）")
        lines.append("")
        for l in laws:
            lines.append(f"- **{l['law']} {l['article']}**：{l['text'][:80]}…")
        lines.append("")
    lines.append("> 来源声明：本回答由上述三源交叉验证生成；local=本库检索，cases=外部案例库，law=法规库。")
    return "\n".join(lines)


# ── Mode B 报告意图与参数抽取 ────────────────────────────────────

def _detect_template(q: str) -> str | None:
    for key, hints in _B_INTENT:
        if any(h in q for h in hints):
            return key
    return None


def _anchored_params(db: Session, key: str, quoted: list[str], q: str) -> dict:
    """参数兜底：优先引号 → 年份/业务线正则 → FTS 第一案实体锚定。"""
    params: dict = {}
    m = _YEAR_RE.search(q)
    if m:
        params["year"] = m.group(1)
    for biz in _BIZ_LINES:
        if biz in q:
            params["biz_line"] = biz
            break
    if quoted:
        if key in ("T1",):
            params["case_id"] = quoted[0]
        elif key in ("T4", "T2"):
            params["party"] = quoted[0]
        elif key in ("T5",):
            params["song"] = quoted[0]
        return params
    if key in ("T1", "T4", "T5"):
        _, hits, _ = _best_query(db, q, limit=5)
        if not hits:
            return params
        try:
            case = _resolve_case(db, str(hits[0]["case_id"]))
        except Exception:  # noqa: BLE001 兜底失败不影响
            return params
        if key == "T1":
            params["case_id"] = str(case.id)
        elif key == "T4":
            defs = []
            try:
                raw = json.loads(case.defendant) if isinstance(case.defendant, str) else case.defendant
                defs = [d for d in (raw or []) if isinstance(d, str)]
            except (TypeError, ValueError):
                defs = []
            if defs:
                params["party"] = defs[0]
        elif key == "T5":
            song = db.execute(
                select(Song.song_name)
                .join(SongCase, SongCase.song_id == Song.id)
                .where(SongCase.case_id == case.id)
                .limit(1)
            ).scalar()
            if song:
                params["song"] = song
    return params


def _chat_report(db: Session, q: str) -> dict:
    key = _detect_template(q)
    if key is None:
        return {
            "mode": "B",
            "title": "未识别报告模板",
            "answer": "未识别出明确的报告模板。可选模板（T1~T7）：\n\n"
            + "\n".join(f"- **{t['key']}** {t['title']}：{t['description']}" for t in _REPORT_TEMPLATES)
            + "\n\n> 请描述分析意图（如「生成 T2 胜诉率分析报告」或「对手方 A 公司画像报告」）。",
            "report_id": None,
            "sources": triple_sources(db, key or "T2", {}),
            "footnote": _FOOTNOTE_B,
        }
    quoted = _QUOTE_RE.findall(q)
    params = _anchored_params(db, key, quoted, q)
    # 幂等：同模板+同参数取最新一条
    dup = db.scalar(
        select(Report).where(
            Report.template_key == key,
            Report.params_json == json.dumps(params, ensure_ascii=False),
        ).order_by(Report.id.desc())
    )
    if dup is not None:
        r = dup
    else:
        try:
            title, body = render_report(db, key, params)
        except Exception as e:  # noqa: BLE001 渲染容错
            return {"mode": "B", "title": "报告生成失败", "answer": f"> 生成失败：{e}",
                    "report_id": None, "sources": triple_sources(db, key, params),
                    "footnote": _FOOTNOTE_B}
        r = Report(
            template_key=key,
            title=title,
            body=body,
            params_json=json.dumps(params, ensure_ascii=False),
            created_by="ai_chat",
        )
        db.add(r)
        db.commit()
        db.refresh(r)
    return {
        "mode": "B",
        "template_key": key,
        "title": r.title,
        "answer": r.body,
        "report_id": r.id,
        "params": params,
        "sources": triple_sources(db, key, params),
        "footnote": _FOOTNOTE_B,
    }


def _chat_answer(db: Session, q: str) -> dict:
    intent = _intent(q)
    used, cards, total, _ = _evidence_cards(db, q)
    core = _strip_noise(q) or used
    ext = _external_hits(db, core)
    laws = search_laws(core)
    answer = _markdown_response(q, intent, cards, total, ext, laws, used=used)
    return {
        "mode": "A",
        "intent": intent,
        "used_query": used,
        "answer": answer,
        "evidence": cards,
        "law_hits": [{"law": l["law"], "article": l["article"], "text": l["text"]} for l in laws],
        "sources": {
            "local": {"hits": total, "note": "FTS5 案件检索（含歌名关联化兜底）"},
            "cases": {"hits": len(ext), "note": "external_cases 包含匹配"},
            "law": {"hits": len(laws), "note": "法规常量库关键词命中"},
        },
        "footnote": _FOOTNOTE_A,
    }


@router.post("/ai/chat")
def ai_chat(payload: AiChatRequest, db: Session = Depends(get_db)) -> dict:
    """Mode A/B 对话（Phase 3）：mode=A 三源问答；mode=B 报告意图生成。"""
    q = (payload.question or "").strip()
    if not q:
        return ok({"mode": payload.mode, "answer": "问题为空，无法回答；请输入检索词或报告意图"},
                  footnote=_FOOTNOTE_A)
    result = _chat_report(db, q) if payload.mode == "B" else _chat_answer(db, q)
    audit(db, op_type="ai", table_name="reports" if payload.mode == "B" else "cases",
          action="ai_chat", detail={"mode": payload.mode, "question": q,
                                    "session_id": payload.session_id or ""})
    return ok(result, footnote=result.get("footnote") or _FOOTNOTE_A)


# ── v1 兼容端点 ───────────────────────────────────────────────────

@router.post("/ai/query")
def ai_query(payload: AiQueryRequest, db: Session = Depends(get_db)) -> dict:
    """本地检索 v1：问题 → 证据（检索案件摘要）+ 指标快照 + 口径脚注。"""
    q = (payload.question or "").strip()
    if not q:
        return ok(
            {"question": payload.question, "answer": "问题为空，无法检索", "evidence": [], "metrics": []},
            footnote=_FOOTNOTE_V1,
        )
    hits, total = search_cases(db, q)
    evidence: list[dict] = []
    for h in hits[:10]:  # 证据卡片上限 10 条（摘要级）
        try:
            case = _resolve_case(db, str(h["case_id"]))
        except Exception:  # noqa: BLE001 检索与详情一致，防御跳变
            continue
        base = _case_basic(case)
        evidence.append({c: base.get(c) for c in _EVIDENCE_COLUMNS if c in base})
    metrics = compute_overview(db)
    audit(db, op_type="ai", table_name="cases", action="ai_query",
          detail={"question": q, "hits": len(hits), "evidence": len(evidence)})
    return ok(
        {
            "question": payload.question,
            "answer": (
                f"本地检索「{q}」命中 {total} 条案件（证据卡片 {len(evidence)} 条）；"
                f"附 8 项指标口径 v1.0 快照（{len(metrics)} 项）。"
                f"口径声明与证据明细见 meta.footnote / evidence。"
            ),
            "evidence": evidence,
            "metrics": metrics,
        },
        total=total,
        footnote=_FOOTNOTE_V1,
    )


@router.get("/ai/report-templates")
def report_templates() -> dict:
    """Mode B 报告模板清单 T1~T7（Phase 3 落地；字段见 AiReportTemplateResult）。"""
    return ok(
        [AiReportTemplateResult(**t) for t in _REPORT_TEMPLATES],
        total=len(_REPORT_TEMPLATES),
        footnote="报告模板 T1~T7 定义见实现计划 Phase 3（Mode B）；与 /ai/query 共用本地检索内核",
    )