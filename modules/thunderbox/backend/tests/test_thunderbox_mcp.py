"""
Thunderbox Console — MCP 层 Characterization Test
==============================================

RED 阶段：先写失败测试，验证 MCP 层行为。

测试策略（AGENTS.md §7 / 08-TDD）：
- 使用 `unittest.mock.patch` mock `http.client.HTTPSConnection`
  （responses 库无法拦截 Python 标准库 http.client）
- 锁定现有代码的实际行为（characterization test）
- 覆盖：list_apps / get_app / check_domain / get_app_logs / get_build_logs

MCP Session 管理：
- POST /mcp → 响应头 mcp-session-id
- 后续请求带 Mcp-Session-Id header
"""

from __future__ import annotations

import http.client
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from thunderbox_mcp import ThunderboxMCP, App, MCPError


# ---------------------------------------------------------------------------
# Mock HTTP 响应构建
# ---------------------------------------------------------------------------

def _sse(payload: str) -> bytes:
    """将 JSON payload 包装成 MCP SSE 格式（bytes）。

    真实 MCP SSE 响应格式（JSON-RPC 2.0）：
    event: message
    data: {"result": {"content": [{"type": "text", "text": "..."}]}}

    _rpc_call 解析时会 strip() 行，跳过 event: 行，只处理 data: 行。
    """
    outer = json.dumps({"result": {"content": [{"type": "text", "text": payload}]}})
    return f"event: message\ndata: {outer}\n\n".encode()


def _make_mock_response(body: bytes, session_id: str = "test-session-001", status: int = 200) -> "MockResponse":
    """构建一个 mock HTTP 响应（用普通 class 避免 MagicMock getheader 问题）"""
    return MockResponse(body, session_id, status)


class MockResponse:
    """可靠的 mock HTTP 响应对象"""
    __slots__ = ("_body", "_sid", "_status")

    def __init__(self, body: bytes, session_id: str, status: int):
        self._body = body
        self._sid = session_id
        self._status = status

    @property
    def status(self) -> int:
        return self._status

    def read(self) -> bytes:
        return self._body

    def getheader(self, name: str, default: str | None = None) -> str | None:
        if name.lower() == "mcp-session-id":
            return self._sid
        return default


def _make_mock_conn(responses: list[tuple[bytes, str, int]]):
    """
    构建 mock HTTPSConnection，每次 request 返回一个响应。

    关键：patch("http.client.HTTPSConnection") 让类返回 MagicMock，
    其 request()/getresponse() 都返回 MagicMock。
    正确做法：patch.__init__ 返回我们自己的 mock_conn，
    然后 mock_conn.request() → MockResponse（不在 MagicMock 上调 getresponse）。

    Args:
        responses: list of (body_bytes, session_id, status)
    """
    idx = [0]

    def fake_request(method, url, *, body=None, headers=None):
        if idx[0] < len(responses):
            body_bytes, sid, status = responses[idx[0]]
            idx[0] += 1
            return MockResponse(body_bytes, sid, status)
        return MockResponse(b'{"error": "unexpected request"}', "", 500)

    mock_conn = MagicMock()
    mock_conn.request = fake_request
    # 不在 mock_conn 上调 getresponse，所以不需要 mock 它
    return mock_conn


def _make_conn_factory(responses: list[tuple[bytes, str, int]]):
    """
    返回 HTTPSConnection patch side_effect factory。

    关键：ThunderboxMCP._rpc_call 使用：
        self._conn.request(...)
        resp = self._conn.getresponse()   # <-- 从 conn 上取，不是 request() 返回值
    因此 mock_conn.getresponse() 也必须返回 MockResponse。
    """
    idx = [0]

    def factory(host, timeout=None):
        mock_conn = MagicMock()

        def fake_request(method, url, *, body=None, headers=None):
            if idx[0] < len(responses):
                body_bytes, sid, status = responses[idx[0]]
                idx[0] += 1
                mock_resp = MockResponse(body_bytes, sid, status)
            else:
                mock_resp = MockResponse(b'{"error": "unexpected request"}', "", 500)
            # ThunderboxMCP._rpc_call 用 self._conn.getresponse()，不是 request() 返回值
            mock_conn.getresponse = MagicMock(return_value=mock_resp)
            return mock_resp

        mock_conn.request = fake_request
        return mock_conn

    return factory


# ---------------------------------------------------------------------------
# Session 级 mock：所有测试共用
# ---------------------------------------------------------------------------

# App JSON（真实 MCP 返回的 app 列表中第一个）
_APP_LIST_JSON = (
    '[{"id":559,"app_id":"y11eb88rulwk1to63zune7z1",'
    '"project_id":"dr7zpk1t1kq7f2xs7crla5te",'
    '"name":"legal-court","domain":"legal-court.tbox.ktvsky.com",'
    '"owner_email":"test@example.com","source_type":"git_repo",'
    '"source_url":"https://github.com/owner/repo","ref":"main",'
    '"is_public":1,"build_pack":"dockerfile","status":"running",'
    '"created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-01T00:00:00Z",'
    '"volumes":"[]","bypass_trusted_ips":0}]'
)

_DOMAIN_JSON = '{"subdomain":"newdomain","domain":"newdomain.tbox.ktvsky.com","available":true}'
_LOGS_TEXT = '"[INFO] App started at 2026-08-01T00:00:00Z"'
_BUILD_LOGS_TEXT = '"Step 1/5 : FROM python:3.11-slim"'


def _build_responses_for_tool(tool_name: str, result_payload: str, sid: str = "test-session-001"):
    """
    为单个 tool call 构建完整的 session 序列：
    1. initialize 请求（返回 serverInfo + session header，jsonrpc 格式）
    2. initialized 通知（空 body，_rpc_call 返回 None，正常）
    3. tool call 响应

    真实 MCP SSE 格式：event: message\\ndata: {...}\\n\\n
    """
    # initialize 响应：MCP JSON-RPC 格式
    init_body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "thunderbox", "version": "0.2.0"}}})
    init_resp = f"event: message\ndata: {init_body}\n\n".encode()
    # initialized 通知：无 id，_rpc_call 解析 data: {} → {} dict → _call_tool 访问 data["result"] 会 KeyError
    # 因此返回带 result 的响应（模拟非通知类工具响应）
    initialized_notify = b'event: message\ndata: {"jsonrpc":"2.0","result":{"content":[]}}\n\n'
    tool_resp = _sse(result_payload)

    return [
        (init_resp, sid, 200),       # initialize
        (initialized_notify, sid, 200),  # initialized notification
        (tool_resp, sid, 200),       # tool call
    ]


# ---------------------------------------------------------------------------
# Test: list_apps
# ---------------------------------------------------------------------------

class TestThunderboxMCPListApps:
    """list_apps() 返回 list[App]"""

    def test_list_apps_returns_list_of_apps(self, thunderbox_token: str):
        """list_apps() 应返回非空 list[App]"""
        sid = "test-list-apps"
        mock_responses = _build_responses_for_tool("thunderbox_query", _APP_LIST_JSON, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                apps = client.list_apps()
                assert isinstance(apps, list)
                assert len(apps) == 1
                assert all(isinstance(a, App) for a in apps)
            finally:
                client.close()

    def test_list_apps_parses_app_fields(self, thunderbox_token: str):
        """App 对象应包含 name/domain/status/source_type 等字段"""
        sid = "test-list-fields"
        mock_responses = _build_responses_for_tool("thunderbox_query", _APP_LIST_JSON, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                app = client.list_apps()[0]
                assert app.name == "legal-court"
                assert app.domain == "legal-court.tbox.ktvsky.com"
                assert app.status == "running"
                assert app.source_type == "git_repo"
                assert app.is_public == 1
                assert app.build_pack == "dockerfile"
                assert app.ref == "main"
            finally:
                client.close()

    def test_list_apps_sends_jsonrpc_tool_call(self, thunderbox_token: str):
        """list_apps() 应发送 method=tools/call, name=thunderbox_query"""
        sid = "test-list-jsonrpc"
        captured_body = [None]

        def make_factory(captured):
            i = [0]
            def factory(host, timeout=None):
                conn = MagicMock()
                responses_seq = [
                    MockResponse(f"event: message\ndata: {json.dumps({'jsonrpc':'2.0','id':1,'result':{'serverInfo':{'name':'thunderbox','version':'0.2.0'}}})}\n\n".encode(), sid, 200),
                    MockResponse(b"event: message\ndata: {}\n\n", sid, 200),
                    MockResponse(_sse("[]"), sid, 200),
                ]
                def fake_req(method, url, *, body=None, headers=None):
                    captured[0] = body
                    i[0] += 1
                    mock_resp = responses_seq[i[0] - 1] if i[0] <= len(responses_seq) else MockResponse(b'{}', sid, 500)
                    conn.getresponse = MagicMock(return_value=mock_resp)
                    return mock_resp
                conn.request = fake_req
                return conn
            return factory

        with patch.object(http.client, "HTTPSConnection", side_effect=make_factory(captured_body)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                client.list_apps()
            finally:
                client.close()

        body = json.loads(captured_body[0])
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "thunderbox_query"

    def test_list_apps_uses_session_header_after_init(self, thunderbox_token: str):
        """初始化后，后续请求应带 Mcp-Session-Id header"""
        sid = "test-session-header"
        captured_headers = []

        def make_factory(captured):
            def factory(host, timeout=None):
                conn = MagicMock()
                responses_seq = [
                    MockResponse(f"event: message\ndata: {json.dumps({'jsonrpc':'2.0','id':1,'result':{'serverInfo':{'name':'thunderbox','version':'0.2.0'}}})}\n\n".encode(), sid, 200),
                    MockResponse(b"event: message\ndata: {}\n\n", sid, 200),
                    MockResponse(_sse("[]"), sid, 200),
                ]
                i = [0]
                def fake_req(method, url, *, body=None, headers=None):
                    captured.append(headers)
                    i[0] += 1
                    mock_resp = responses_seq[i[0] - 1] if i[0] <= len(responses_seq) else MockResponse(b'{}', sid, 500)
                    conn.getresponse = MagicMock(return_value=mock_resp)
                    return mock_resp
                conn.request = fake_req
                return conn
            return factory

        with patch.object(http.client, "HTTPSConnection", side_effect=make_factory(captured_headers)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                client.list_apps()
            finally:
                client.close()

        # 最后一个请求（tool call）应带 session header
        # MCP 客户端发送 'Mcp-Session-Id'（camelCase）
        last_headers = captured_headers[-1]
        assert "mcp-session-id" in last_headers or "Mcp-Session-Id" in last_headers
        key = "Mcp-Session-Id" if "Mcp-Session-Id" in last_headers else "mcp-session-id"
        assert last_headers[key] == sid


# ---------------------------------------------------------------------------
# Test: get_app
# ---------------------------------------------------------------------------

class TestThunderboxMCPGetApp:
    """get_app() 通过 app_id 或 domain 查找"""

    def test_get_app_by_app_id_returns_app(self, thunderbox_token: str):
        """get_app('legal-court.tbox.ktvsky.com') 通过 domain 查找"""
        sid = "test-get-app-id"
        mock_responses = _build_responses_for_tool("thunderbox_query", _APP_LIST_JSON, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                app = client.get_app("legal-court.tbox.ktvsky.com")
                assert app is not None
                assert app.name == "legal-court"
            finally:
                client.close()

    def test_get_app_by_domain_returns_app(self, thunderbox_token: str):
        """get_app('legal-court.tbox.ktvsky.com') 应返回对应 App"""
        sid = "test-get-domain"
        mock_responses = _build_responses_for_tool("thunderbox_query", _APP_LIST_JSON, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                app = client.get_app("legal-court.tbox.ktvsky.com")
                assert app is not None
                assert app.domain == "legal-court.tbox.ktvsky.com"
            finally:
                client.close()

    def test_get_app_not_found_returns_none(self, thunderbox_token: str):
        """get_app() 查找不存在的 app 应返回 None"""
        sid = "test-get-notfound"
        mock_responses = _build_responses_for_tool("thunderbox_query", "[]", sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                app = client.get_app("non-existent-xyz")
                assert app is None
            finally:
                client.close()


# ---------------------------------------------------------------------------
# Test: check_domain
# ---------------------------------------------------------------------------

class TestThunderboxMCPCheckDomain:
    """check_domain() 检测域名可用性"""

    def test_check_domain_returns_result(self, thunderbox_token: str):
        """check_domain('newdomain') 应返回 DomainCheckResult"""
        from thunderbox_mcp import DomainCheckResult

        sid = "test-check-domain"
        mock_responses = _build_responses_for_tool("thunderbox_check", _DOMAIN_JSON, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                result = client.check_domain("newdomain")
                assert isinstance(result, DomainCheckResult)
                assert result.subdomain == "newdomain"
                assert result.domain == "newdomain.tbox.ktvsky.com"
                assert result.available is True
            finally:
                client.close()


# ---------------------------------------------------------------------------
# Test: logs
# ---------------------------------------------------------------------------

class TestThunderboxMCPLogs:
    """get_app_logs() / get_build_logs() 获取日志"""

    def test_get_app_logs_returns_text(self, thunderbox_token: str):
        """get_app_logs() 应返回日志文本字符串"""
        sid = "test-app-logs"
        mock_responses = _build_responses_for_tool("thunderbox_query", _LOGS_TEXT, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                logs = client.get_app_logs("legal-court")
                assert isinstance(logs, str)
                assert "App started" in logs
            finally:
                client.close()

    def test_get_build_logs_returns_text(self, thunderbox_token: str):
        """get_build_logs() 应返回构建日志文本字符串"""
        sid = "test-build-logs"
        mock_responses = _build_responses_for_tool("thunderbox_query", _BUILD_LOGS_TEXT, sid)

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                logs = client.get_build_logs("legal-court")
                assert isinstance(logs, str)
                assert "FROM python" in logs
            finally:
                client.close()


# ---------------------------------------------------------------------------
# Test: error handling
# ---------------------------------------------------------------------------

class TestThunderboxMCPError:
    """MCP 错误处理"""

    def test_mcp_error_raises_mcp_error(self, thunderbox_token: str):
        """MCP 返回 error JSON-RPC 应抛出 MCPError"""
        sid = "test-mcp-error"
        # 序列：initialize → initialized → tool call error
        init_body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "thunderbox", "version": "0.2.0"}}})
        init_resp = f"event: message\ndata: {init_body}\n\n".encode()
        init_notify = b"event: message\ndata: {}\n\n"
        error_resp = b'event: message\ndata: {"jsonrpc":"2.0","id":2,"error":{"code":-32600,"message":"Server not initialized"}}\n\n'
        mock_responses = [
            (init_resp, sid, 200),
            (init_notify, sid, 200),
            (error_resp, sid, 200),
        ]

        with patch.object(http.client, "HTTPSConnection", side_effect=_make_conn_factory(mock_responses)):
            client = ThunderboxMCP(token=thunderbox_token)
            client.connect()
            try:
                with pytest.raises(MCPError) as exc_info:
                    client.list_apps()
                assert "not initialized" in str(exc_info.value)
            finally:
                client.close()


# ---------------------------------------------------------------------------
# Test: token validation
# ---------------------------------------------------------------------------

class TestThunderboxMCPTokenValidation:
    """Token 校验"""

    def test_missing_token_raises_value_error(self):
        """未提供 token 且无环境变量时应抛出 ValueError"""
        import os as _os

        _backup = _os.environ.pop("THUNDERBOX_TOKEN", None)
        try:
            with pytest.raises(ValueError) as exc_info:
                ThunderboxMCP()
            assert "THUNDERBOX_TOKEN" in str(exc_info.value)
        finally:
            if _backup:
                _os.environ["THUNDERBOX_TOKEN"] = _backup
