"""F6 操作日志 API 测试（TDD RED→GREEN）。"""
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def random_name():
    return f"TestUser_{secrets.token_hex(4)}"


import pytest


@pytest.fixture
def ws_id():
    name = random_name()
    r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
    return r.json()["workspace_id"]


def headers(ws_id):
    return {"X-Workspace-Id": ws_id}


class TestAudit:
    def test_login_register_logs(self, ws_id):
        """注册/登录成功都写日志。"""
        name = random_name()
        client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        r = client.post("/api/v1/auth/login", json={"name": name, "password": "test1234"})
        ws2 = r.json()["workspace_id"]
        logs = client.get("/api/v1/audit-logs", headers=headers(ws2)).json()
        actions = [log["action"] for log in logs]
        assert "register" in actions
        assert "login" in actions
        assert logs[0]["username"] == name  # 最新一条在前

    def test_case_create_logs(self, ws_id):
        """案件创建写日志，target 含案号。"""
        h = headers(ws_id)
        r = client.post("/api/v1/cases", json={
            "case_number": "(2026)京0101民初88888号", "court": "某法院",
            "cause": "合同纠纷", "hearing_date": "", "opposing_party": "",
            "our_role": "原告", "company_id": None, "agent_id": None,
        }, headers=h)
        case_id = r.json()["id"]
        logs = client.get("/api/v1/audit-logs", headers=h).json()
        create_logs = [log for log in logs if log["action"] == "case_create"]
        assert len(create_logs) == 1
        assert "(2026)京0101民初88888号" in create_logs[0]["target"]
        assert "case " + str(case_id) in create_logs[0]["target"]

    def test_mask_pii(self, ws_id):
        """mask_pii 将身份证号遮罩为前4后4。"""
        from app.api.audit import mask_pii
        assert mask_pii("110101199003071234") == "1101**********1234"
        assert mask_pii("身份证号是 110101199003071234 谢谢") == "身份证号是 1101**********1234 谢谢"
        assert mask_pii("短文本") == "短文本"
        assert mask_pii("") == ""

    def test_generate_logs(self, ws_id):
        """生成成功写 ok，失败写 failed。"""
        from random import randint
        h = headers(ws_id)
        # 准备 company + agent + case
        co = client.post("/api/v1/companies", json={
            "name": "测试公司", "legal_rep_name": "张三", "legal_rep_position": "总经理",
            "address": "", "phone": "", "credit_code": ""
        }, headers=h).json()
        ag = client.post("/api/v1/agents", json={
            "name": "代理人", "position": "法务", "phone": "13800001111",
            "company_id": None, "is_default": 1
        }, headers=h).json()
        ca = client.post("/api/v1/cases", json={
            "case_number": f"(2026)京0101民初{randint(10000, 99999)}号",
            "court": "法院", "cause": "", "hearing_date": "",
            "opposing_party": "", "our_role": "原告",
            "company_id": co["id"], "agent_id": ag["id"],
        }, headers=h).json()
        # 成功
        client.post("/api/v1/generate", json={
            "case_id": ca["id"], "company_id": co["id"], "agent_id": ag["id"],
        }, headers=h)
        # 失败（company 不存在）
        client.post("/api/v1/generate", json={
            "case_id": ca["id"], "company_id": 999999, "agent_id": ag["id"],
        }, headers=h)
        logs = client.get("/api/v1/audit-logs", headers=h).json()
        gen_logs = [log for log in logs if log["action"] == "generate"]
        results = {log["result"] for log in gen_logs}
        assert "ok" in results
        assert "failed" in results

    def test_workspace_isolation(self, ws_id):
        """跨 workspace 查询隔离。"""
        h1 = headers(ws_id)
        client.post("/api/v1/cases", json={
            "case_number": "(2026)京0101民初77777号", "court": "", "cause": "",
            "hearing_date": "", "opposing_party": "", "our_role": "原告",
            "company_id": None, "agent_id": None,
        }, headers=h1)
        name = random_name()
        ws2 = client.post("/api/v1/auth/register", json={
            "name": name, "password": "test1234"
        }).json()["workspace_id"]
        logs2 = client.get("/api/v1/audit-logs", headers=headers(ws2)).json()
        assert all(l["action"] != "case_create" for l in logs2)

    def test_pagination(self, ws_id):
        """limit/offset 正确切片（新→旧）。"""
        h = headers(ws_id)
        for i in range(5):
            client.post("/api/v1/cases", json={
                "case_number": f"(2026)京0101民初{i:05d}号", "court": "", "cause": "",
                "hearing_date": "", "opposing_party": "", "our_role": "原告",
                "company_id": None, "agent_id": None,
            }, headers=h)
        all_logs = client.get("/api/v1/audit-logs", headers=h).json()
        assert len(all_logs) >= 5
        page = client.get("/api/v1/audit-logs?limit=2&offset=0", headers=h).json()
        assert len(page) == 2
        assert page[0]["id"] > page[1]["id"]  # 新在前
        page2 = client.get("/api/v1/audit-logs?limit=2&offset=2", headers=h).json()
        assert len(page2) == 2
        assert page2[0]["id"] == all_logs[2]["id"]