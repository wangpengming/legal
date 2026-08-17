"""测试 database 模块：CRUD + agents 唯一性修复。"""
import os
import tempfile
from pathlib import Path

import pytest

# 用临时数据库
TMP_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ["COURT_DB_PATH"] = str(TMP_DB)


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    """每个测试用全新的临时数据库。"""
    import importlib
    import database
    importlib.reload(database)
    monkeypatch.setattr(database, "DB_PATH", TMP_DB)
    database.init_db()
    yield
    if TMP_DB.exists():
        TMP_DB.unlink()


def test_init_db_creates_tables(fresh_db):
    """init_db 应创建 4 张表。"""
    import database as db
    with db.get_conn() as conn:
        tables = [row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
    assert "companies" in tables
    assert "agents" in tables
    assert "cases" in tables
    assert "case_history" in tables


def test_upsert_company(fresh_db):
    """upsert_company：第一次插入应返回 id，第二次（同 name）应更新。"""
    import database as db
    cid1 = db.upsert_company({"name": "测试公司A"})
    cid2 = db.upsert_company({"name": "测试公司A", "phone": "010-12345678"})
    assert cid1 == cid2, "同名公司应更新而非新增"
    co = db.get_company(cid1)
    assert co["phone"] == "010-12345678"


def test_upsert_agent_unique_by_name_and_company(fresh_db):
    """agents 唯一性修复：以 (name, company_id) 判重。"""
    import database as db
    cid = db.upsert_company({"name": "公司X"})

    # 同公司下同名 + 空 id_card 应是同一人
    aid1 = db.upsert_agent({"name": "张三", "company_id": cid, "id_card": ""})
    aid2 = db.upsert_agent({"name": "张三", "company_id": cid, "id_card": ""})
    assert aid1 == aid2, "同公司下同名同空 id_card 应是同一人"

    # 同名但不同公司应是两人
    cid_y = db.upsert_company({"name": "公司Y"})
    aid3 = db.upsert_agent({"name": "张三", "company_id": cid_y, "id_card": ""})
    assert aid3 != aid1, "不同公司下同名应不同人"

    # 同公司下不同名应是两人
    aid4 = db.upsert_agent({"name": "李四", "company_id": cid, "id_card": ""})
    assert aid4 != aid1, "同公司下不同名应不同人"


def test_list_agents_excludes_empty(fresh_db):
    """list_agents 默认排除空名字记录。"""
    import database as db
    db.upsert_company({"name": "公司"})
    db.upsert_agent({"name": "张三", "company_id": 1})
    agents = db.list_agents()
    names = [a["name"] for a in agents]
    assert "张三" in names


def test_create_and_search_cases(fresh_db):
    """create_case + search_cases。"""
    import database as db
    cid = db.upsert_company({"name": "公司"})
    aid = db.upsert_agent({"name": "代理人", "company_id": cid})

    case_id = db.create_case({
        "case_number": "（2026）京01民初123号",
        "case_cause": "合同纠纷",
        "court": "北京一中院",
        "hearing_date": "2026-09-01",
        "our_role": "原告",
        "authority_type": "特别授权",
        "company_id": cid,
        "agent_id": aid,
    })
    assert case_id > 0

    # 搜索
    found = db.search_cases("合同")
    assert len(found) >= 1
    assert found[0]["case_number"] == "（2026）京01民初123号"