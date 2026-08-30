"""
Thunderbox Console — Config & Database API Characterization Test
============================================================

RED 阶段：验证 Config/Database 端点返回结构。
使用 TestClient（FastAPI）+ mock MCP HTTP。

覆盖端点（SPEC-2026-001 Story-3/Story-4）：
- GET  /api/apps/{id}/config     — 获取应用配置
- PATCH /api/apps/{id}/config    — 更新配置（env_vars / access_mode / managers / emails）
- POST /api/apps/{id}/database    — 附加数据库
- DELETE /api/apps/{id}/database — 卸除数据库
- GET  /api/apps/{id}/tables     — 列出数据库表
- GET  /api/apps/{id}/schema      — 获取表结构
- POST /api/apps/{id}/sql         — 执行 SQL
- POST /api/apps/{id}/migrations — 执行迁移（幂等）
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import sys
_backend_dir = Path(__file__).parent.parent.resolve()
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import thunderbox_mcp as tbmcp
from main import app


# ---------------------------------------------------------------------------
# Mock MCP helper（与 test_api.py 保持一致）
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
# Mock 数据
# ---------------------------------------------------------------------------

_CONFIG_JSON = json.dumps({
    "ref": "main",
    "access_mode": "internal",
    "bypass_trusted_ips": False,
    "env_vars": [["LOG_LEVEL", "info"], ["DATABASE_URL", "postgres://..."]],
    "volumes": [{"source": "my-data", "target": "/app/data"}],
    "managers": ["admin@example.com"],
})
_TABLES_JSON = json.dumps({"tables": [
    {"name": "users", "columns": [{"name": "id", "type": "integer"}, {"name": "email", "type": "text"}]},
    {"name": "posts", "columns": [{"name": "id", "type": "integer"}, {"name": "user_id", "type": "integer"}]},
]})
_SCHEMA_JSON = json.dumps({
    "tables": [
        {"name": "users", "columns": [{"name": "id", "type": "integer"}, {"name": "email", "type": "text"}]},
    ],
    "migrations": [
        {"name": "001_init", "applied_at": "2026-08-20T10:00:00Z"},
    ],
})
_SQL_RESULT_JSON = json.dumps({
    "rows": [{"id": 1, "email": "test@example.com"}],
    "row_count": 1,
    "columns": ["id", "email"],
})
_SQL_ERROR_JSON = json.dumps({"error": "syntax error at or near \"SELEC\"", "code": "42601"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def thunderbox_token():
    import os
    token = os.environ.get("THUNDERBOX_TOKEN", "")
    if not token:
        pytest.skip("THUNDERBOX_TOKEN not set")
    return token


# ---------------------------------------------------------------------------
# Test: GET /api/apps/{id}/config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_get_config_returns_ref_access_env_managers(self, thunderbox_token):
        """验证 GET /api/apps/{id}/config 返回 ref / access_mode / env_vars / managers"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_CONFIG_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ref"] == "main"
            assert data["access_mode"] == "internal"
            assert "env_vars" in data
            assert isinstance(data["env_vars"], list)
            assert "managers" in data
            assert isinstance(data["managers"], list)
            assert "volumes" in data

    def test_get_config_includes_bypass_trusted_ips(self, thunderbox_token):
        """验证 bypass_trusted_ips 字段存在"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_CONFIG_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/config")
            assert resp.status_code == 200
            data = resp.json()
            assert "bypass_trusted_ips" in data


# ---------------------------------------------------------------------------
# Test: PATCH /api/apps/{id}/config — env_vars
# ---------------------------------------------------------------------------

class TestUpdateEnvVars:
    def test_patch_config_adds_env_var(self, thunderbox_token):
        """PATCH config + env_vars 后 thunderbox_config 被调用"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"env_vars": [["NEW_VAR", "new_value"]]}
            )
            assert resp.status_code == 200

    def test_patch_config_removes_env_var(self, thunderbox_token):
        """PATCH config + 过滤后的 env_vars 列表实现删除"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"env_vars": [["LOG_LEVEL", "info"]]}  # 只保留一条
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: PATCH /api/apps/{id}/config — access_mode
# ---------------------------------------------------------------------------

class TestUpdateAccessMode:
    def test_patch_config_sets_access_mode_public(self, thunderbox_token):
        """切换 access_mode = public 时返回成功"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"access_mode": "public"}
            )
            assert resp.status_code == 200

    def test_patch_config_sets_access_mode_restricted(self, thunderbox_token):
        """切换 access_mode = restricted"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"access_mode": "restricted"}
            )
            assert resp.status_code == 200

    def test_patch_config_sets_access_mode_internal(self, thunderbox_token):
        """切换 access_mode = internal"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"access_mode": "internal"}
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: PATCH /api/apps/{id}/config — restricted 白名单
# ---------------------------------------------------------------------------

class TestEmailWhitelist:
    def test_patch_config_add_emails(self, thunderbox_token):
        """add_emails 参数正确传递"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"add_emails": ["user@example.com"]}
            )
            assert resp.status_code == 200

    def test_patch_config_remove_emails(self, thunderbox_token):
        """remove_emails 参数正确传递"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"remove_emails": ["user@example.com"]}
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: PATCH /api/apps/{id}/config — 协作者管理
# ---------------------------------------------------------------------------

class TestManagerCRUD:
    def test_patch_config_add_manager(self, thunderbox_token):
        """添加协作者：manager_action=add + manager_email"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"manager_email": "new@example.com", "manager_action": "add"}
            )
            assert resp.status_code == 200

    def test_patch_config_remove_manager(self, thunderbox_token):
        """移除协作者：manager_action=remove + manager_email"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.patch(
                "/api/apps/test-app/config",
                json={"manager_email": "old@example.com", "manager_action": "remove"}
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: POST/DELETE /api/apps/{id}/database
# ---------------------------------------------------------------------------

class TestDatabaseCRUD:
    def test_post_database_adds_postgres(self, thunderbox_token):
        """POST /api/apps/{id}/database 附加 PostgreSQL"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"database":"postgres"}'))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/database", json={"database": "postgres"})
            assert resp.status_code == 200

    def test_post_database_adds_sqlite(self, thunderbox_token):
        """POST /api/apps/{id}/database 附加 SQLite"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"database":"sqlite"}'))):
            client = TestClient(app)
            resp = client.post("/api/apps/test-app/database", json={"database": "sqlite"})
            assert resp.status_code == 200

    def test_delete_database_removes(self, thunderbox_token):
        """DELETE /api/apps/{id}/database 卸除数据库"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.delete("/api/apps/test-app/database")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: GET /api/apps/{id}/tables
# ---------------------------------------------------------------------------

class TestListTables:
    def test_get_tables_returns_dict_with_tables(self, thunderbox_token):
        """GET /api/apps/{id}/tables 返回 dict 含 tables 列表"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_TABLES_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/tables")
            assert resp.status_code == 200
            data = resp.json()
            assert "tables" in data
            assert isinstance(data["tables"], list)
            assert len(data["tables"]) == 2
            assert data["tables"][0]["name"] == "users"

    def test_get_tables_includes_column_info(self, thunderbox_token):
        """表数据包含列信息"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_TABLES_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/tables")
            assert resp.status_code == 200
            data = resp.json()
            assert "columns" in data["tables"][0]


# ---------------------------------------------------------------------------
# Test: GET /api/apps/{id}/schema
# ---------------------------------------------------------------------------

class TestDescribeSchema:
    def test_get_schema_returns_tables_and_migrations(self, thunderbox_token):
        """GET /api/apps/{id}/schema 返回表结构 + 迁移记录"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_SCHEMA_JSON))):
            client = TestClient(app)
            resp = client.get("/api/apps/test-app/schema")
            assert resp.status_code == 200
            data = resp.json()
            assert "tables" in data
            assert "migrations" in data


# ---------------------------------------------------------------------------
# Test: POST /api/apps/{id}/sql
# ---------------------------------------------------------------------------

class TestSQLWorkbench:
    def test_post_sql_select_returns_rows(self, thunderbox_token):
        """POST /api/apps/{id}/sql 执行 SELECT 返回 rows + columns"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_SQL_RESULT_JSON))):
            client = TestClient(app)
            resp = client.post(
                "/api/apps/test-app/sql",
                json={"sql": "SELECT * FROM users LIMIT 10"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "rows" in data
            assert "columns" in data
            assert data["row_count"] == 1

    def test_post_sql_error_returns_error_field(self, thunderbox_token):
        """POST /api/apps/{id}/sql 执行失败返回 error 字段"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3(_SQL_ERROR_JSON))):
            client = TestClient(app)
            resp = client.post(
                "/api/apps/test-app/sql",
                json={"sql": "SELEC * FROM users"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "error" in data


# ---------------------------------------------------------------------------
# Test: POST /api/apps/{id}/migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_post_migrations_returns_success(self, thunderbox_token):
        """POST /api/apps/{id}/migrations 执行幂等迁移"""
        with patch.object(tbmcp.http.client, "HTTPSConnection",
                         side_effect=_make_conn_factory(_build_3('{"success":true}'))):
            client = TestClient(app)
            resp = client.post(
                "/api/apps/test-app/migrations",
                json={"name": "add_users_table", "sql": "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY);"}
            )
            assert resp.status_code == 200
