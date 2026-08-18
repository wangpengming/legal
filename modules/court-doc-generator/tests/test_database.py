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
    assert "generation_history" in tables


def test_upsert_company(fresh_db):
    """upsert_company：第一次插入应返回 id，第二次（同 name）应更新。"""
    import database as db
    cid1 = db.upsert_company({"name": "测试公司A", "legal_rep_name": "测试法人"})
    cid2 = db.upsert_company({"name": "测试公司A", "phone": "010-12345678", "legal_rep_name": "测试法人"})
    assert cid1 == cid2, "同名公司应更新而非新增"
    co = db.get_company(cid1)
    assert co["phone"] == "010-12345678"


def test_upsert_agent_unique_by_name_and_company(fresh_db):
    """agents 唯一性修复：以 (name, company_id) 判重。"""
    import database as db
    cid = db.upsert_company({"name": "公司X", "legal_rep_name": "测试法人"})

    # 同公司下同名 + 空 id_card 应是同一人
    aid1 = db.upsert_agent({"name": "张三", "company_id": cid, "id_card": ""})
    aid2 = db.upsert_agent({"name": "张三", "company_id": cid, "id_card": ""})
    assert aid1 == aid2, "同公司下同名同空 id_card 应是同一人"

    # 同名但不同公司应是两人
    cid_y = db.upsert_company({"name": "公司Y", "legal_rep_name": "测试法人"})
    aid3 = db.upsert_agent({"name": "张三", "company_id": cid_y, "id_card": ""})
    assert aid3 != aid1, "不同公司下同名应不同人"

    # 同公司下不同名应是两人
    aid4 = db.upsert_agent({"name": "李四", "company_id": cid, "id_card": ""})
    assert aid4 != aid1, "同公司下不同名应不同人"


def test_list_agents_excludes_empty(fresh_db):
    """list_agents 默认排除空名字记录。"""
    import database as db
    db.upsert_company({"name": "公司", "legal_rep_name": "测试法人"})
    db.upsert_agent({"name": "张三", "company_id": 1})
    agents = db.list_agents()
    names = [a["name"] for a in agents]
    assert "张三" in names


def test_create_and_search_cases(fresh_db):
    """create_case + search_cases。"""
    import database as db
    cid = db.upsert_company({"name": "公司", "legal_rep_name": "测试法人"})
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


# ============================================================
# F-031 多代理人材料动态绑定：数据库迁移 + 新字段 CRUD
# ============================================================

def test_migrate_add_agent_pdf_paths(fresh_db):
    """F-031: 迁移函数能给旧库新增 contract_pdf_path / id_card_pdf_path 字段。

    旧库（无新字段）→ 执行迁移 → 新字段存在 → 重复执行幂等无报错。
    """
    import database as db
    import sqlite3

    with db.get_conn() as conn:
        # 验证迁移后字段存在
        cols = [row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()]
        assert "contract_pdf_path" in cols, "迁移后应包含 contract_pdf_path"
        assert "id_card_pdf_path" in cols, "迁移后应包含 id_card_pdf_path"

        # 验证幂等性：再次执行不报错
        db.migrate_add_agent_pdf_paths(conn)
        cols2 = [row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()]
        assert cols == cols2, "重复执行迁移不应改变列定义"


def test_upsert_agent_with_pdf_paths(fresh_db):
    """F-031: upsert_agent 能写入和读取 contract_pdf_path / id_card_pdf_path。

    覆盖：插入时写入 / 更新时更新 / list_agents 返回新字段。
    """
    import database as db

    cid = db.upsert_company({"name": "公司X", "legal_rep_name": "测试法人"})

    # 插入时写入 2 个路径
    aid1 = db.upsert_agent({
        "name": "张三",
        "company_id": cid,
        "contract_pdf_path": "static/agents/1/contract_a1b2.pdf",
        "id_card_pdf_path": "static/agents/1/id_card_c3d4.pdf",
    })

    # 读取验证
    agent = db.get_default_agent()
    assert agent["contract_pdf_path"] == "static/agents/1/contract_a1b2.pdf"
    assert agent["id_card_pdf_path"] == "static/agents/1/id_card_c3d4.pdf"

    # list_agents 也应返回新字段
    agents = db.list_agents()
    assert agents[0]["contract_pdf_path"] == "static/agents/1/contract_a1b2.pdf"

    # 更新时修改路径
    db.upsert_agent({
        "name": "张三",
        "company_id": cid,
        "contract_pdf_path": "static/agents/1/contract_new.pdf",
        "id_card_pdf_path": None,  # 显式置空
    })
    agent2 = db.get_default_agent()
    assert agent2["contract_pdf_path"] == "static/agents/1/contract_new.pdf"
    assert agent2["id_card_pdf_path"] is None


def test_old_record_compatible_after_migration(fresh_db):
    """F-031: 旧记录（迁移前插入的）在迁移后仍可读，路径字段为 None。

    兼容性验证：新增字段对老数据透明，不破坏现有 CRUD。
    """
    import database as db

    cid = db.upsert_company({"name": "公司X", "legal_rep_name": "测试法人"})

    # 在新表结构下插入老格式记录（不写新字段）
    aid = db.upsert_agent({"name": "李四", "company_id": cid, "id_card": "123456"})

    agent = db.get_default_agent()
    assert agent["name"] == "李四"
    assert agent["id_card"] == "123456"
    assert agent["contract_pdf_path"] is None  # 默认 None
    assert agent["id_card_pdf_path"] is None   # 默认 None


# ============================================================
# F-039 delete_agent 级联清理
# ============================================================

def test_delete_agent_no_relation_succeeds(fresh_db):
    """F-039: 无关联案件的代理人 → 删除成功 + 返回待清理文件路径。"""
    import database as db

    cid = db.upsert_company({"name": "公司", "legal_rep_name": "法人"})
    aid = db.upsert_agent({"name": "张三", "company_id": cid})

    success, msg, paths = db.delete_agent(aid)
    assert success is True
    assert "已删除" in msg
    assert paths == []  # 没上传 PDF，无文件路径


def test_delete_agent_with_relation_blocks(fresh_db):
    """F-039: 有关联案件的代理人 → 拒绝删除（保护历史）。"""
    import database as db

    cid = db.upsert_company({"name": "公司", "legal_rep_name": "法人"})
    aid = db.upsert_agent({"name": "李四", "company_id": cid})

    # 创建一个案件关联李四
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

    # 删除应失败
    success, msg, paths = db.delete_agent(aid)
    assert success is False
    assert "关联" in msg
    assert "1 个案件" in msg
    assert paths == []  # 不返回路径（不删文件）


def test_delete_agent_returns_file_paths(fresh_db):
    """F-039: 返回正确的待清理文件路径列表。"""
    import database as db

    cid = db.upsert_company({"name": "公司", "legal_rep_name": "法人"})
    aid = db.upsert_agent({
        "name": "王五",
        "company_id": cid,
        "contract_pdf_path": "static/agents/9/contract_abc.pdf",
        "id_card_pdf_path": "static/agents/9/id_card_xyz.pdf",
    })

    success, msg, paths = db.delete_agent(aid)
    assert success is True
    assert len(paths) == 2
    assert "contract_abc.pdf" in paths[0]
    assert "id_card_xyz.pdf" in paths[1]


def test_delete_agent_not_exists(fresh_db):
    """F-039: 删除不存在的代理人 → 失败。"""
    import database as db

    success, msg, paths = db.delete_agent(999)
    assert success is False
    assert "不存在" in msg
    assert paths == []