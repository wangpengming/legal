"""
Thunderbox Console — REST API Characterization Test
=================================================

RED 阶段：验证 FastAPI 端点返回结构。
使用 TestClient（FastAPI）+ mock MCP HTTP。

覆盖端点（SPEC §6 Subtask-1.2）：
- GET  /health
- GET  /api/apps
- GET  /api/apps/{app_id}
- GET  /api/apps/{app_id}/logs
- GET  /api/apps/{app_id}/build-logs
- GET  /api/apps/{app_id}/health
- GET  /api/apps/{app_id}/rollback-history
- GET  /api/apps/{app_id}/config
- POST /api/apps
- POST /api/apps/{app_id}/deploy
- POST /api/apps/{app_id}/control
- POST /api/apps/{app_id}/rollback
- PATCH /api/apps/{app_id}/config
- GET  /api/domains/check
- POST /api/apps/{app_id}/database
- DELETE /api/apps/{app_id}/database
- GET  /api/apps/{app_id}/tables
- GET  /api/apps/{app_id}/schema
- POST /api/apps/{app_id}/sql
- POST /api/apps/{app_id}/migrations
"""

from __future__ import annotations

import json
import http.client
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# 添加 backend/ 到 path 以便 import main
import sys
_backend_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(_backend_dir))
import thunderbox_mcp as tbmcp
from main import app


# ---------------------------------------------------------------------------
# Mock MCP
# ---------------------------------------------------------------------------

class MockResponse:
    __slots__ = ("_body", "_sid", "_status")

    def __init__(self, body: bytes, sid: str = "test", status: int = 200):
        self._body = body
        self._sid = sid
        self._status = status

    @property
    def status(self) -> int:
        return self._status

    def read(self) -> bytes:
        return self._body

    def getheader(self, name: str, default=None):
        if name.lower() == "mcp-session-id":
            return self._sid
        return default


def _sse(payload: str) -> bytes:
    outer = json.dumps({"result": {"content": [{"type": "text", "text": payload}]}})
    return f"event: message\ndata: {outer}\n\n".encode()


def _make_conn_factory(responses: list[tuple[bytes, str, int]]):
    idx = [0]

    def factory(host, timeout=None):
        conn = MagicMock()

        def fake_request(method, url, *, body=None, headers=None):
            if idx[0] < len(responses):
                body_bytes, sid, status = responses[idx[0]]
                idx[0] += 1
                mock_resp = MockResponse(body_bytes, sid, status)
            else:
                mock_resp = MockResponse(b'{"error": "unexpected"}', "", 500)
            conn.getresponse = MagicMock(return_value=mock_resp)
            return mock_resp

        conn.request = fake_request
        return conn

    return factory


def _build_3(tool_payload: str):
    """构建 3 个响应的序列（initialize + initialized + tool）"""
    init_body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "thunderbox", "version": "1.0.0"}}})
    init_resp = f"event: message\ndata: {init_body}\n\n".encode()
    init_notify = b'event: message\ndata: {"jsonrpc":"2.0","result":{"content":[]}}\n\n'
    tool_resp = _sse(tool_payload)
    return [(init_resp, "test-sid", 200), (init_notify, "test-sid", 200), (tool_resp, "test-sid", 200)]


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------

_APP_JSON = '[{"id":1,"app_id":"abc123","project_id":"proj1","name":"test-app","domain":"test-app.tbox.ktvsky.com","owner_email":"test@example.com","source_type":"git_repo","source_url":"https://github.com/x/y","ref":"main","is_public":0,"build_pack":"dockerfile","status":"running","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","volumes":"[]","bypass_trusted_ips":0}]'
_DOMAIN_JSON = '{"subdomain":"newdomain","domain":"newdomain.tbox.ktvsky.com","available":true}'
_LOGS_JSON = '"[INFO] App started"'
_CONFIG_JSON = '{"ref":"main","access_mode":"internal","bypass_trusted_ips":0,"env_vars":[],"volumes":[],"managers":[]}'
_HISTORY_JSON = '{"history":[{"commit":"abc123","deployed_at":"2026-01-01T00:00:00Z","status":"running"}]}'
_TABLES_JSON = '{"tables":[{"table_name":"users","table_schema":"public"}]}'
_SCHEMA_JSON = '[{"column_name":"id","data_type":"integer"}]'
_SQL_RESULT_JSON = '{"rows":[{"id":1}],"row_count":1,"columns":["id"]}'


# ---------------------------------------------------------------------------
# Test: health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    """GET /health 返回 200 + status/version"""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ---------------------------------------------------------------------------
# Test: list apps
# ---------------------------------------------------------------------------

class TestListApps:
    def test_get_apps_returns_list(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_APP_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["name"] == "test-app"


# ---------------------------------------------------------------------------
# Test: get app
# ---------------------------------------------------------------------------

class TestGetApp:
    def test_get_app_returns_dict(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_APP_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app.tbox.ktvsky.com")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "test-app"

    def test_get_app_404_for_missing(self, thunderbox_token: str):
        empty = _build_3("[]")
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(empty)):
            client = TestClient(app)
            resp = client.get("/api/apps/nonexistent")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: logs
# ---------------------------------------------------------------------------

class TestLogs:
    def test_get_logs_returns_text(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_LOGS_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/logs")
            assert resp.status_code == 200

    def test_get_build_logs_returns_text(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_LOGS_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/build-logs")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_get_config_returns_dict(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_CONFIG_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/config")
            assert resp.status_code == 200
            data = resp.json()
            assert "ref" in data
            assert "access_mode" in data

    def test_patch_config_accepts_request(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.patch("/api/apps/test-app/config", json={"access_mode": "public"})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: domain check
# ---------------------------------------------------------------------------

class TestDomainCheck:
    def test_check_domain_returns_availability(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_DOMAIN_JSON))):
            client = TestClient(app)
            resp = client.get("/api/domains/check", params={"subdomain": "newdomain"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True


# ---------------------------------------------------------------------------
# Test: rollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_get_rollback_history(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_HISTORY_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/rollback-history")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)

    def test_post_rollback_accepts_target(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/rollback", params={"target": 1})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: deploy / control
# ---------------------------------------------------------------------------

class TestDeployControl:
    def test_post_deploy(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/deploy")
            assert resp.status_code == 200

    def test_post_control_stop(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/control", json={"action": "stop"})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: database
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_list_tables(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_TABLES_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/tables")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            assert "tables" in data

    def test_get_schema(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_SCHEMA_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/schema")
            assert resp.status_code == 200

    def test_post_sql(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3(_SQL_RESULT_JSON))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/sql", json={"sql": "SELECT 1"})
            assert resp.status_code == 200

    def test_add_database(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/database", json={"database": "postgres"})
            assert resp.status_code == 200

    def test_delete_database(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.delete("/api/apps/test-app/database")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: create app
# ---------------------------------------------------------------------------

class TestCreateApp:
    def test_post_create_app(self, thunderbox_token: str):
        with patch.object(tbmcp.http.client, "HTTPSConnection", side_effect=_make_conn_factory(_build_3("{}"))):
            client = TestClient(app)
            resp = client.post("/api/apps", json={
                "name": "new-app",
                "source_type": "git_repo",
                "source_url": "https://github.com/x/y",
            })
            assert resp.status_code == 200
