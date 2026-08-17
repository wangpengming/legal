"""统计端点（docs/03 §6.2：/stats/overview|party|bizline|songs|fees）。

口径说明（基线 638 条，docs/04 G8-01 真值）：
- overview：8 项指标（stats.metrics 口径引擎复用）+ 判赔趋势（按收案年份）× 业务线构成 +
  未来开庭日程（court_date >= 当前时刻）；
- party：被告画像（defendant JSON 数组包含匹配）；异地管辖为近似口径
  （court 数组不含「北京」即异地，原告音集协注册地在北京，footnote 声明）；
- fees：判赔 = 结案原因「判赔」的支付金额合计（G8-01：¥1,284,600/41 件）；
  获赔 = 判赔中支付时间存在（执行到位近似，原型 07-fees 口径）；支出 = 台账缺失置
  None 并标注（费用台账表 Phase 2 接入，见 docs/03 §2.5）；净费用 = 支出 − 获赔；
  存疑清单 = dirty_flags 含金额相关字段（amount/pay_amount）的案件。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import ok
from app.core.database import get_db
from app.stats.metrics import compute_overview, metric_versions

router = APIRouter(tags=["stats"])

# 判赔口径：结案原因 = 判赔（其余 314 类结案原因不计入判赔统计）
_VERDICT_RESOLVE = "判赔"
# 胜诉率口径 A（与 metrics.win_rate_a formula_sql 一致）：胜=胜诉类结案 / 败=判赔 / 待定=其余
_WIN_RESOLVES = ("胜诉", "驳回上诉维持原判", "判决驳回对雷石的诉求",
                 "裁定驳回雷石的诉讼请求", "裁定驳回对雷石的诉讼请求")
_LOSE_RESOLVES = ("判赔",)
# 异地管辖近似口径：court 数组不含「北京」（原告音集协注册地）→ 异地
_OFFSITE_NOT_CONTAINS = "北京"
# 金额相关脏字段（fees 存疑清单：这些字段的标记影响费用口径可信度）
_FEE_DIRTY_FIELDS = ("amount", "pay_amount", "per_song_amount", "lawyer_fee")


def _load_json(v) -> list | None:
    if not v or not isinstance(v, str):
        return None
    try:
        r = json.loads(v)
        return r if isinstance(r, list) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- GET /stats/overview

@router.get("/stats/overview")
def stats_overview(db: Session = Depends(get_db)) -> dict:
    """01-overview 页数据：8 KPI + 判赔趋势 + 业务线构成 + 未来开庭日程。"""
    kpis = compute_overview(db)
    trend = db.execute(
        text(
            "SELECT year, COUNT(*) AS case_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount "
            "FROM cases WHERE year IS NOT NULL GROUP BY year ORDER BY year"
        ),
        {"r": _VERDICT_RESOLVE},
    ).mappings().all()
    biz = db.execute(
        text(
            "SELECT biz_line, COUNT(*) AS case_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount "
            "FROM cases WHERE biz_line IS NOT NULL "
            "GROUP BY biz_line ORDER BY case_count DESC"
        ),
        {"r": _VERDICT_RESOLVE},
    ).mappings().all()
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    upcoming = db.execute(
        text(
            "SELECT record_id, case_no, court_date, year, resolve FROM cases "
            "WHERE court_date IS NOT NULL AND court_date >= :now ORDER BY court_date LIMIT 20"
        ),
        {"now": now},
    ).mappings().all()
    # 摘要聚合（01-overview hero 数字：全库/音集协/本月新收/判赔累计，G8-01 真值对齐）
    acmc = db.execute(
        text("SELECT COUNT(*) FROM cases WHERE plaintiff LIKE :p"), {"p": "%音集协%"}
    ).scalar() or 0
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    monthly_new = db.execute(
        text(
            "SELECT COUNT(*) FROM cases "
            "WHERE accept_date IS NOT NULL AND strftime('%Y-%m', datetime(accept_date/1000, 'unixepoch')) = :m"
        ),
        {"m": month_prefix},
    ).scalar() or 0
    verdict_total = db.execute(
        text("SELECT COALESCE(SUM(pay_amount), 0) FROM cases WHERE resolve = :r"),
        {"r": _VERDICT_RESOLVE},
    ).scalar() or 0
    return ok(
        {
            "kpis": [
                {k: v for k, v in m.items() if k in ("key", "title", "value", "definition", "version")}
                for m in kpis
            ],
            "metric_versions": metric_versions(db),
            "trend": [dict(r) for r in trend],
            "bizline": [dict(r) for r in biz],
            "upcoming_court": [dict(r) for r in upcoming],
            "summary": {
                "total_cases": db.execute(text("SELECT COUNT(*) FROM cases")).scalar() or 0,
                "acmc_cases": acmc,
                "monthly_new": monthly_new,
                "verdict_total": round(float(verdict_total), 2),
            },
        },
        footnote="指标口径 v1.0（versions 见 /metadata）；判赔趋势按收案年份，判赔 = 结案原因「判赔」的支付金额合计",
    )


# ---------------------------------------------------------------- GET /stats/parties（主体清单）

@router.get("/stats/parties")
def stats_parties(limit: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db)) -> dict:
    """04-parties 主体清单：defendant JSON 数组扁平化聚合 top N（按案件数倒序）。

    每个被告名聚合项含案件数 / 胜诉类与判赔计数 / 判赔额 / 异地管辖数（近似口径）/ 业务线 / 年份跨度。
    """
    rows = db.execute(
        text(
            "SELECT defendant, year, court, resolve, pay_amount, biz_line FROM cases "
            "WHERE defendant IS NOT NULL AND defendant != ''"
        )
    ).mappings().all()
    total = len(rows)
    agg: dict[str, dict] = {}
    for r in rows:
        names = _load_json(r["defendant"])
        if not names:
            continue
        for raw in names:
            name = str(raw).strip()
            if not name:
                continue
            a = agg.setdefault(
                name,
                {"case_count": 0, "win": 0, "lose": 0, "verdict_count": 0,
                 "verdict_amount": 0.0, "offsite": 0, "biz": set(), "years": set()},
            )
            a["case_count"] += 1
            if r["resolve"] == _VERDICT_RESOLVE:
                a["verdict_count"] += 1
                a["verdict_amount"] += r["pay_amount"] or 0
            if r["resolve"] in _WIN_RESOLVES:
                a["win"] += 1
            elif r["resolve"] in _LOSE_RESOLVES:
                a["lose"] += 1
            court = _load_json(r["court"])
            if court and not any(_OFFSITE_NOT_CONTAINS in c for c in court):
                a["offsite"] += 1
            if r["biz_line"]:
                a["biz"].add(r["biz_line"])
            if r["year"] is not None:
                a["years"].add(r["year"])
    items = [
        {
            "name": name,
            "case_count": a["case_count"],
            "win_count": a["win"],
            "lose_count": a["lose"],
            "win_rate_a": round(a["win"] / (a["win"] + a["lose"]), 4)
                if a["win"] + a["lose"] else None,
            "verdict_count": a["verdict_count"],
            "verdict_amount": round(a["verdict_amount"], 2),
            "offsite_count": a["offsite"],
            "biz_lines": sorted(a["biz"]),
            "first_year": min((y for y in a["years"] if y and y > 1900), default=None),
            "last_year": max((y for y in a["years"] if y and y > 1900), default=None),
            "share": round(a["case_count"] / total, 4) if total else None,
        }
        for name, a in agg.items()
    ]
    items.sort(key=lambda x: (x["case_count"], x["verdict_amount"]), reverse=True)
    return ok(
        {"items": items[:limit], "total_parties": len(items), "covered_cases": total},
        footnote="主体清单：被告 JSON 数组扁平化聚合；胜诉率A = 胜诉类/(胜诉类+判赔)；异地 = court 数组不含「北京」",
    )


# ---------------------------------------------------------------- GET /stats/party（单体画像）

@router.get("/stats/party")
def stats_party(name: str = Query(..., description="被告名称（JSON 数组包含匹配）"),
                db: Session = Depends(get_db)) -> dict:
    """04-parties 被告画像：案件数 / 判赔件数与总额 / 异地管辖件数（近似口径）+
    年份分布 / 案由分布 / 我方胜诉率A（G5-02 画像详情）。"""
    if not name or not name.strip():
        raise HTTPException(status_code=422, detail="name 必填（被告名称）")
    needle = f"%{name.strip()}%"
    rows = db.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN resolve = :r THEN 1 ELSE 0 END) AS verdict_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount, "
            "SUM(CASE WHEN plaintiff IS NOT NULL THEN 1 ELSE 0 END) AS with_plaintiff, "
            "SUM(CASE WHEN court NOT LIKE '%' || :q || '%' THEN 1 ELSE 0 END) AS offsite_count "
            "FROM cases WHERE defendant LIKE :needle"
        ),
        {"r": _VERDICT_RESOLVE, "q": _OFFSITE_NOT_CONTAINS, "needle": needle},
    ).mappings().one()
    # 胜诉率A（metrics.win_rate_a 同口径子集）
    wr = db.execute(
        text(
            "SELECT SUM(CASE WHEN resolve IN (:w1, :w2, :w3, :w4, :w5) THEN 1 ELSE 0 END) AS win, "
            "SUM(CASE WHEN resolve IN (:l1) THEN 1 ELSE 0 END) AS lose "
            "FROM cases WHERE defendant LIKE :needle AND resolve IS NOT NULL"
        ),
        {"w1": _WIN_RESOLVES[0], "w2": _WIN_RESOLVES[1], "w3": _WIN_RESOLVES[2],
         "w4": _WIN_RESOLVES[3], "w5": _WIN_RESOLVES[4], "l1": _LOSE_RESOLVES[0],
         "needle": needle},
    ).mappings().one()
    win_sum = (wr["win"] or 0) + (wr["lose"] or 0)
    win_rate_a = round(wr["win"] / win_sum, 4) if win_sum else None
    # 年份分布（G5-02 涉案年份分布）
    years = db.execute(
        text(
            "SELECT year, COUNT(*) AS case_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount "
            "FROM cases WHERE defendant LIKE :needle AND year IS NOT NULL "
            "GROUP BY year ORDER BY year"
        ),
        {"r": _VERDICT_RESOLVE, "needle": needle},
    ).mappings().all()
    # 案由分布（G5-02 案由分布）
    causes = db.execute(
        text(
            "SELECT cause, COUNT(*) AS case_count, "
            "SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount "
            "FROM cases WHERE defendant LIKE :needle AND cause IS NOT NULL "
            "GROUP BY cause ORDER BY case_count DESC, cause"
        ),
        {"r": _VERDICT_RESOLVE, "needle": needle},
    ).mappings().all()
    recent = db.execute(
        text(
            "SELECT record_id, case_no, year, court, resolve, amount, pay_amount, case_status, "
            "biz_line, cause, support_rate "
            "FROM cases WHERE defendant LIKE :needle ORDER BY id DESC LIMIT 50"
        ),
        {"needle": needle},
    ).mappings().all()
    return ok(
        {
            "name": name,
            "total": rows["total"] or 0,
            "verdict_count": rows["verdict_count"] or 0,
            "verdict_amount": round(rows["verdict_amount"] or 0, 2),
            "offsite_count": rows["offsite_count"] or 0,
            "win_rate_a": win_rate_a,
            "years": [dict(r) for r in years],
            "causes": [dict(r) for r in causes],
            "cases": [dict(r) | {"court": _load_json(r["court"])} for r in recent],
        },
        footnote="异地管辖近似口径：court 数组不含「北京」即异地（原告音集协注册地北京）；判赔 = 结案原因「判赔」的支付金额合计；胜诉率A 与指标中心 win_rate_a 同口径",
    )


# ---------------------------------------------------------------- GET /stats/bizline

@router.get("/stats/bizline")
def stats_bizline(year: int | None = Query(None, description="收案年份过滤"),
                  db: Session = Depends(get_db)) -> dict:
    """业务线 × 年份分布（08 业务线分布热力）。"""
    where = "WHERE biz_line IS NOT NULL"
    params: dict = {}
    if year is not None:
        where += " AND year = :year"
        params["year"] = year
    rows = db.execute(
        text(
            f"SELECT biz_line, year, COUNT(*) AS case_count, "
            f"SUM(CASE WHEN resolve = :r THEN pay_amount ELSE 0 END) AS verdict_amount, "
            f"SUM(CASE WHEN year IS NOT NULL THEN 1 ELSE 0 END) AS with_year "
            f"FROM cases {where} GROUP BY biz_line, year ORDER BY biz_line, year"
        ),
        {"r": _VERDICT_RESOLVE, **params},
    ).mappings().all()
    return ok(
        {"year": year, "items": [dict(r) for r in rows]},
        footnote="业务线 × 收案年份交叉聚合；判赔 = 结案原因「判赔」的支付金额合计",
    )


# ---------------------------------------------------------------- GET /stats/songs

@router.get("/stats/songs")
def stats_songs(db: Session = Depends(get_db)) -> dict:
    """06-songs 歌曲画像：涉案歌曲 / 艺人聚合 + 单曲判赔指标（口诀 ¥870 口径）。"""
    songs = db.execute(
        text(
            "SELECT s.record_id AS song_id, s.song_name, s.artist, "
            "COUNT(sc.case_id) AS case_count, "
            "SUM(CASE WHEN c.resolve = :r THEN c.pay_amount ELSE 0 END) AS verdict_amount "
            "FROM songs s JOIN song_case sc ON sc.song_id = s.id "
            "LEFT JOIN cases c ON c.id = sc.case_id "
            "GROUP BY s.id ORDER BY case_count DESC LIMIT 50"
        ),
        {"r": _VERDICT_RESOLVE},
    ).mappings().all()
    per_song = db.execute(
        text(
            "SELECT COALESCE(SUM(pay_amount), 0) / NULLIF(SUM(song_count), 0) AS avg_per_song, "
            "SUM(song_count) AS total_song_slots, COUNT(*) AS case_count "
            "FROM cases WHERE resolve = :r AND song_count IS NOT NULL AND song_count > 0"
        ),
        {"r": _VERDICT_RESOLVE},
    ).mappings().one()
    return ok(
        {
            "songs": [dict(r) for r in songs],
            "aggregate": {
                "avg_per_song": round(per_song["avg_per_song"] or 0, 2),
                "total_song_slots": per_song["total_song_slots"] or 0,
                "case_count": per_song["case_count"] or 0,
            },
            "metric": next(
                (m for m in compute_overview(db) if m["key"] == "per_song"), None
            ),
        },
        footnote="单曲判赔口径 v1.0：判赔案件支付金额合计 ÷ 涉案歌曲数合计（¥870/首基线）；歌曲画像按涉及案件数排序",
    )


# ---------------------------------------------------------------- GET /stats/fees

@router.get("/stats/fees")
def stats_fees(year: int | None = Query(None, description="收案年份过滤"),
               db: Session = Depends(get_db)) -> dict:
    """07-fees 费用看板四值：判赔 / 获赔 / 支出 / 净费用 + 月度分布 + 存疑清单。

    判赔 = 结案原因「判赔」支付金额合计；获赔 = 判赔中支付时间存在（执行到位近似）；
    支出 = 费用台账（Phase 2 表接入，当前账号数据缺失置 None + 标注）；
    净费用 = 支出 − 获赔（支出缺失时同样缺失）。存疑 = 金额相关脏标记案件。
    """
    where = "resolve = :r"
    params: dict = {"r": _VERDICT_RESOLVE}
    if year is not None:
        where += " AND year = :year"
        params["year"] = year
    rows = db.execute(
        text(
            f"SELECT COUNT(*) AS cnt, COALESCE(SUM(pay_amount), 0) AS amount, "
            f"COUNT(pay_date) AS paid FROM cases WHERE {where}"
        ),
        params,
    ).mappings().one()
    verdict_count, verdict_amount, paid_count = rows["cnt"], rows["amount"], rows["paid"]
    monthly = db.execute(
        text(
            "SELECT strftime('%Y-%m', datetime(pay_date/1000, 'unixepoch')) AS m, "
            "COUNT(*) AS cnt, SUM(pay_amount) AS amount "
            f"FROM cases WHERE {where} AND pay_date IS NOT NULL "
            "GROUP BY m ORDER BY m"
        ),
        params,
    ).mappings().all()
    # 存疑清单：金额相关字段 dirty_flags 命中（dirty_flags JSON 文本包含字段名）
    dirty_where = " OR ".join(f"dirty_flags LIKE '%\"{f}\"%'" for f in _FEE_DIRTY_FIELDS)
    dubious = db.execute(
        text(
            "SELECT record_id, case_no, year, resolve, amount, pay_amount, dirty_flags "
            f"FROM cases WHERE ({dirty_where}) LIMIT 100"
        )
    ).mappings().all()
    verdict_amount_f = round(verdict_amount, 2) if verdict_amount else 0.0
    expense = None  # 台账缺失：Phase 2 接入费用台账表（docs/03 §2.5）
    net = None if expense is None else round(expense - verdict_amount_f, 2)
    return ok(
        {
            "year": year,
            "four": {
                "verdict": {"amount": verdict_amount_f, "count": verdict_count},
                "recovered": {"amount": None if paid_count is None else verdict_amount_f,
                              "count": paid_count,
                              "hint": "获赔 = 判赔中支付时间存在（执行到位近似；台账口径 Phase 2 细化）"},
                "expense": {"amount": expense, "count": None,
                            "hint": "费用台账未接入（Phase 2 §2.5），当前不可得"},
                "net": {"amount": net, "hint": "净费用 = 支出 − 获赔（支出缺失随之为空）"},
            },
            "monthly": [dict(r) for r in monthly],
            "dubious": [
                {k: (json.loads(r["dirty_flags"]) if k == "dirty_flags" and isinstance(r[k], str) else r[k])
                 for k in ("record_id", "case_no", "year", "resolve", "amount", "pay_amount", "dirty_flags")}
                for r in dubious
            ],
        },
        footnote="费用口径（原型 07-fees）：判赔 = 结案原因「判赔」支付金额合计；获赔 = 支付时间存在近似；支出 = 台账缺失；存疑 = 金额字段脏标记案件",
    )


# ---------------------------------------------------------------- GET /stats/analysis（多维热力 + 下钻）

# 三维分析矩阵（维度键 → {行字段, 列字段}；列字段为 year 时过滤脏值 year=-1）
_ANALYSIS_DIMS = {
    "bizYear": {"row": "biz_line", "col": "year"},
    "causeYear": {"row": "cause", "col": "year"},
    "payerStatus": {"row": "payer", "col": "case_status"},
}
_ANALYSIS_LABELS = {
    "bizYear": ("业务线", "年份"),
    "causeYear": ("案由", "年份"),
    "payerStatus": ("支付主体", "案件状态"),
}


def _analysis_where(dim_info: dict) -> tuple[str, dict]:
    """构造热力矩阵的行/列非空过滤（year 列剔除脏值 year=-1）。"""
    row, col = dim_info["row"], dim_info["col"]
    clauses = [f"{row} IS NOT NULL AND {row} != ''"]
    params: dict = {}
    if col == "year":
        clauses.append("year IS NOT NULL AND year > 1900")
    else:
        clauses.append(f"{col} IS NOT NULL AND {col} != ''")
    return " AND ".join(clauses), params


@router.get("/stats/analysis")
def stats_analysis(dim: str = Query("bizYear", description="bizYear|causeYear|payerStatus"),
                   db: Session = Depends(get_db)) -> dict:
    """05-analysis 多维热力矩阵：{行} × {列} 案件数 + 判赔占比（G6）。

    cells[row_i][col_j] = {case_count, verdict_count, verdict_rate}；
    rows 按案件数降序（命中度高的维度在前），cols 年份升序 / 状态按频次降序。
    判赔口径与指标中心一致（结案原因 = 判赔）；year=-1 脏值剔除。
    """
    info = _ANALYSIS_DIMS.get(dim)
    if not info:
        raise HTTPException(status_code=422, detail=f"未知分析维度：{dim}（可选 bizYear/causeYear/payerStatus）")
    row, col = info["row"], info["col"]
    where, _ = _analysis_where(info)
    rows = db.execute(
        text(f"SELECT {row} AS v, COUNT(*) AS cnt FROM cases WHERE {where} "
             f"GROUP BY v ORDER BY cnt DESC, v LIMIT 40")
    ).mappings().all()
    col_order = "cnt DESC, v" if col == "case_status" else "v"
    cols = db.execute(
        text(f"SELECT {col} AS v, COUNT(*) AS cnt FROM cases WHERE {where} "
             f"GROUP BY v ORDER BY {col_order} LIMIT 40")
    ).mappings().all()
    cell_rows = db.execute(
        text(f"SELECT {row} AS rv, {col} AS cv, COUNT(*) AS case_count, "
             f"SUM(CASE WHEN resolve = :r THEN 1 ELSE 0 END) AS verdict_count "
             f"FROM cases WHERE {where} GROUP BY rv, cv"),
        {"r": _VERDICT_RESOLVE},
    ).mappings().all()
    index = {(r["rv"], str(r["cv"])): r for r in cell_rows}
    row_names = [r["v"] for r in rows]
    col_names = [str(c["v"]) for c in cols]
    cells = []
    for rv in row_names:
        line = []
        for cv_raw in col_names:
            hit = index.get((rv, cv_raw))
            if not hit:
                line.append({"case_count": 0, "verdict_count": 0, "verdict_rate": 0.0})
                continue
            cc, vc = hit["case_count"], hit["verdict_count"]
            line.append({
                "case_count": cc,
                "verdict_count": vc,
                "verdict_rate": round(vc / cc, 4) if cc else 0.0,
            })
        cells.append(line)
    total = db.execute(text(f"SELECT COUNT(*) AS n FROM cases WHERE {where}")).scalar_one()
    row_label, col_label = _ANALYSIS_LABELS[dim]
    return ok(
        {
            "dim": dim,
            "row_label": row_label,
            "col_label": col_label,
            "rows": row_names,
            "cols": col_names,
            "cells": cells,
            "total_cases": total,
        },
        footnote=f"聚合口径：{row_label}=字段精确匹配 · {col_label}=收案{'年份' if col == 'year' else '状态字段'} · 判赔占比=结案原因「判赔」 · 口径 v1.0",
    )


@router.get("/stats/analysis/drill")
def stats_analysis_drill(dim: str = Query("bizYear"),
                         x: str = Query(..., description="行维度值（如业务线）"),
                         col: str = Query("", description="列维度值（年份或状态，空=全部）"),
                         cause: str = Query("", description="案由二次下钻，空=不限"),
                         db: Session = Depends(get_db)) -> dict:
    """热力下钻（G6）：命中 {dim} 行 {x}（+列 col / 案由 cause）的案件明细与案由分布。"""
    info = _ANALYSIS_DIMS.get(dim)
    if not info:
        raise HTTPException(status_code=422, detail=f"未知分析维度：{dim}")
    row, col_field = info["row"], info["col"]
    where, params = _analysis_where(info)
    where += " AND {row} = :x".format(row=row)
    params["x"] = x
    if col:
        where += f" AND {col_field} = :col"
        params["col"] = int(col) if col_field == "year" else col
    if cause:
        where += " AND cause = :cause"
        params["cause"] = cause
    items = db.execute(
        text("SELECT record_id, case_no, year, defendant, court, resolve, amount, pay_amount, "
             "cause, biz_line, case_status, support_rate, payer FROM cases WHERE " + where +
             " ORDER BY year, record_id LIMIT 200"),
        params,
    ).mappings().all()
    total = db.execute(
        text("SELECT COUNT(*) AS n FROM cases WHERE " + where), params
    ).scalar_one()
    causes = []
    if dim != "causeYear":  # causeYear 下行即案由，不再二次聚合
        cause_rows = db.execute(
            text("SELECT cause AS c, COUNT(*) AS cnt FROM cases WHERE " + where +
                 " AND cause IS NOT NULL AND cause != '' GROUP BY c ORDER BY cnt DESC, c LIMIT 30"),
            params,
        ).mappings().all()
        causes = [{"cause": r["c"], "case_count": r["cnt"]} for r in cause_rows]
    flat = []
    for r in items:
        flat.append({
            "record_id": r["record_id"],
            "case_no": r["case_no"],
            "year": r["year"],
            "defendant": _load_json(r["defendant"]),
            "court": _load_json(r["court"]),
            "resolve": r["resolve"],
            "amount": r["amount"],
            "pay_amount": r["pay_amount"],
            "cause": r["cause"],
            "biz_line": r["biz_line"],
            "case_status": r["case_status"],
            "support_rate": r["support_rate"],
            "payer": r["payer"],
        })
    return ok(
        {
            "x": x,
            "dim": dim,
            "col": int(col) if col_field == "year" and col else col,
            "cause": cause or None,
            "items": flat,
            "total": total,
            "causes": causes,
        },
        footnote="下钻口径：命中行/列/案由条件案件明细 · 案由聚合用于二次下钻 · 数据截至最近同步",
    )