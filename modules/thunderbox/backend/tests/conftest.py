"""
Thunderbox Console — pytest 配置与全局 Fixture
============================================

测试隔离原则（AGENTS.md §7.5）：
- 所有 pytest 测试必须与真实数据完全隔离
- MCP 测试用 `responses` library mock HTTP 响应，不直连真实 API
- app 操作 fixture 只能创建/操作 legal-thunderbox-test-* 前缀的沙盒应用
- legal-thunderbox.tbox.ktvsky.com 仅用于只读验证
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 路径：确保 backend/ 在 sys.path 中（方便 thunderbox_mcp 导入）
# ---------------------------------------------------------------------------

_backend_dir = Path(__file__).parent.parent.resolve()
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ---------------------------------------------------------------------------
# 测试隔离常量
# ---------------------------------------------------------------------------

# 所有破坏性操作（create/deploy/start/stop/config/db 等）的 app 前缀
APP_NAME_PREFIX = "legal-thunderbox-test-"

# 只读验证目标（真实应用，可用于 read-only 测试）
READONLY_APP_NAME = "legal-thunderbox"


def generate_test_app_name() -> str:
    """生成唯一的测试 app 名称（时间戳 + 随机后缀）"""
    import random

    suffix = f"{int(time.time())}-{random.randint(1000, 9999)}"
    return f"{APP_NAME_PREFIX}{suffix}"


# ---------------------------------------------------------------------------
# 环境变量
# ---------------------------------------------------------------------------

def get_thunderbox_token() -> str:
    """
    从环境变量读取 Bearer token。
    禁止硬编码真实 token。
    """
    token = os.environ.get("THUNDERBOX_TOKEN", "")
    if not token:
        pytest.skip("THUNDERBOX_TOKEN not set in environment")
    return token


# ---------------------------------------------------------------------------
# 临时目录 fixture（测试数据隔离）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Session 级临时数据目录，用于需要文件写入的测试。
    落在 tmp_path_factory 下，每次 session 自动清理。
    """
    return tmp_path_factory.mktemp("thunderbox-test-data")


@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """
    Function 级临时数据目录。
    每次测试函数结束自动清理。
    """
    return tmp_path


# ---------------------------------------------------------------------------
# MCP Token fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def thunderbox_token() -> str:
    """读取真实 THUNDERBOX_TOKEN（只读，不泄露到日志）"""
    token = get_thunderbox_token()
    # 日志中只显示前 4 位
    masked = f"{token[:4]}***{token[-4:]}" if len(token) > 8 else "***"
    print(f"\n[TEST SETUP] Using token: {masked}")
    return token


# ---------------------------------------------------------------------------
# App 名称 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app_name() -> str:
    """生成唯一测试 app 名称（用于 create/deploy/stop 等破坏性测试）"""
    return generate_test_app_name()


# ---------------------------------------------------------------------------
# API Test：重置全局 MCP client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_mcp_client():
    """每个测试前重置 main._client，防止缓存导致 mock 失效"""
    import main
    main._client = None
    main._token = ""
    yield
    # 测试后关闭（如果有）
    if main._client:
        main._client.close()
        main._client = None


# ---------------------------------------------------------------------------
# Audit DB fixture（临时，用于审计测试）
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_db_path(tmp_data_dir: Path) -> Path:
    """返回临时 SQLite 审计数据库路径（测试结束后自动清理）"""
    return tmp_data_dir / "test_audit.db"
