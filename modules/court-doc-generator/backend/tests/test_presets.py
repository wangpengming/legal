"""F5 法院/案由预设库 API 测试（TDD RED→GREEN）。"""
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app

client = TestClient(app)


def random_name():
    return f"TestUser_{secrets.token_hex(4)}"


import pytest


@pytest.fixture
def ws_id():
    """创建测试 workspace 并返回其 ID。"""
    name = random_name()
    r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
    return r.json()["workspace_id"]


def headers(ws_id):
    return {"X-Workspace-Id": ws_id}


class TestPresets:
    def test_create_preset(self, ws_id):
        """新增预设（court/cause）：插入成功，唯一约束生效。"""
        r = client.post("/api/v1/presets", json={
            "kind": "court", "value": "北京市朝阳区人民法院"
        }, headers=headers(ws_id))
        assert r.status_code == 200
        data = r.json()
        assert data["id"] > 0
        assert data["kind"] == "court"
        assert data["value"] == "北京市朝阳区人民法院"
        assert data["usage_count"] == 0

    def test_create_duplicate_reuses_existing(self, ws_id):
        """重复新增同一 (workspace, kind, value)：复用旧记录。"""
        h = headers(ws_id)
        r1 = client.post("/api/v1/presets", json={
            "kind": "cause", "value": "合同纠纷"
        }, headers=h).json()
        r2 = client.post("/api/v1/presets", json={
            "kind": "cause", "value": "合同纠纷"
        }, headers=h)
        assert r2.status_code == 200
        assert r2.json()["id"] == r1["id"]
        # 列表中只有一条
        lst = client.get("/api/v1/presets?kind=cause", headers=h).json()
        assert len(lst) == 1

    def test_bump_sorting(self, ws_id):
        """bump 次数排序：高频项排前面。"""
        h = headers(ws_id)
        a = client.post("/api/v1/presets", json={
            "kind": "court", "value": "法院A"
        }, headers=h).json()
        b = client.post("/api/v1/presets", json={
            "kind": "court", "value": "法院B"
        }, headers=h).json()
        # bump A 两次
        client.post(f"/api/v1/presets/{a['id']}/bump", headers=h)
        client.post(f"/api/v1/presets/{a['id']}/bump", headers=h)
        lst = client.get("/api/v1/presets?kind=court", headers=h).json()
        assert lst[0]["id"] == a["id"]
        assert lst[0]["usage_count"] == 2
        assert lst[1]["id"] == b["id"]

    def test_workspace_isolation(self, ws_id):
        """不同 workspace 隔离：互不可见。"""
        h1 = headers(ws_id)
        client.post("/api/v1/presets", json={
            "kind": "court", "value": "仅A可见法院"
        }, headers=h1)

        name = random_name()
        ws2 = client.post("/api/v1/auth/register", json={
            "name": name, "password": "test1234"
        }).json()["workspace_id"]
        h2 = headers(ws2)
        lst2 = client.get("/api/v1/presets?kind=court", headers=h2).json()
        assert lst2 == []
        assert all(p["value"] != "仅A可见法院" for p in lst2)

    def test_case_create_registers_preset(self, ws_id):
        """案件保存自动注册新值：新法院自动入库 usage_count 递增。"""
        h = headers(ws_id)
        # 创建案件，法院是预设表里没有的
        r = client.post("/api/v1/cases", json={
            "case_number": f"(2026)京0101民初{secrets.randbelow(90000) + 10000}号",
            "court": "海淀区人民法院", "cause": "劳动争议", "hearing_date": "2026-10-01",
            "opposing_party": "对方", "our_role": "原告",
            "company_id": None, "agent_id": None
        }, headers=h)
        assert r.status_code == 200
        lst = client.get("/api/v1/presets?kind=court", headers=h).json()
        match = [p for p in lst if p["value"] == "海淀区人民法院"]
        assert len(match) == 1
        assert match[0]["usage_count"] == 1
        # 案由也应注册
        causes = client.get("/api/v1/presets?kind=cause", headers=h).json()
        assert any(p["value"] == "劳动争议" for p in causes)
        # 再建同法院案件 → usage_count 变 2
        client.post("/api/v1/cases", json={
            "case_number": f"(2026)京0101民初{secrets.randbelow(90000) + 10000}号",
            "court": "海淀区人民法院", "cause": "劳动争议", "hearing_date": "",
            "opposing_party": "对方", "our_role": "原告",
            "company_id": None, "agent_id": None
        }, headers=h)
        lst = client.get("/api/v1/presets?kind=court", headers=h).json()
        match = [p for p in lst if p["value"] == "海淀区人民法院"]
        assert match[0]["usage_count"] == 2

    def test_delete_preset(self, ws_id):
        """删除预设：删除成功，列表不再含该项。"""
        h = headers(ws_id)
        p = client.post("/api/v1/presets", json={
            "kind": "court", "value": "待删除法院"
        }, headers=h).json()
        r = client.delete(f"/api/v1/presets/{p['id']}", headers=h)
        assert r.status_code == 200
        lst = client.get("/api/v1/presets?kind=court", headers=h).json()
        assert all(x["id"] != p["id"] for x in lst)