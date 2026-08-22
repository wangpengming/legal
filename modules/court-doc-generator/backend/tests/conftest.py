"""pytest 全局配置：数据隔离（防测试污染生产数据）。

背景：TestClient(app) 直连真实 FastAPI 应用，Settings 单例在 import 时实例化。
因此必须在任何测试模块 import app 之前，把 DATA_DIR 指向临时目录 ——
注册表（workspaces.db）与各 workspace 业务库均基于 DATA_DIR，一条环境变量全量隔离。

教训：此前的 pytest 直连生产注册表，累计产生 400+ 个 TestUser_* workspace（2026-08-22 清理）。
"""
import os
import shutil
from pathlib import Path

_TEST_DATA_DIR = Path(__file__).parent.parent.parent / ".pytest-data"
os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)


def pytest_sessionstart(session):
    """清掉上次运行残留，保证每次从干净目录开始。"""
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
    _TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    """测试结束后清理临时数据目录。"""
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)