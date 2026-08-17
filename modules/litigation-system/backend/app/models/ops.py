"""运维、审计与配置表（docs/03 §2.4 其余表）。

- sync_jobs / sync_batches：同步任务主/明细（增量游标 last_sync_at 驱动）；
- audit_logs：清洗回放 + API 写操作审计（需求 4.2「清洗可回放」）；
- settings：KV 配置（口径版本指针 / 规则版本快照）；
- tags / tag_links：案件/歌曲/对手方标签体系（Phase 2 M4）；
- external_cases：外部案例库入库（Phase 2/3 网上判决数据源，§7.2）；
- saved_views / reports：保存筛选视图 / AI 报告（Phase 1/3）。
"""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.fact import TimestampMixin


class SyncJob(Base, TimestampMixin):
    """同步任务主记录（status 状态机：running → success/failed）。"""

    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # full / incremental / schema
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # running / success / failed
    started_at: Mapped[int | None] = mapped_column(Integer)
    finished_at: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer, default=0)  # 源侧记录数
    upserted: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)  # 幂等跳过（hash 未变）
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    error_brief: Mapped[str | None] = mapped_column(Text)  # 失败摘要（不存完整堆栈）
    last_sync_at: Mapped[int | None] = mapped_column(Integer)  # 增量游标（utc epoch_ms，成功时推进）
    lock_token: Mapped[str | None] = mapped_column(String(64))  # 并发锁：单任务未结束时多次触发直接拒


class SyncBatch(Base):
    """同步批次明细（一次分页拉取 = 一行）。"""

    __tablename__ = "sync_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    page_token: Mapped[str | None] = mapped_column(String(255))  # 续拉游标
    fetched: Mapped[int] = mapped_column(Integer, default=0)  # 本页取回数
    has_more: Mapped[bool | None] = mapped_column(Boolean)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """审计日志（清洗回放 / 同步 / API 写操作三类共用）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    op_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # clean / sync / api / export
    table_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # cases / enum_dicts / ...
    record_id: Mapped[str | None] = mapped_column(String(64))  # 业务键（record_id / 规则 id）
    rule_tag: Mapped[str | None] = mapped_column(String(16))  # 若由清洗触发：R01~R10
    rule_version: Mapped[str | None] = mapped_column(String(16))  # 规则包版本
    field: Mapped[str | None] = mapped_column(String(64))  # 目标字段
    old_value: Mapped[str | None] = mapped_column(Text)  # 原值（JSON 序列化）
    new_value: Mapped[str | None] = mapped_column(Text)  # 新值
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # upsert / mark_dirty / rollback / ...
    detail: Mapped[str | None] = mapped_column(Text)  # JSON 补充（批号、页、耗时、请求摘要）
    operator: Mapped[str | None] = mapped_column(String(64))  # system / api 调用者
    created_at: Mapped[int] = mapped_column(Integer, index=True)  # utc epoch_ms


class Setting(Base):
    """KV 配置（版本指针等；值任意 JSON 序列化）。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    updated_at: Mapped[int] = mapped_column(Integer)


class Tag(Base, TimestampMixin):
    """标签（M4 体系：人工/派生两类）。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)  # manual / derived
    color: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)


class TagLink(Base, TimestampMixin):
    """标签↔对象多态关联（case / song / party / external_case）。"""

    __tablename__ = "tag_links"
    __table_args__ = (UniqueConstraint("tag_id", "target_type", "target_id", name="uq_tag_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)  # 业务 record_id
    # created_at/updated_at 由 TimestampMixin 提供（default=_now_ms）


class ExternalCase(Base, TimestampMixin):
    """外部案例库（网上判决数据源入库；§7.2 三源交叉验证事实源之一）。"""

    __tablename__ = "external_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # 判决网 / 裁判文书网 / ...
    source_id: Mapped[str | None] = mapped_column(String(128), index=True)  # 源站唯一键（幂等）
    case_no: Mapped[str | None] = mapped_column(String(255), index=True)
    court: Mapped[str | None] = mapped_column(String(255))
    cause: Mapped[str | None] = mapped_column(String(128))
    judgment_date: Mapped[int | None] = mapped_column(Integer)  # epoch_ms
    defendant: Mapped[str | None] = mapped_column(String(255))
    song: Mapped[str | None] = mapped_column(String(255))  # 涉及歌曲（抽取）
    amount: Mapped[float | None] = mapped_column(Float)  # 判赔额
    verdict: Mapped[str | None] = mapped_column(String(255))  # 判决结果摘要
    summary: Mapped[str | None] = mapped_column(Text)  # 人工/LLM 摘要（FTS 索引）
    url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[int | None] = mapped_column(Integer)


class SavedView(Base, TimestampMixin):
    """保存的检索/筛选视图（Phase 1 02-search 收藏）。"""

    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON：筛选条件快照
    created_by: Mapped[str | None] = mapped_column(String(64))


class Report(Base, TimestampMixin):
    """AI/模板报告产物（Phase 3 Mode B）。"""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_key: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # T1~T7
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown
    params_json: Mapped[str | None] = mapped_column(Text)  # 生成参数
    created_by: Mapped[str | None] = mapped_column(String(64))