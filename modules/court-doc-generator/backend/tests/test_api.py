"""后端 API 测试。"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app

client = TestClient(app)


def random_name():
    import secrets
    return f"TestUser_{secrets.token_hex(4)}"


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAuth:
    def test_register_and_login(self):
        name = random_name()
        # Register
        r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        assert r.status_code == 200
        data = r.json()
        assert "workspace_id" in data
        assert data["workspace_name"] == name
        ws_id = data["workspace_id"]

        # Login
        r = client.post("/api/v1/auth/login", json={"name": name, "password": "test1234"})
        assert r.status_code == 200
        assert r.json()["workspace_id"] == ws_id

        # Login wrong password
        r = client.post("/api/v1/auth/login", json={"name": name, "password": "wrong"})
        assert r.status_code == 401

    def test_register_duplicate(self):
        name = random_name()
        client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        assert r.status_code == 409


class TestCRUD:
    @pytest.fixture
    def ws_id(self):
        """创建测试 workspace 并返回其 ID。"""
        name = random_name()
        r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        return r.json()["workspace_id"]

    def headers(self, ws_id):
        return {"X-Workspace-Id": ws_id}

    def test_company_crud(self, ws_id):
        # Create
        r = client.post("/api/v1/companies", json={
            "name": "测试公司", "legal_rep_name": "张三", "legal_rep_position": "总经理",
            "address": "北京", "phone": "", "credit_code": ""
        }, headers=self.headers(ws_id))
        assert r.status_code == 200
        co = r.json()
        assert co["name"] == "测试公司"
        company_id = co["id"]

        # List
        r = client.get("/api/v1/companies", headers=self.headers(ws_id))
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # Delete
        r = client.delete(f"/api/v1/companies/{company_id}", headers=self.headers(ws_id))
        assert r.status_code == 200

    def test_agent_crud(self, ws_id):
        # Create
        r = client.post("/api/v1/agents", json={
            "name": "李四", "position": "法务", "phone": "13800001111",
            "company_id": None, "is_default": 1
        }, headers=self.headers(ws_id))
        assert r.status_code == 200
        agent = r.json()
        assert agent["name"] == "李四"
        agent_id = agent["id"]

        # List
        r = client.get("/api/v1/agents", headers=self.headers(ws_id))
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # Delete
        r = client.delete(f"/api/v1/agents/{agent_id}", headers=self.headers(ws_id))
        assert r.status_code == 200

    def test_case_crud(self, ws_id):
        # Create company first
        r = client.post("/api/v1/companies", json={
            "name": "测试公司", "legal_rep_name": "张三", "legal_rep_position": "总经理",
            "address": "北京", "phone": "", "credit_code": ""
        }, headers=self.headers(ws_id))
        company_id = r.json()["id"]

        # Create agent
        r = client.post("/api/v1/agents", json={
            "name": "代理人", "position": "法务", "phone": "13800001111",
            "company_id": None, "is_default": 1
        }, headers=self.headers(ws_id))
        agent_id = r.json()["id"]

        # Create case
        r = client.post("/api/v1/cases", json={
            "case_number": "(2026)京0101民初9999号", "court": "北京朝阳法院",
            "cause": "合同", "hearing_date": "2026-09-01",
            "opposing_party": "对方", "our_role": "原告",
            "company_id": company_id, "agent_id": agent_id
        }, headers=self.headers(ws_id))
        assert r.status_code == 200
        case = r.json()
        assert case["case_number"] == "(2026)京0101民初9999号"
        case_id = case["id"]

        # List
        r = client.get("/api/v1/cases", headers=self.headers(ws_id))
        assert r.status_code == 200
        assert any(c["id"] == case_id for c in r.json())

        # Delete
        r = client.delete(f"/api/v1/cases/{case_id}", headers=self.headers(ws_id))
        assert r.status_code == 200


    def test_case_our_role_court(self, ws_id):
        # 我方角色支持「法院」（拍照扫描起诉状建档场景）
        r = client.post("/api/v1/cases", json={
            "case_number": f"(2026)京0101民初{randint(10000, 99999)}号",
            "court": "北京朝阳法院", "cause": "合同", "hearing_date": "2026-09-01",
            "opposing_party": "对方公司", "our_role": "法院",
            "company_id": None, "agent_id": None
        }, headers=self.headers(ws_id))
        assert r.status_code == 200
        assert r.json()["our_role"] == "法院"
        case_id = r.json()["id"]
        # 列表回读验证
        r = client.get("/api/v1/cases", headers=self.headers(ws_id))
        assert r.status_code == 200
        created = next(c for c in r.json() if c["id"] == case_id)
        assert created["our_role"] == "法院"
        client.delete(f"/api/v1/cases/{case_id}", headers=self.headers(ws_id))


class TestGenerate:
    @pytest.fixture
    def ws_setup(self):
        """创建 workspace + company + agent 并返回 ws_id 和 ID。"""
        name = random_name()
        r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        ws_id = r.json()["workspace_id"]
        headers = {"X-Workspace-Id": ws_id}

        r = client.post("/api/v1/companies", json={
            "name": "测试公司", "legal_rep_name": "张三", "legal_rep_position": "总经理",
            "address": "北京", "phone": "", "credit_code": ""
        }, headers=headers)
        company_id = r.json()["id"]

        r = client.post("/api/v1/agents", json={
            "name": "代理人", "position": "法务", "phone": "13800001111",
            "company_id": None, "is_default": 1
        }, headers=headers)
        agent_id = r.json()["id"]

        r = client.post("/api/v1/cases", json={
            "case_number": f"(2026)京0101民初{randint(10000, 99999)}号",
            "court": "北京朝阳法院", "cause": "合同", "hearing_date": "2026-09-01",
            "opposing_party": "对方", "our_role": "原告",
            "company_id": company_id, "agent_id": agent_id
        }, headers=headers)
        case_id = r.json()["id"]
        return ws_id, case_id, company_id, agent_id, headers

    def test_generate(self, ws_setup):
        ws_id, case_id, company_id, agent_id, headers = ws_setup
        r = client.post("/api/v1/generate", json={
            "case_id": case_id, "company_id": company_id, "agent_id": agent_id
        }, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "output_dir" in data
        assert isinstance(data["files"], list)

    def test_history(self, ws_setup):
        ws_id, case_id, company_id, agent_id, headers = ws_setup
        # Generate
        r = client.post("/api/v1/generate", json={
            "case_id": case_id, "company_id": company_id, "agent_id": agent_id
        }, headers=headers)
        assert r.status_code == 200

        # List history
        r = client.get("/api/v1/history", headers=headers)
        assert r.status_code == 200
        records = r.json()
        assert len(records) >= 1

        # History files
        record_id = records[0]["id"]
        r = client.get(f"/api/v1/history/{record_id}/files", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        # Delete history
        r = client.delete(f"/api/v1/history/{record_id}", headers=headers)
        assert r.status_code == 200

    def test_scan_endpoint(self, ws_setup):
        ws_id, *_ = ws_setup
        r = client.post("/api/v1/scan/scan-url", json={"url": "https://example.com/test.jpg"}, headers={"X-Workspace-Id": ws_id})
        assert r.status_code == 200
        data = r.json()
        assert "text" in data
        assert "fields" in data


class TestFiles:
    def test_file_not_found(self):
        """不存在的文件返回 404。"""
        import base64
        path = "nonexistent/file.pdf"
        hex_path = path.encode("utf-8").hex()
        r = client.get(f"/api/v1/files/~hex/{hex_path}?ws=nonexistent")
        assert r.status_code == 404


from random import randint
