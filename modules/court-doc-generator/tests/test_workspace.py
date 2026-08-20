"""测试 workspace 工作空间管理（F-048）。"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# 测试前切换数据目录到临时位置，避免污染真实数据
import config as _config_module


@pytest.fixture(autouse=True)
def _isolate_workspace_data(monkeypatch, tmp_path):
    """将 workspace 数据目录指向临时目录，test 间互不干扰。"""
    test_data = tmp_path / "data"
    test_data.mkdir()
    monkeypatch.setattr(
        "workspace.DATA_DIR", test_data, raising=False
    )
    monkeypatch.setattr(
        "workspace.WORKSPACE_META_DB", test_data / "workspaces.db", raising=False
    )
    monkeypatch.setattr(
        "workspace.WORKSPACES_DIR", test_data / "workspaces", raising=False
    )
    monkeypatch.setattr(
        "workspace.STATIC_DIR", tmp_path / "static", raising=False
    )
    monkeypatch.setattr(
        "workspace.PROJECT_ROOT", tmp_path, raising=False
    )
    # 确保干净状态
    import workspace as ws
    ws.init_workspace_db()


def test_hash_and_verify_password():
    """密码哈希 → 验证正确 → 拒绝错误密码。"""
    import workspace as ws

    h = ws.hash_password("test123")
    assert "$" in h
    assert len(h.split("$")[0]) == 64  # salt hex
    assert len(h.split("$")[1]) == 64  # hash hex

    assert ws.verify_password("test123", h) is True
    assert ws.verify_password("wrong", h) is False
    assert ws.verify_password("", h) is False
    assert ws.verify_password("test123", "bad$hash") is False


def test_create_and_verify_workspace():
    """创建 workspace → 验证密码 → 拒绝错误密码。"""
    import workspace as ws

    ws_id = ws.create_workspace("测试用户", "pass123")
    assert ws_id is not None
    assert len(ws_id) == 8  # UUID 短哈希

    # 正确密码
    assert ws.verify_workspace("测试用户", "pass123") == ws_id
    # 错误密码
    assert ws.verify_workspace("测试用户", "wrong") is None
    # 用户不存在
    assert ws.verify_workspace("不存在的用户", "pass") is None


def test_create_duplicate_name():
    """重复注册同名 workspace 应抛出 ValueError。"""
    import workspace as ws

    ws.create_workspace("重复名", "p1")
    with pytest.raises(ValueError, match="已存在"):
        ws.create_workspace("重复名", "p2")


def test_create_empty_name():
    """空名称应拒绝。"""
    import workspace as ws

    with pytest.raises(ValueError, match="不能为空"):
        ws.create_workspace("", "pass")
    with pytest.raises(ValueError, match="不能为空"):
        ws.create_workspace("   ", "pass")


def test_create_empty_password():
    """空密码应拒绝。"""
    import workspace as ws

    with pytest.raises(ValueError, match="不能为空"):
        ws.create_workspace("用户", "")


def test_list_workspaces():
    """列出所有 workspace（不含密码）。"""
    import workspace as ws

    ws.create_workspace("用户A", "p1")
    ws.create_workspace("用户B", "p2")

    ws_list = ws.list_workspaces()
    assert len(ws_list) >= 2
    names = {w["name"] for w in ws_list}
    assert "用户A" in names
    assert "用户B" in names

    # 不应包含密码哈希
    for w in ws_list:
        assert "password_hash" not in w


def test_workspace_directory_created():
    """创建 workspace 后，目录结构应自动生成。"""
    import workspace as ws

    ws_id = ws.create_workspace("目录测试", "pass")
    ws_dir = ws.WORKSPACES_DIR / ws_id

    assert ws_dir.exists()
    assert (ws_dir / "outputs").exists()
    assert (ws_dir / "agents").exists()


def test_migrate_legacy_idempotent():
    """迁移函数幂等：第二次调用返回 None。"""
    import workspace as ws

    # 没有旧数据 → 返回 None
    result = ws.migrate_legacy_data()
    assert result is None


def test_migrate_legacy_with_old_db(monkeypatch, tmp_path):
    """有旧 court_matters.db 时，迁移应创建默认 workspace。"""
    import workspace as ws

    test_data = tmp_path / "data"
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("workspace.DATA_DIR", test_data, raising=False)
    monkeypatch.setattr(
        "workspace.WORKSPACE_META_DB", test_data / "workspaces.db", raising=False
    )
    monkeypatch.setattr(
        "workspace.WORKSPACES_DIR", test_data / "workspaces", raising=False
    )
    monkeypatch.setattr("workspace.STATIC_DIR", tmp_path / "static", raising=False)
    monkeypatch.setattr("workspace.PROJECT_ROOT", tmp_path, raising=False)
    # config 模块也需同步 monkeypatch（get_db_path 等函数用 config.DATA_DIR）
    monkeypatch.setattr("config.DATA_DIR", test_data, raising=False)

    ws.init_workspace_db()

    # 创建模拟旧 DB
    import sqlite3
    legacy_db = test_data / "court_matters.db"
    conn = sqlite3.connect(str(legacy_db))
    conn.execute("CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    assert legacy_db.exists()

    # 执行迁移
    ws_id = ws.migrate_legacy_data()
    assert ws_id is not None

    # 旧 DB 已移动
    assert not legacy_db.exists()

    # 新 DB 在 workspace 中
    from config import get_db_path
    assert get_db_path(ws_id).exists()

    # 标记文件已写入
    assert (test_data / ".migration_done").exists()

    # 第二次调用应返回 None（幂等）
    assert ws.migrate_legacy_data() is None


def test_config_workspace_paths(monkeypatch, tmp_path):
    """测试 config.py 的 workspace 路径函数。"""
    import config as cfg

    test_data = tmp_path / "data"
    monkeypatch.setattr(cfg, "DATA_DIR", test_data)

    ws_id = "abc12345"
    db_path = cfg.get_db_path(ws_id)
    assert db_path == test_data / "workspaces" / ws_id / "court_matters.db"
    assert db_path.parent.exists()

    outputs = cfg.get_outputs_dir(ws_id)
    assert outputs == test_data / "workspaces" / ws_id / "outputs"
    assert outputs.exists()

    agent_dir = cfg.get_agent_dir(ws_id, 42)
    assert agent_dir == test_data / "workspaces" / ws_id / "agents" / "42"
    assert agent_dir.exists()