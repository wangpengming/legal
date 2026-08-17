"""8 项指标口径 v1.0 计算引擎（需求 4.3 + docs/03 §5 指标口径表）。

metric_defs 表为口径唯一数据源（title / definition / formula_sql / footnote 的 v1
快照由 app.models.seed 权威维护）；本模块负责：`{filters}` 占位替换（白名单 + 绑定
参数防注入）→ SQLite 执行 → 结构化结果，供 /stats/overview（t08-7）、08-metrics
页「SQL 断言 + 版本历史」复用。

口径基线（638 基线，seed settings.baseline）：胜诉率A 78.2% / 胜诉率B 71.2% /
支持率 6.4% / 判赔率 31.2% / 单曲 ¥870 / 结案周期 186 天 / 系列案系数 1.0 / 在办 42。
"""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.meta import MetricDef

# 8 项指标固定顺序（overview KPI 卡展示顺序即此）
METRIC_KEYS = [
    "win_rate_a",
    "win_rate_b",
    "support_rate",
    "verdict_rate",
    "per_song",
    "cycle",
    "series_coef",
    "open_count",
]

# 过滤白名单：仅允许枚举字典/维度字段等值过滤；值类型强制转换（非法入参直接忽略）
_FILTER_TYPES: dict[str, type] = {
    "biz_line": str,
    "year": int,
    "cause": str,
    "resolve": str,
    "case_status": str,
    "payer": str,
}


def _build_filters(filters: dict | None) -> tuple[str, dict]:
    """filters → (WHERE 片段「biz_line = :p0 AND year = :p1」, 命名参数 dict)。

    命名参数（SQLAlchemy text() 不支持 qmark 位置占位）；字段名来自白名单
    _FILTER_TYPES，非法键/非法类型一律忽略（防御，不报错）。
    """
    if not filters:
        return "", {}
    clause: list[str] = []
    params: dict = {}
    for i, (k, v) in enumerate(filters.items()):
        if k not in _FILTER_TYPES or v in (None, ""):
            continue
        try:
            typed = _FILTER_TYPES[k](v)
        except (TypeError, ValueError):
            continue  # 类型不合法 → 忽略该条件（防御，不报错）
        param = f"p{i}"
        clause.append(f"{k} = :{param}")
        params[param] = typed
    return " AND ".join(clause), params


def compute_metric(db: Session, key: str, filters: dict | None = None, version: str = "v1") -> dict | None:
    """单指标计算：metric_defs 表驱动 formula_sql + 口径元数据。

    返回 {key, title, value, definition, version, footnote}；value 为原始计算值
    （比例/金额/天数/计数，前端按口径格式化）；定义缺失或 SQL 无结果时返回 None。
    """
    metric = db.scalar(select(MetricDef).where(MetricDef.key == key, MetricDef.version == version))
    if metric is None or not metric.formula_sql:
        return None
    where, params = _build_filters(filters)
    sql = metric.formula_sql.replace("{filters}", where or "1=1")
    value = db.execute(text(sql), params).scalar()
    if isinstance(value, float):
        value = round(value, 4)  # 口径 v1.0：4 位小数（78.2% = 0.7820）
    return {
        "key": metric.key,
        "title": metric.title,
        "definition": metric.definition,
        "value": value,
        "version": metric.version,
        "footnote": metric.footnote,
    }


def compute_overview(db: Session, filters: dict | None = None) -> list[dict]:
    """overview KPI 卡：8 项指标全量计算（顺序 = METRIC_KEYS）。"""
    return [r for key in METRIC_KEYS if (r := compute_metric(db, key, filters)) is not None]


def metric_versions(db: Session) -> list[str]:
    """指标口径版本历史（08-metrics 页版本列表；回滚切旧版本快照）。"""
    rows = db.scalars(select(MetricDef.version).distinct()).all()
    return sorted(rows)