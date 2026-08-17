"""数据库引擎基座。

docs/03 §1.1 决策：SQLite 单文件 + WAL（`journal_mode=WAL; synchronous=NORMAL;
foreign_keys=ON`）；写读分离（同步走 staging 表 → 事务原子换入正式表，查询只读
正式表，WAL 读快照永不阻塞）。
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import PROJECT_ROOT, get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """全部 ORM 模型的声明基类（模型定义见 app/models/）。"""


_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 依赖：每请求一个会话（请求结束即关）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表 + FTS 索引 + 幂等种子。

    决策 D1：应用启动 `create_all` 自建（638 条规模不上 alembic；重建即迁移）；
    字典/规则集版本化管理（enum_dicts / clean_rules / metric_defs）。
    """
    from app import models  # noqa: F401  确保模型类注册进 Base.metadata

    Base.metadata.create_all(bind=engine)
    # FTS5 影子表（不在 metadata；启动建索引 + 全量重建兜底，638 行秒级）
    from app.models.fts import init_fts, rebuild_cases_fts

    init_fts(engine)
    # 种子数据（字典基座 / 首版内置规则 / 指标口径 v1.0）由 app.models.seed 提供
    from app.models.seed import seed_meta

    with SessionLocal() as db:
        seed_meta(db)
        rebuild_cases_fts(db)  # 与索引字段同事务（cases 空表时无操作）
        db.commit()