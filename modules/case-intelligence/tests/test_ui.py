# =============================================
# test_ui.py - UI 层测试（mock streamlit，无外部依赖）
# 覆盖: config 常量 / 登录认证逻辑（ui/auth.py）
# 可 pytest 收集，亦可直接运行: python3 tests/test_ui.py
# =============================================
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))


class _FakeState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


class _FakeST:
    """最小 streamlit 替身：仅覆盖 ui/auth.py 用到的接口。"""

    def __init__(self):
        self.session_state = _FakeState()
        self.warned = []
        self.switched = []

    def warning(self, *args, **kwargs):
        self.warned.append(args)

    def switch_page(self, *args, **kwargs):
        self.switched.append(args)


def _fresh_auth():
    """注入假 streamlit 并（重新）导入 ui.auth，返回 (auth_module, fake_st)。"""
    fake = _FakeST()
    sys.modules["streamlit"] = fake
    sys.modules.pop("ui.auth", None)
    import ui.auth as auth  # noqa: WPS433
    return auth, fake


def _unload():
    sys.modules.pop("ui.auth", None)
    sys.modules.pop("streamlit", None)


def test_config_constants():
    from config import PORT, FALLBACK_PORT, USERS, PAGE_SIZE
    assert PORT == 18503
    assert FALLBACK_PORT == 18504
    assert isinstance(USERS, dict) and USERS
    assert isinstance(PAGE_SIZE, int)


def test_check_auth_initial_false():
    auth, fake = _fresh_auth()
    assert auth.check_auth() is False
    assert fake.session_state.logged_in is False
    _unload()


def test_login_success_and_state():
    auth, fake = _fresh_auth()
    assert auth.login("admin", "admin123") is True
    assert auth.check_auth() is True
    assert fake.session_state.username == "admin"
    _unload()


def test_login_failure_wrong_password():
    auth, fake = _fresh_auth()
    assert auth.login("admin", "wrong-password") is False
    assert fake.session_state.get("logged_in") is not True
    _unload()


def test_login_failure_unknown_user():
    auth, fake = _fresh_auth()
    assert auth.login("nobody", "whatever") is False
    _unload()


def test_logout_clears_state():
    auth, fake = _fresh_auth()
    assert auth.login("test", "test123") is True
    auth.logout()
    assert auth.check_auth() is False
    assert fake.session_state.username is None
    _unload()


def test_require_auth_redirects_when_anonymous():
    auth, fake = _fresh_auth()
    auth.require_auth()
    assert fake.warned, "未登录应给出提示"
    assert fake.switched, "未登录应跳转登录页"
    _unload()


def _run_all():
    import traceback

    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())