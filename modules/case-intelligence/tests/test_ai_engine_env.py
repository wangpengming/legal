# =============================================
# test_ai_engine_env.py — 密钥 env:// 解析（F3，安全红线 §6.2）
# 对应 SPEC：docs/SPEC-ui-upload.md §4
# =============================================
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.ai_engine import resolve_env_ref
from src.langchain_llm import get_minimax_api_key


# ---------- resolve_env_ref ----------

def test_env_ref_resolves_env_value(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-123")
    assert resolve_env_ref("env://MINIMAX_API_KEY") == "sk-test-123"


def test_env_ref_missing_var_raises_with_hint(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with pytest.raises(KeyError) as ei:
        resolve_env_ref("env://MINIMAX_API_KEY")
    assert "MINIMAX_API_KEY" in str(ei.value)


def test_env_ref_passthrough_plain_string():
    assert resolve_env_ref("sk-plain-passthrough") == "sk-plain-passthrough"
    assert resolve_env_ref("") == ""


def test_env_ref_passthrough_other_scheme():
    assert resolve_env_ref("file:///tmp/x") == "file:///tmp/x"


# ---------- get_minimax_api_key ----------

def test_get_key_env_priority(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-env")
    assert get_minimax_api_key() == "sk-from-env"


def test_get_key_yaml_env_ref_without_env_returns_none(monkeypatch):
    """ai_engines.yaml 为 env://MINIMAX_API_KEY 且环境未设置 → 返回 None（降级路径）。"""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert get_minimax_api_key() is None


def test_get_key_yaml_env_ref_with_env_returns_value(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-env-yaml")
    assert get_minimax_api_key() == "sk-from-env-yaml"


# ---------- 安全回归：配置文件无明文密钥 ----------

def test_ai_engines_yaml_contains_no_plaintext_sk():
    """安全红线回归：ai_engines.yaml 不得再出现明文 sk- 密钥。"""
    content = (_PROJECT_ROOT / "ai_engines.yaml").read_text(encoding="utf-8")
    assert "sk-" not in content
    assert "env://MINIMAX_API_KEY" in content