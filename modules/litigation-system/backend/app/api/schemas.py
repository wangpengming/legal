"""API v1 公共契约（docs/03 §6.1 通用约定）。

- 响应包裹：{code:0, data, meta:{page,total,footnote}}（ok 助手）；
- 错误：FastAPI HTTPException → {code, message, detail}；
- 请求模型：search / sync / dicts / export / ai / batch；
- api 写操作审计助手（写操作与导出自动记 audit_logs，docs/03 §6.1）。
"""
from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.ops import AuditLog

FIELD_EQ_OPS = {"eq", "ne"}
FIELD_LIST_OPS = {"in", "nin"}
CONTAINS_OPS = {"contains"}
RANGE_OPS = {"range"}
SEARCH_OPS = FIELD_EQ_OPS | FIELD_LIST_OPS | CONTAINS_OPS | RANGE_OPS


def ok(data: Any = None, *, total: int | None = None, page: int | None = None,
       page_size: int | None = None, footnote: str | None = None) -> dict:
    """统一成功包裹 {code:0, data, meta}（meta 仅出现非空字段）。"""
    meta: dict[str, Any] = {}
    if total is not None:
        meta["total"] = total
    if page is not None:
        meta["page"] = page
    if page_size is not None:
        meta["page_size"] = page_size
    if footnote:
        meta["footnote"] = footnote
    return {"code": 0, "data": data, "meta": meta}


def audit(db: Session, *, op_type: str, table_name: str, action: str,
          detail: dict | str | None = None, record_id: str | None = None) -> None:
    """写操作审计（docs/03 §6.1：写操作/导出自动记 audit_logs）。"""
    db.add(
        AuditLog(
            op_type=op_type,
            table_name=table_name,
            action=action,
            detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            record_id=record_id,
            operator="api",
            created_at=int(time.time() * 1000),
        )
    )
    db.commit()


# ── 检索（POST /search，docs/03 §6.2） ───────────────────────────

class SearchFilter(BaseModel):
    field: str
    op: Literal["eq", "ne", "in", "nin", "contains", "range"]
    value: Any = None  # eq/ne/contains 单值
    values: list[Any] | None = None  # in/nin
    min: Any = None  # range
    max: Any = None  # range


class SearchSort(BaseModel):
    field: str
    desc: bool = False


class SearchRequest(BaseModel):
    q: str | None = None  # 全文检索（FTS5 / LIKE 兜底）
    filters: list[SearchFilter] = Field(default_factory=list)
    sorts: list[SearchSort] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    columns: list[str] | None = None  # 摘要列（None = 默认集合）


class CaseBatchRequest(BaseModel):
    ids: list[str]  # case record_id / int id 字符串均可
    action: Literal["export", "tag"]
    tag: str | None = None  # action=tag 时必填


# ── 同步（POST /sync/run，docs/03 §6.2） ─────────────────────────

class SyncRunRequest(BaseModel):
    type: Literal["full", "incremental", "record"] = "incremental"
    id: str | None = None  # type=record 时必填


# ── 字典/规则（POST /dicts & /dicts/test，docs/03 §4.3） ──────────

class DictWriteRequest(BaseModel):
    action: Literal["enum", "rule_toggle"]
    # — enum（维护枚举字典：aliases 追加原始选项→规范值映射） —
    field: str | None = None
    enum_key: str | None = None  # 规范值
    label: str | None = None
    color: str | None = None
    aliases: dict[str, str] | None = None  # {原始选项: 规范值}
    # — rule_toggle（R 规则启停；前端 11-dicts 页保存重跑前提） —
    rule_tag: str | None = None
    enabled: bool | None = None


class DictTestRequest(BaseModel):
    samples: list[dict]  # 单条案件字段模拟（不落库）
    rule_tags: list[str] | None = None  # None = 全部启用规则


class DirtyItemAction(BaseModel):
    action: Literal["adopt", "ignore", "edit"]
    value: str | None = None  # adopt/edit 的目标规范值


# ── 导出（POST /export，docs/03 §6.2） ───────────────────────────

class ExportRequest(BaseModel):
    scope: Literal["all", "search", "case"] = "all"
    columns: list[str] | None = None  # None = 默认全列
    format: Literal["csv", "xlsx"] = "csv"
    with_footnote: bool = True
    # scope=search：复用检索条件
    q: str | None = None
    filters: list[SearchFilter] = Field(default_factory=list)
    # scope=case：指定案件
    ids: list[str] = Field(default_factory=list)


# ── AI Mode A（POST /ai/query；Phase 0 本地检索 v1，Phase 3 升级 SSE） ──

class AiQueryRequest(BaseModel):
    session_id: str | None = None
    question: str


class AiChatRequest(BaseModel):
    """Mode A 对话请求（Phase 3）：mode=A 检索问答 / mode=B 报告生成入口。"""

    session_id: str | None = None
    mode: Literal["A", "B"] = "A"
    question: str = ""


class AiReportTemplateResult(BaseModel):
    key: str
    title: str
    description: str
    params: list[str]
    output: str


# ── 报告 Mode B（POST /reports/generate，Phase 3） ────────────────

class ReportGenerateRequest(BaseModel):
    template_key: str  # T1~T7
    params: dict[str, str] = Field(default_factory=dict)
    created_by: str | None = None


# ── 标签 M4（/tags，Phase 2） ────────────────────────────────────

class TagWriteRequest(BaseModel):
    name: str
    kind: Literal["manual", "derived"] = "manual"
    color: str | None = None
    description: str | None = None


class TagUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    description: str | None = None


class TagLinkRequest(BaseModel):
    """打标/取消关联：tag_id 与 tag_name 二选一（tag_name 不存在自动创建）。"""

    tag_id: int | None = None
    tag_name: str | None = None
    target_type: Literal["case", "song", "party", "external_case"]
    target_id: str
    link: bool = True  # True=打标，False=取消


class TagMergeRequest(BaseModel):
    from_id: int
    into_id: int


class TagBatchLinkRequest(BaseModel):
    """批量打标（02-search 表格进阶批量操作 / 详情页多选）。"""

    tag_name: str
    target_type: Literal["case", "song", "party", "external_case"]
    target_ids: list[str]  # 业务 record_id 列表