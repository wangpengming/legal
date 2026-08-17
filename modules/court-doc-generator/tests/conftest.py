"""conftest.py：pytest 全局 fixtures 与环境隔离。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_data_dir(monkeypatch, tmp_path):
    """每个测试都使用临时 data 目录，避免污染真实数据库。"""
    monkeypatch.setenv("COURT_DATA_DIR", str(tmp_path))