"""Mode B 报告模板渲染器 T1~T7（docs/03 §7.3 / 需求 F5.2）。

每个 render_* 返回 (title, markdown body)，由 api/reports.py 组装三源脚注并
落库 reports 表；数据口径与 /stats/*、/metrics 引擎完全同构（单一口径源）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai.laws import law_brief, search_laws
from app.api.search import _case_basic, _resolve_case
from app.models.fact import Case, Song, SongCase
from app.models.meta import CleanRule, MetricDef
from app.models.ops import ExternalCase, Report, SyncJob
from app.stats.metrics import compute_metric, compute_overview, metric_versions

_VERDICT_RESOLVE = "判赔"
_WIN_A = "'胜诉','驳回上诉维持原判','判决驳回对雷石的诉求','裁定驳回雷石的诉讼请求','裁定驳回对雷石的诉讼请求'"
_WIN_B = _WIN_A + ",'双方和解'"

# 三源脚注检索词优先级（与模板参数语义对应）
_SOURCE_FIELDS: dict[str, list[str]] = {
    "T1": ["case_no", "case_id"],
    "T2": ["biz_line", "cause", "year"],
    "T3": ["year", "biz_line"],
    "T4": ["party"],
    "T5": ["song", "biz_line"],
    "T6": [],  # 同步健康无检索语义，取空
    "T7": ["metric_key", "biz_line", "year"],
}


def triple_sources(db: Session, key: str, params: dict | None = None) -> dict:
    """三源交叉验证脚注（G10）：local / cases / law 各源命中计数。

    local = 本库已有同模板产物（口径有据）；cases = external_cases 包含匹配
    （案号/案由/被告/歌曲/摘要）；law = 法规常量库关键词命中。
    """
    params = params or {}
    texts: list[str] = []
    for field in _SOURCE_FIELDS.get(key, []):
        v = (params.get(field) or "").strip()
        if v and v not in texts:
            texts.append(v)
    texts = texts[:3] or [key]
    local_count = (
        db.scalar(select(func.count(Report.id)).where(Report.template_key == key)) or 0
    )
    case_count = 0
    law_count = 0
    for t in texts:
        cond = (
            ExternalCase.case_no.contains(t)
            | ExternalCase.cause.contains(t)
            | ExternalCase.defendant.contains(t)
            | ExternalCase.song.contains(t)
            | ExternalCase.summary.contains(t)
        )
        case_count += len(db.scalars(select(ExternalCase).where(cond).limit(10)).all())
        law_count += len(search_laws(t))
    return {
        "local": {"source": "cases（本库）", "hits": local_count, "note": "本地检索/口径快照"},
        "cases": {"source": "external_cases（外部案例库）", "hits": case_count,
                  "note": "含案号/案由/被告/歌曲/摘要包含匹配"},
        "law": {"source": "laws（法规常量库）", "hits": law_count,
                "note": f"命中法规条数（库共 {law_brief()} 条）"},
    }


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"¥{v:,.2f}"
        return f"{v:.2%}"
    return str(v)


def _fmt_date(ms: int | None) -> str:
    if not ms:
        return "—"
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return "—"


def _year_filter(params: dict, where: list[str], bind: dict) -> None:
    y = (params.get("year") or "").strip()
    if y:
        where.append("year = :py")
        bind["py"] = int(y) if str(y).isdigit() else y


def _filters_clause(params: dict) -> tuple[list[str], dict]:
    where: list[str] = []
    bind: dict = {}
    for key, col in (("biz_line", "biz_line"), ("cause", "cause"), ("resolve", "resolve")):
        v = (params.get(key) or "").strip()
        if v:
            where.append(f"{col} = :p{col}")
            bind[f"p{col}"] = v
    _year_filter(params, where, bind)
    return where, bind


# ---------------------------------------------------------------- T1 案件全景

def render_report(db: Session, template_key: str, params: dict | None = None) -> tuple[str, str]:
    params = params or {}
    fn = {
        "T1": _t1_case_panorama,
        "T2": _t2_win_rate,
        "T3": _t3_fees,
        "T4": _t4_party,
        "T5": _t5_songs,
        "T6": _t6_sync_health,
        "T7": _t7_metrics_audit,
    }.get(template_key)
    if fn is None:
        raise ValueError(f"未知报告模板：{template_key}")
    return fn(db, params)


def _t1_case_panorama(db: Session, params: dict) -> tuple[str, str]:
    key = (params.get("case_no") or params.get("case_id") or "").strip()
    if not key:
        return "案件全景报告", "> 错误：缺少 case_no/case_id 参数"
    try:
        case = _resolve_case(db, key)
        base = _case_basic(case)
    except Exception as e:  # noqa: BLE001 渲染容错
        return "案件全景报告", f"> 错误：案件不存在或查询失败（{e}）"
    songs = db.execute(
        select(Song.song_name, Song.artist, SongCase.role)
        .join(SongCase, SongCase.song_id == Song.id)
        .where(SongCase.case_id == case.id)
        .order_by(Song.id)
    ).mappings().all()
    siblings = db.scalars(
        select(Case).where(Case.parent_record_id == case.record_id).order_by(Case.id).limit(20)
    ).all()
    lines = [
        f"# 案件全景报告（T1）",
        "",
        f"- 案号：{base.get('case_no') or '—'}（record_id：{base.get('record_id')}）",
        f"- 案件状态：{base.get('case_status') or '—'}　收案年份：{base.get('year') or '—'}",
        f"- 案由：{base.get('cause') or '—'}",
        f"- 业务线：{base.get('biz_line') or '—'}　支付主体：{base.get('payer') or '—'}",
        f"- 原告：{base.get('plaintiff') or '—'}",
        f"- 被告：{', '.join(base.get('defendant') or []) or '—'}",
        "",
        "## 金额",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| 标的金额 | {_fmt(base.get('amount'))} |",
        f"| 支付总金额 | {_fmt(base.get('pay_amount'))} |",
        f"| 单曲判赔 | {_fmt(base.get('per_song_amount'))} |",
        f"| 对方诉求支持率 | {_fmt(base.get('support_rate'))} |",
        "",
        "## 时间线",
        "",
        "| 事件 | 日期 |",
        "| --- | --- |",
        f"| 收案 | {_fmt_date(base.get('accept_date'))} |",
        f"| 结案 | {_fmt_date(base.get('close_date'))} |",
        f"| 一审文书 | {_fmt_date(base.get('doc1_date'))} |",
        f"| 二审文书 | {_fmt_date(base.get('doc2_date'))} |",
        f"| 支付 | {_fmt_date(base.get('pay_date'))} |",
        "",
    ]
    if songs:
        lines += [
            "## 关联歌曲",
            "",
            "| 歌曲 | 艺人 | 角色 |",
            "| --- | --- | --- |",
            *[f"| {s['song_name']} | {s['artist'] or '—'} | {s['role'] or '—'} |" for s in songs],
            "",
        ]
    if siblings:
        lines += [
            f"## 系列案（{len(siblings)} 件）",
            "",
            "| 案号 | 年份 | 结案原因 |",
            "| --- | --- | --- |",
            *[f"| {s.case_no or '—'} | {s.year or '—'} | {s.resolve or '—'} |" for s in siblings],
            "",
        ]
    if case.notes:
        lines.append(f"## 办案笔记\n\n{case.notes}\n")
    lines.append("> 口径：字段为清洗后规范值；raw 原始值见案件详情页。")
    return "案件全景报告（T1）", "\n".join(lines)


# ---------------------------------------------------------------- T2 胜诉率分析

def _t2_win_rate(db: Session, params: dict) -> tuple[str, str]:
    where, bind = _filters_clause(params)
    clause = " AND ".join(where) if where else "1=1"
    rows = db.execute(
        text(
            "SELECT resolve, COUNT(*) AS cnt FROM cases "
            f"WHERE {clause} AND resolve IS NOT NULL GROUP BY resolve ORDER BY cnt DESC"
        ),
        bind,
    ).mappings().all()
    total = sum(r["cnt"] for r in rows) or 0
    own = sum(r["cnt"] for r in rows if r["resolve"] in _WIN_A.split(",") or r["resolve"] == "胜诉")
    lines = [
        "# 胜诉率分析报告（T2）",
        "",
    ]
    dims = [f"{k}={v}" for k, v in (("业务线", params.get("biz_line")), ("年份", params.get("year")),
                                    ("案由", params.get("cause"))) if v]
    lines.append(f"- 分析维度：{' / '.join(dims) if dims else '全库'}")
    lines.append(f"- 样本量：{total} 件（已结案原因非空）")
    lines.append("")
    lines.append("## 结案原因分布")
    lines.append("")
    lines.append("| 结案原因 | 件数 | 占比 |")
    lines.append("| --- | --- | --- |")
    for r in rows:
        lines.append(f"| {r['resolve']} | {r['cnt']} | {r['cnt'] / total:.2%}" if total else f"| {r['resolve']} | {r['cnt']} | — |")
    lines.append("")
    lines.append("## 胜诉率指标")
    lines.append("")
    lines.append("| 指标 | 值 | 口径 |")
    lines.append("| --- | --- | --- |")
    for key in ("win_rate_a", "win_rate_b", "support_rate", "verdict_rate"):
        m = compute_metric(db, key, dict(_filter_pairs(params)))
        if m and m.get("value") is not None:
            lines.append(f"| {m['title']} | {m['value']:.4f} | {m.get('footnote') or '—'} |")
    lines.append("")
    lines.append(f"> 胜诉口径说明：口径A = 胜/（胜+败），败=判赔；口径B = 口径A + 双方和解。败诉基准 = 结案原因「{_VERDICT_RESOLVE}」。")
    return "胜诉率分析报告（T2）", "\n".join(lines)


def _filter_pairs(params: dict) -> list[tuple]:
    out: list[tuple] = []
    for key in ("biz_line", "year", "cause"):
        if (params.get(key) or "").strip():
            out.append((key, params[key].strip()))
    return out


# ---------------------------------------------------------------- T3 判赔与费用

def _t3_fees(db: Session, params: dict) -> tuple[str, str]:
    where = ["resolve = :r"]
    bind = {"r": _VERDICT_RESOLVE}
    _year_filter(params, where, bind)
    clause = " AND ".join(where)
    v = db.execute(
        text(f"SELECT COUNT(*) AS cnt, COALESCE(SUM(pay_amount),0) AS amount, COUNT(pay_date) AS paid FROM cases WHERE {clause}"),
        bind,
    ).mappings().one()
    monthly = db.execute(
        text(
            "SELECT strftime('%Y-%m', datetime(pay_date/1000, 'unixepoch')) AS m, "
            "COUNT(*) AS cnt, SUM(pay_amount) AS amount FROM cases "
            f"WHERE {clause} AND pay_date IS NOT NULL GROUP BY m ORDER BY m"
        ),
        bind,
    ).mappings().all()
    lines = [
        "# 判赔与费用分析报告（T3）",
        "",
        f"- 年份范围：{params.get('year') or '全部'}",
        "",
        "## 四值总览",
        "",
        "| 指标 | 金额 | 说明 |",
        "| --- | --- | --- |",
        f"| 累计判赔 | ¥{v['amount']:,.2f}（{v['cnt']} 件） | 结案原因=判赔的支付金额合计 |",
        f"| 获赔（执行到位近似） | ¥{v['amount']:,.2f}（{v['paid']} 件有支付时间） | 判赔中支付时间存在 |",
        "| 支出 | — | 费用台账未接入（Phase 2 §2.5） |",
        "| 净费用 | — | 支出 − 获赔（支出缺失随之为空） |",
        "",
        "## 月度判赔",
        "",
        "| 月份 | 件数 | 金额 |",
        "| --- | --- | --- |",
        *[f"| {r['m']} | {r['cnt']} | ¥{r['amount']:,.2f}" for r in monthly],
        "",
        "> 口径：判赔 = 支付总金额（结案原因=判赔 子集）；与 07-fees 页四值完全同构。",
    ]
    return "判赔与费用分析报告（T3）", "\n".join(lines)


# ---------------------------------------------------------------- T4 对手方画像

def _t4_party(db: Session, params: dict) -> tuple[str, str]:
    name = (params.get("party") or "").strip()
    if not name:
        return "对手方画像报告", "> 错误：缺少 party 参数"
    needle = f"%{name}%"
    rows = db.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN resolve = :r THEN 1 ELSE 0 END) AS verdict_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount, "
            "SUM(CASE WHEN court NOT LIKE '%北京%' THEN 1 ELSE 0 END) AS offsite_count, "
            "AVG(CASE WHEN amount > 0 AND pay_amount IS NOT NULL THEN pay_amount / amount END) AS avg_support "
            "FROM cases WHERE defendant LIKE :needle"
        ),
        {"r": _VERDICT_RESOLVE, "needle": needle},
    ).mappings().one()
    cases = db.execute(
        text(
            "SELECT case_no, year, court, resolve, amount, pay_amount, case_status "
            "FROM cases WHERE defendant LIKE :needle ORDER BY id DESC LIMIT 20"
        ),
        {"needle": needle},
    ).mappings().all()
    lines = [
        f"# 对手方画像报告（T4）：{name}",
        "",
        "## 涉诉总览",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 累计涉诉 | {rows['total'] or 0} 件 |",
        f"| 判赔件数 | {rows['verdict_count'] or 0} 件 |",
        f"| 判赔总额 | ¥{rows['verdict_amount'] or 0:,.2f} |",
        f"| 异地管辖（近似） | {rows['offsite_count'] or 0} 件（court 不含「北京」） |",
        f"| 平均支持率（加权） | {_fmt(rows['avg_support'])} |",
        "",
        "## 近期案件明细（Top20）",
        "",
        "| 案号 | 年份 | 法院 | 结案原因 | 标的 | 支付额 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in cases:
        courts = c["court"]
        if isinstance(courts, str):
            try:
                courts = json.loads(courts)
            except (TypeError, ValueError):
                courts = None
        lines.append(
            f"| {c['case_no'] or '—'} | {c['year'] or '—'} | "
            f"{'、'.join(courts or []) or '—'} | {c['resolve'] or '—'} | "
            f"{_fmt(c['amount'])} | {_fmt(c['pay_amount'])} | {c['case_status'] or '—'} |"
        )
    lines.append("")
    lines.append("> 口径：对手方按被告 JSON 数组包含匹配；异地管辖为近似口径（注册地北京）。")
    return "对手方画像报告（T4）", "\n".join(lines)


# ---------------------------------------------------------------- T5 歌曲统计

def _t5_songs(db: Session, params: dict) -> tuple[str, str]:
    song = (params.get("song") or "").strip()
    song_where = ""
    bind: dict = {}
    if song:
        song_where = "WHERE s.song_name LIKE :psong"
        bind["psong"] = f"%{song}%"
    rows = db.execute(
        text(
            "SELECT s.song_name, s.artist, COUNT(sc.case_id) AS case_count, "
            "SUM(CASE WHEN c.resolve = :r THEN c.pay_amount ELSE 0 END) AS verdict_amount "
            "FROM songs s JOIN song_case sc ON sc.song_id = s.id "
            "LEFT JOIN cases c ON c.id = sc.case_id "
            f"{song_where} GROUP BY s.id ORDER BY case_count DESC LIMIT 50"
        ),
        {"r": _VERDICT_RESOLVE, **bind},
    ).mappings().all()
    per_song = db.execute(
        text(
            "SELECT COALESCE(SUM(pay_amount),0) / NULLIF(SUM(song_count),0) AS avg_per_song, "
            "SUM(song_count) AS total_slots FROM cases "
            "WHERE resolve = :r AND song_count IS NOT NULL AND song_count > 0"
        ),
        {"r": _VERDICT_RESOLVE},
    ).mappings().one()
    lines = [
        f"# 歌曲使用统计报告（T5）",
        "",
        f"- 过滤：{'歌曲含「' + song + '」' if song else '全部歌曲'}",
        "",
        "## 单曲判赔口径",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 平均单曲判赔 | ¥{per_song['avg_per_song'] or 0:,.2f} |",
        f"| 涉案歌曲槽位数 | {per_song['total_slots'] or 0} |",
        "",
        "## 高频歌曲 Top50",
        "",
        "| 歌曲 | 艺人 | 涉案件数 | 判赔合计 |",
        "| --- | --- | --- | --- |",
        *[f"| {r['song_name'] or '未命名歌曲'} | {r['artist'] or '—'} | {r['case_count']} | ¥{r['verdict_amount'] or 0:,.2f}" for r in rows],
        "",
        "> 口径：判赔合计 = 判赔案件支付金额；单曲判赔 = Σ支付额 ÷ Σ歌曲数（v1.0）。",
    ]
    return "歌曲使用统计报告（T5）", "\n".join(lines)


# ---------------------------------------------------------------- T6 同步健康

def _t6_sync_health(db: Session, params: dict) -> tuple[str, str]:
    jobs = db.scalars(select(SyncJob).order_by(SyncJob.id.desc()).limit(10)).all()
    dirty = db.execute(text(
        "SELECT COUNT(*) FROM cases WHERE dirty_flags IS NOT NULL AND dirty_flags != '[]'"
    )).scalar() or 0
    rules = db.scalars(select(CleanRule).where(CleanRule.version == "v1")).all()
    total = db.execute(text("SELECT COUNT(*) FROM cases")).scalar() or 0
    lines = [
        "# 同步健康报告（T6）",
        "",
        "## 数据概况",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 案件总量 | {total} |",
        f"| 脏标记案件 | {dirty} |",
        "",
        "## 最近同步作业（10 条）",
        "",
        "| 类型 | 状态 | 总数 | 新增 | 跳过 | 开始 | 完成 | 失败摘要 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for j in jobs:
        lines.append(
            f"| {j.job_type} | {j.status} | {j.total} | {j.upserted} | {j.skipped} | "
            f"{_fmt_date(j.started_at)} | {_fmt_date(j.finished_at)} | {j.error_brief or '—'} |"
        )
    lines.append("")
    lines.append("## 清洗规则启停（v1）")
    lines.append("")
    lines.append("| 规则 | 目标字段 | 状态 | 说明 |")
    lines.append("| --- | --- | --- | --- |")
    for r in rules:
        lines.append(f"| {r.rule_tag} | {r.target_field} | {'启用' if r.enabled else '停用'} | {r.description or '—'} |")
    lines.append("")
    lines.append("> 口径：脏标记 = dirty_flags 非空案件；同步作业以 sync_jobs 表为准。")
    return "同步健康报告（T6）", "\n".join(lines)


# ---------------------------------------------------------------- T7 口径复核

def _t7_metrics_audit(db: Session, params: dict) -> tuple[str, str]:
    key = (params.get("metric_key") or "").strip()
    metrics = [{m: r for m, r in zip(("key", "title", "value", "definition", "version", "footnote"),
                                     [r.get("key"), r.get("title"), r.get("value"), None, r.get("version"), r.get("footnote")])}
               for r in compute_overview(db)]
    if key:
        metrics = [m for m in metrics if m["key"] == key]
    lines = [
        "# 口径复核报告（T7）",
        "",
        f"- 口径版本：{','.join(metric_versions(db))}",
        "",
        "## 8 项指标当前值",
        "",
        "| 指标 | 值 | 版本 | 口径说明 |",
        "| --- | --- | --- | --- |",
    ]
    for m in metrics:
        value = m["value"]
        v_str = "—" if value is None else (f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append(f"| {m['title']} | {v_str} | {m['version'] or '—'} | {m['footnote'] or m['definition'] or '—'} |")
    lines.append("")
    lines.append("## 版本历史")
    lines.append("")
    for v in metric_versions(db):
        rows = db.scalars(select(MetricDef).where(MetricDef.version == v)).all()
        lines.append(f"### {v}")
        lines.append("")
        lines.append("| 指标 | 定义 |")
        lines.append("| --- | --- |")
        for mdef in rows:
            lines.append(f"| {mdef.title} | {mdef.definition or '—'} |")
        lines.append("")
    lines.append("> 口径：值来自 metric_defs.formula_sql 实时计算（与 08-metrics 页同源）。")
    return "口径复核报告（T7）", "\n".join(lines)