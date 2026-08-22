"""F4 案件 CSV 导出测试（TDD RED→GREEN）。"""
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
def ws_setup():
    """workspace + company + agent + 1 个案件。"""
    name = random_name()
    r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
    ws_id = r.json()["workspace_id"]
    h = {"X-Workspace-Id": ws_id}
    co = client.post("/api/v1/companies", json={
        "name": "测试公司", "legal_rep_name": "张三", "legal_rep_position": "总经理",
        "address": "", "phone": "", "credit_code": ""
    }, headers=h).json()
    ag = client.post("/api/v1/agents", json={
        "name": "代理人甲", "position": "法务", "phone": "13800001111",
        "company_id": None, "is_default": 1
    }, headers=h).json()
    ca = client.post("/api/v1/cases", json={
        "case_number": "(2026)京0101民初66666号", "court": "北京市朝阳区人民法院",
        "cause": "合同纠纷", "hearing_date": "2026-09-01",
        "opposing_party": "=SUM(A1)", "our_role": "原告",
        "company_id": co["id"], "agent_id": ag["id"],
    }, headers=h).json()
    return ws_id, h, ca


class TestExport:
    def test_export_header_only_when_empty(self):
        """导出空列表：只有表头 10 列。"""
        name = random_name()
        r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
        h = {"X-Workspace-Id": r.json()["workspace_id"]}
        resp = client.get("/api/v1/cases/export", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        text = resp.content.decode("utf-8-sig")  # 去 BOM
        header = text.splitlines()[0]
        cols = header.split(",")
        assert len(cols) == 10
        assert cols == [
            "case_number", "court", "cause", "hearing_date", "opposing_party",
            "our_role", "status", "created_at", "company_name", "agent_name",
        ]

    def test_export_has_bom_and_chinese(self, ws_setup):
        """UTF-8 BOM 开头，中文正常。"""
        ws_id, h, ca = ws_setup
        resp = client.get("/api/v1/cases/export", headers=h)
        raw = resp.content
        assert raw.startswith(b"\xef\xbb\xbf")  # BOM
        text = raw.decode("utf-8-sig")
        assert "北京市朝阳区人民法院" in text
        assert "合同纠纷" in text

    def test_export_injection_guard(self, ws_setup):
        """注入防护：= 开头的单元格前缀 '。"""
        ws_id, h, ca = ws_setup
        resp = client.get("/api/v1/cases/export", headers=h)
        text = resp.content.decode("utf-8-sig")
        assert "'=SUM(A1)" in text  # opposing_party 被防护

    def test_export_respects_filters(self, ws_setup):
        """带筛选参数：只导出筛选结果。"""
        ws_id, h, ca = ws_setup
        # 再加一个案件（上海）
        client.post("/api/v1/cases", json={
            "case_number": "(2026)沪0101民初70007号", "court": "上海市浦东新区人民法院",
            "cause": "劳动争议", "hearing_date": "2026-11-01",
            "opposing_party": "对方", "our_role": "被告",
            "company_id": None, "agent_id": None,
        }, headers=h)
        resp = client.get("/api/v1/cases/export?search=沪0101", headers=h)
        text = resp.content.decode("utf-8-sig")
        assert "沪0101民初70007" in text
        assert "66666" not in text

    def test_export_columns_content(self, ws_setup):
        """公司名/代理人名列正确（JOIN）。"""
        ws_id, h, ca = ws_setup
        resp = client.get("/api/v1/cases/export", headers=h)
        text = resp.content.decode("utf-8-sig")
        assert "测试公司" in text
        assert "代理人甲" in text

    def test_export_audit_logged(self, ws_setup):
        """导出操作写 audit 日志。"""
        ws_id, h, ca = ws_setup
        client.get("/api/v1/cases/export", headers=h)
        logs = client.get("/api/v1/audit-logs", headers=h).json()
        assert any(l["action"] == "export" and l["result"] == "ok" for l in logs)