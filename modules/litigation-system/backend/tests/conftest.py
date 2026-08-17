"""pytest 共享夹具。

原则：测试永不触碰开发库 data/app.db —— 每个会话使用临时目录 SQLite，
通过环境变量 DATABASE_URL 注入后再导入 app 包；每个测试模块独立数据现场。
"""
import os
import tempfile
from pathlib import Path

import pytest

# 注意：app.core.database 在 import 时读取 DATABASE_URL 创建 engine（get_settings lru_cache），
# 而 pytest 收集阶段（fixture 生效前）就会导入测试模块 —— 因此必须在 conftest 模块级（先于
# 任何测试模块导入）把 URL 指到临时库，否则会绑定开发库 data/app.db。
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="litigation-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'test.db'}"


@pytest.fixture(scope="session", autouse=True)
def _isolated_db():
    """会话开始前把 DATABASE_URL 指到临时库，保证与开发数据隔离（现为模块级兜底）。"""
    yield os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def db_url(_isolated_db):
    return _isolated_db


@pytest.fixture(scope="module", autouse=True)
def _module_isolated_db():
    """每个测试模块独立数据现场：模块开始前重置共享临时库。

    背景：conftest 的 DATABASE_URL 对全部测试模块生效（import 时固定），
    test_api/test_clean 均经 SessionLocal 用同一 SQLite 文件；若不重置，前序
    模块残留的合成数据（如 api0★ 用例）会污染后序模块的件数/口径断言
    （曾实测 cases_total=27≠24）。test_metrics/test_sync 自带独立 engine，
    本重置对其无副作用。
    """
    from sqlalchemy import text

    from app.core.database import Base, engine, init_db
    from app.models.fts import CASES_FTS_TABLE

    # FTS5 影子表不在 metadata（DDL 直建），先显式 DROP 再 drop_all 其余表
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {CASES_FTS_TABLE}"))
    Base.metadata.drop_all(bind=engine)
    init_db()  # create_all + init_fts + 幂等种子（clean_rules/metric_defs/enum_dicts）
    yield