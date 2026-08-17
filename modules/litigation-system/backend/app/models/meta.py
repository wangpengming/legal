"""字典与规则表（docs/03 §2.3~2.4）：驱动前端动态渲染 + 清洗管道表驱动。"""
from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnumDict(Base):
    """枚举字典（field/enum_key 唯一；版本化管理，运行期 schema 同步增量补录）。

    aliases = 飞书选项 → 规范值映射 JSON（合并项在此，如「原告撤诉(重复)」）。
    """

    __tablename__ = "enum_dicts"
    __table_args__ = (UniqueConstraint("field", "enum_key", name="uq_enum_dict"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    enum_key: Mapped[str] = mapped_column(String(128), nullable=False)  # 规范值
    label: Mapped[str | None] = mapped_column(String(128))
    aliases: Mapped[dict | None] = mapped_column(Text)  # JSON：{原始选项: 规范值}
    color: Mapped[str | None] = mapped_column(String(32))  # 语义色名（前端 token）
    sort: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)


class CleanRule(Base):
    """清洗规则表（UI 可维护；整包版本发布可回滚）。

    rule_type 枚举：normalize_enum / company_map / regex_replace /
    extract_year / split_court / de_dup / null_mark / amount_guard。
    """

    __tablename__ = "clean_rules"
    __table_args__ = (UniqueConstraint("rule_tag", "version", name="uq_clean_rule_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_tag: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # R01~R06
    version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)
    target_field: Mapped[str] = mapped_column(String(64), nullable=False)  # 作用字段（* = 全部枚举字段）
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern: Mapped[str | None] = mapped_column(Text)  # 正则/匹配串
    replacement: Mapped[str | None] = mapped_column(Text)  # 替换值/映射目标
    mapped: Mapped[dict | None] = mapped_column(Text)  # JSON：批量映射（R05 别名表）
    priority: Mapped[int] = mapped_column(Integer, default=100)  # 执行顺序（小者先）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)  # 审计展示


class CompanyMap(Base):
    """公司名归一表（独立便于维护；首版内置见 seed）。"""

    __tablename__ = "company_map"
    __table_args__ = (UniqueConstraint("company_raw", name="uq_company_map"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), default="seed")  # seed / 人工采纳
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MetricDef(Base):
    """指标口径中心唯一数据源（驱动 /metrics 与全站脚注）。"""

    __tablename__ = "metric_defs"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_metric_def_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)  # 需求 4.3 操作化原文
    version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)  # 当前有效版本
    formula_sql: Mapped[str | None] = mapped_column(Text)  # 计算 SQL（口径引擎执行）
    affected_pages: Mapped[list | None] = mapped_column(Text)  # JSON：影响页面清单
    sample_n: Mapped[int | None] = mapped_column(Integer)  # 最近一次计算样本数（随计算刷新）
    footnote: Mapped[str | None] = mapped_column(Text)  # 口径脚注（导出/展示强制带）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


def _json_dict(value: dict[str, Any] | None = None) -> str:
    """便捷序列化辅助（模型层不直接使用，保留给工具/种子）。"""
    import json

    return json.dumps(value or {}, ensure_ascii=False)