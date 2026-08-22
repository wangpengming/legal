"""F1 案件搜索/筛选 API 测试（TDD RED→GREEN）。"""
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
    """创建 workspace + 3 个不同特征案件。"""
    name = random_name()
    r = client.post("/api/v1/auth/register", json={"name": name, "password": "test1234"})
    ws_id = r.json()["workspace_id"]
    h = {"X-Workspace-Id": ws_id}

    def mk(case_number, court, cause, hearing_date):
        return client.post("/api/v1/cases", json={
            "case_number": case_number, "court": court, "cause": cause,
            "hearing_date": hearing_date, "opposing_party": "对方",
            "our_role": "原告", "company_id": None, "agent_id": None,
        }, headers=h).json()["id"]

    c1 = mk("(2026)京0101民初10001号", "北京市朝阳区人民法院", "合同纠纷", "2026-09-01")
    c2 = mk("(2026)沪0101民初20002号", "上海市浦东新区人民法院", "劳动争议", "2026-10-15")
    c3 = mk("(2026)京0101民初30003号", "北京市海淀区人民法院", "合同纠纷", "")
    return ws_id, h, c1, c2, c3


class TestSearch:
    def test_search_by_case_number(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases?search=20002", headers=h)
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert ids == [c2]

    def test_search_by_court(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases?search=朝阳", headers=h)
        ids = [c["id"] for c in r.json()]
        assert c1 in ids and c2 not in ids and c3 not in ids

    def test_search_by_cause(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases?search=劳动", headers=h)
        ids = [c["id"] for c in r.json()]
        assert ids == [c2]

    def test_status_filter(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        # 直接改 DB 制造不同状态（无 update API）
        from app.core.database import get_conn
        with get_conn(ws_id) as conn:
            conn.execute("UPDATE cases SET status='closed' WHERE id=?", (c2,))
            conn.commit()
        r = client.get("/api/v1/cases?status=closed", headers=h)
        ids = [c["id"] for c in r.json()]
        assert ids == [c2]
        r = client.get("/api/v1/cases?status=pending", headers=h)
        ids = [c["id"] for c in r.json()]
        assert c1 in ids and c3 in ids and c2 not in ids

    def test_hearing_date_range(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases?hearing_from=2026-10-01", headers=h)
        ids = [c["id"] for c in r.json()]
        assert ids == [c2]
        r = client.get("/api/v1/cases?hearing_to=2026-09-30", headers=h)
        ids = [c["id"] for c in r.json()]
        assert ids == [c1]
        # 边界：等于 from/to 也包含
        r = client.get("/api/v1/cases?hearing_from=2026-09-01&hearing_to=2026-10-15", headers=h)
        ids = [c["id"] for c in r.json()]
        assert c1 in ids and c2 in ids and c3 not in ids

    def test_combined_filters(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases?search=京0101&status=pending&hearing_from=2026-09-01", headers=h)
        ids = [c["id"] for c in r.json()]
        assert c1 in ids and c3 not in ids  # c3 无开庭日期，不在 from 范围内

    def test_no_params_returns_all(self, ws_setup):
        ws_id, h, c1, c2, c3 = ws_setup
        r = client.get("/api/v1/cases", headers=h)
        ids = [c["id"] for c in r.json()]
        assert set(ids) == {c1, c2, c3}