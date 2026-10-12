# =============================================
# test_lark_bot.py - 飞书 Bot 命令处理测试（无外部依赖）
# 覆盖: 命令解析 / list/search/register/detail/report/help / Webhook 事件
# 使用临时 SQLite，不触碰生产 data/case_registry.db
# 可 pytest 收集，亦可直接运行: python3 tests/test_lark_bot.py
# =============================================
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))
sys.path.insert(0, str(_HERE.parent))

from lark_bot import CaseBot, LarkWebhookHandler  # noqa: E402


def _make_db():
    """创建与 lark_bot 查询/写入字段一致的临时数据库。"""
    tmp = Path(tempfile.mkdtemp()) / "bot_test.db"
    conn = sqlite3.connect(str(tmp))
    conn.executescript(
        """
        CREATE TABLE cases (
            id TEXT PRIMARY KEY, case_number TEXT, case_name TEXT,
            plaintiff TEXT, defendant TEXT, cause TEXT, court TEXT,
            year INTEGER, quality TEXT, status TEXT,
            created_at TEXT, entry_method TEXT
        );
        CREATE TABLE artifacts (
            id TEXT PRIMARY KEY, case_id TEXT, artifact_type TEXT,
            title TEXT, version INTEGER
        );
        CREATE TABLE templates (id TEXT PRIMARY KEY, name TEXT, category TEXT);
        """
    )
    conn.commit()
    conn.close()
    return tmp


def _bot():
    return CaseBot(db_path=_make_db())


def test_unknown_command_returns_error():
    bot = _bot()
    out = bot.handle_message("hello world")
    assert out.startswith("❌")


def test_bare_case_prefix_lists():
    bot = _bot()
    out = bot.handle_message("/case")
    assert "案件列表" in out or "暂无案件记录" in out


def test_list_empty_returns_hint():
    bot = _bot()
    assert "暂无案件记录" in bot.handle_message("/case list")


def test_help_text_contains_commands():
    bot = _bot()
    out = bot.handle_message("/case help")
    assert "/case list" in out
    assert "/case search" in out


def test_format_error():
    bot = _bot()
    assert bot._format_error("boom") == "❌ boom"


def test_register_then_list_and_detail():
    bot = _bot()
    msg = (
        "/case register\n"
        "案号: (2024)京0491民初123号\n"
        "原告: 甲公司\n"
        "被告: 乙公司\n"
        "案由: 著作权侵权\n"
        "法院: 北京互联网法院"
    )
    reg = bot.handle_message(msg)
    assert "登记成功" in reg

    lst = bot.handle_message("/case list")
    assert "甲公司" in lst

    detail = bot.handle_message("/case detail (2024)京0491民初123号")
    assert "乙公司" in detail
    assert "北京互联网法院" in detail


def test_search_hit_and_miss():
    bot = _bot()
    bot.handle_message(
        "/case register\n案号: (2024)京0491民初9号\n原告: 腾讯音乐\n被告: 雷石公司\n案由: 侵权"
    )
    hit = bot.handle_message("/case search 腾讯")
    assert "腾讯音乐" in hit

    miss = bot.handle_message("/case search 不存在的关键词")
    assert "未找到" in miss


def test_search_without_keyword_errors():
    bot = _bot()
    out = bot.handle_message("/case search")
    assert out.startswith("❌")


def test_report_runs_on_empty_db():
    bot = _bot()
    out = bot.handle_message("/case report")
    assert "案件总数" in out


def test_detail_not_found():
    bot = _bot()
    out = bot.handle_message("/case detail does-not-exist")
    assert "未找到案件" in out


def test_webhook_text_event_ok():
    bot = _bot()
    handler = LarkWebhookHandler(bot)
    event = {"event": {"msg_type": "text", "content": json.dumps({"text": "/case help"})}}
    resp = handler.handle_event(event)
    assert resp["status_code"] == 0
    assert "/case list" in resp["data"]["content"]


def test_webhook_malformed_content_returns_error():
    bot = _bot()
    handler = LarkWebhookHandler(bot)
    # content 为 dict（非 JSON 字符串）→ json.loads 失败 → 走异常分支
    event = {"event": {"msg_type": "text", "content": {"text": "/case help"}}}
    resp = handler.handle_event(event)
    assert resp["status_code"] == 1


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