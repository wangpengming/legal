"""
Thunderbox Console — 审计日志测试
=================================

覆盖（SPEC-2026-001 Story-5 Subtask-5.1）：
- audit.py 中间件：拦截写操作并写入 SQLite
- GET /api/audit：分页查询审计日志

测试隔离：audit.db 放在 .pytest-data/ 下（不碰真实数据）
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

_backend_dir = Path(__file__).parent.parent.resolve()
if str(_backend_dir) not in os.environ.get("PYTHONPATH", ""):
    os.environ["PYTHONPATH"] = str(_backend_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

import sys as _sys
if str(_backend_dir) not in _sys.path:
    _sys.path.insert(0, str(_backend_dir))

# 设置测试隔离的 audit.db 路径
_test_data_dir = _backend_dir / ".pytest-data"
_test_data_dir.mkdir(exist_ok=True)
os.environ["THUNDERBOX_DATA_DIR"] = str(_test_data_dir)


# ---------------------------------------------------------------------------
# 导入（必须在环境变量设置之后）
# ---------------------------------------------------------------------------

# 与 main.py 一致的条件导入策略
try:
    from backend.audit import (
        write_audit,
        query_audit,
        sanitize_body,
        _init_db,
        _DB_PATH,
    )
except ModuleNotFoundError:
    from audit import (
        write_audit,
        query_audit,
        sanitize_body,
        _init_db,
        _DB_PATH,
    )


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

import asyncio


def run_sync(coro):
    """在事件循环中运行异步函数（测试用）"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test: sanitize_body — 敏感字段过滤
# ---------------------------------------------------------------------------

class TestSanitizeBody:
    def test_redacts_git_token(self):
        body = b'{"name":"test","git_token":"s3cr3t"}'
        result = sanitize_body(body)
        assert "s3cr3t" not in result
        assert "REDACTED" in result
        assert "test" in result

    def test_redacts_password(self):
        body = b'{"password":"hunter2"}'
        result = sanitize_body(body)
        assert "hunter2" not in result

    def test_redacts_api_key(self):
        body = b'{"api_key":"abcd1234"}'
        result = sanitize_body(body)
        assert "abcd1234" not in result

    def test_preserves_normal_fields(self):
        body = b'{"name":"my-app","port":8000}'
        result = sanitize_body(body)
        assert "my-app" in result
        assert "8000" in result

    def test_none_body_returns_none(self):
        assert sanitize_body(None) is None

    def test_empty_body_returns_none(self):
        assert sanitize_body(b"") is None


# ---------------------------------------------------------------------------
# Test: write_audit — 写入审计记录
# ---------------------------------------------------------------------------

class TestWriteAudit:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """每个测试前初始化临时数据库"""
        os.environ["THUNDERBOX_DATA_DIR"] = str(_test_data_dir)
        run_sync(_init_db())
        yield

    def test_write_audit_inserts_record(self):
        """write_audit 成功写入一条记录"""
        run_sync(write_audit(
            action="deploy",
            method="POST",
            path="/api/apps/test-id/deploy",
            result="success",
            app_id="test-id",
            app_name="test-app",
            message="deploy started",
            duration_ms=1200,
        ))
        result = run_sync(query_audit(page=1, page_size=10))
        assert result["total"] >= 1
        item = result["items"][0]
        assert item["action"] == "deploy"
        assert item["app_id"] == "test-id"
        assert item["app_name"] == "test-app"
        assert item["result"] == "success"
        assert item["duration_ms"] == 1200

    def test_write_audit_error_result(self):
        """失败操作也记录"""
        run_sync(write_audit(
            action="create_app",
            method="POST",
            path="/api/apps",
            result="error",
            message="HTTP 400",
        ))
        result = run_sync(query_audit(page=1, page_size=10))
        item = result["items"][0]
        assert item["result"] == "error"
        assert item["action"] == "create_app"


# ---------------------------------------------------------------------------
# Test: query_audit — 分页查询
# ---------------------------------------------------------------------------

class TestQueryAudit:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """每个测试前初始化并写入多条记录"""
        os.environ["THUNDERBOX_DATA_DIR"] = str(_test_data_dir)
        run_sync(_init_db())
        # 写入 5 条记录
        for i in range(5):
            run_sync(write_audit(
                action="deploy" if i % 2 == 0 else "control",
                method="POST",
                path=f"/api/apps/app-{i}/deploy",
                result="success" if i % 2 == 0 else "error",
                app_id=f"app-{i}",
                app_name=f"App {i}",
            ))
        yield

    def test_query_audit_returns_items(self):
        """查询返回 items 列表"""
        result = run_sync(query_audit(page=1, page_size=10))
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "pages" in result
        assert result["total"] >= 5

    def test_query_audit_pagination(self):
        """分页正确：page_size=2 返回 2 条"""
        result = run_sync(query_audit(page=1, page_size=2))
        assert len(result["items"]) == 2
        assert result["total"] >= 5
        assert result["page"] == 1

    def test_query_audit_filter_by_action(self):
        """按 action 筛选"""
        result = run_sync(query_audit(page=1, page_size=10, action="deploy"))
        for item in result["items"]:
            assert item["action"] == "deploy"

    def test_query_audit_filter_by_app_id(self):
        """按 app_id 筛选"""
        result = run_sync(query_audit(page=1, page_size=10, app_id="app-0"))
        for item in result["items"]:
            assert item["app_id"] == "app-0"

    def test_query_audit_filter_by_result(self):
        """按 result 筛选"""
        result = run_sync(query_audit(page=1, page_size=10, result="success"))
        for item in result["items"]:
            assert item["result"] == "success"

    def test_query_audit_order_by_time_desc(self):
        """结果按时间倒序"""
        result = run_sync(query_audit(page=1, page_size=10))
        items = result["items"]
        for i in range(len(items) - 1):
            assert items[i]["ts"] >= items[i + 1]["ts"]

    def test_query_audit_page_2(self):
        """第 2 页返回不同记录"""
        result1 = run_sync(query_audit(page=1, page_size=2))
        result2 = run_sync(query_audit(page=2, page_size=2))
        ids1 = {item["id"] for item in result1["items"]}
        ids2 = {item["id"] for item in result2["items"]}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Test: audit endpoint via TestClient
# ---------------------------------------------------------------------------

class TestAuditEndpoint:
    """通过 FastAPI TestClient 测试 /api/audit 端点"""

    @pytest.fixture(autouse=True)
    def setup(self):
        os.environ["THUNDERBOX_DATA_DIR"] = str(_test_data_dir)
        import sys
        if str(_backend_dir) not in sys.path:
            sys.path.insert(0, str(_backend_dir))
        from main import app
        from fastapi.testclient import TestClient
        # 初始化 DB
        run_sync(_init_db())
        # 写入测试记录
        run_sync(write_audit(
            action="deploy",
            method="POST",
            path="/api/apps/test-id/deploy",
            result="success",
            app_id="test-id",
        ))
        yield

    def test_get_audit_returns_200(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_audit_pagination_params(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/audit?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_get_audit_filter_params(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/audit?action=deploy&result=success")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["action"] == "deploy"
            assert item["result"] == "success"

    def test_get_audit_invalid_page_normalizes(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/audit?page=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1  # 归一化为 1

    def test_get_audit_page_size_cap(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/audit?page_size=500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 50  # 上限 200，归一化为 50
