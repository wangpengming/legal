# =============================================
# case-intelligence 测试配置
# =============================================
import os
import sys
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ▓§7.5 数据隔离（强制）：所有 src 模块（database/artifact_store 等）在 import 时
# 读取 DATA_DIR → 必须在任何 src 导入前指向独立测试目录，禁止直连生产 data/
# （历史事故：未隔离时测试曾向真实库写入 TestUser 垃圾数据）。
os.environ.setdefault("DATA_DIR", str(PROJECT_ROOT / ".pytest-data"))

# 测试数据目录
TEST_DATA_DIR = PROJECT_ROOT / "tests" / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)

# 测试数据库（隔离）
TEST_DB_PATH = PROJECT_ROOT / "tests" / "test_case_registry.db"


@pytest.fixture
def test_db_path(tmp_path):
    """测试数据库路径"""
    return tmp_path / "test.db"


@pytest.fixture
def sample_case_data():
    """示例案件数据"""
    return {
        "case_number": "(2024)京0491民初12345号",
        "case_name": "测试案件",
        "plaintiff": "测试原告",
        "defendant": "测试被告",
        "cause": "著作权侵权",
        "court": "北京互联网法院",
    }


@pytest.fixture
def sample_artifact_data():
    """示例 Artifact 数据"""
    return {
        "case_id": "test-case-id",
        "artifact_type": "D1",
        "title": "事实认定",
        "content": "# D1: 事实认定\n\n## 案件背景\n测试内容",
    }
