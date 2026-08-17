"""ORM 模型包（docs/03 §2 全量表）。

表：raw_cases / cases / songs / song_case / enum_dicts / clean_rules /
company_map / metric_defs / sync_jobs / sync_batches / audit_logs /
settings / tags / tag_links / external_cases / saved_views / reports +
FTS5 影子表 cases_fts（见 fts.py，不在 metadata 内）。
导入即注册进 Base.metadata（供 create_all）；seed_meta 供幂等种子。
"""
from app.models.fact import Case, RawCase, Song, SongCase, TimestampMixin
from app.models.meta import CleanRule, CompanyMap, EnumDict, MetricDef
from app.models.ops import (
    AuditLog,
    ExternalCase,
    Report,
    SavedView,
    Setting,
    SyncBatch,
    SyncJob,
    Tag,
    TagLink,
)
from app.models.seed import seed_meta

__all__ = [
    "Base",
    "RawCase",
    "Case",
    "Song",
    "SongCase",
    "TimestampMixin",
    "EnumDict",
    "CleanRule",
    "CompanyMap",
    "MetricDef",
    "SyncJob",
    "SyncBatch",
    "AuditLog",
    "Setting",
    "Tag",
    "TagLink",
    "ExternalCase",
    "SavedView",
    "Report",
    "seed_meta",
]

# Base 从 core 导入，保持 __all__ 稳定引用
from app.core.database import Base  # noqa: E402