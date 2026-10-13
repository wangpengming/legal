# =============================================
# test_markdown_utils.py - 空小节抑制（纯函数，无外部依赖）
# 可 pytest 收集，亦可直接运行: python3 tests/test_markdown_utils.py
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from markdown_utils import strip_empty_sections  # noqa: E402


def test_drops_empty_section():
    md = "## 1. 背景\n有内容\n\n## 2. 空节\n\n## 3. 收尾\n末内容"
    got = strip_empty_sections(md)
    assert "## 2. 空节" not in got
    assert "## 1. 背景" in got and "## 3. 收尾" in got


def test_drops_header_only_table():
    md = "## 1. 证据\n| a | b |\n|---|---|\n\n## 2. 事实\n| h | h |\n| 1 | x |"
    got = strip_empty_sections(md)
    assert "## 1. 证据" not in got      # 只有表头无数据行 → 空
    assert "## 2. 事实" in got          # 表头 + 数据行 → 保留


def test_keeps_all_when_no_empty():
    md = "## 1. A\naa\n\n## 2. B\nbb"
    assert strip_empty_sections(md) == md.strip()


def test_empty_input():
    assert strip_empty_sections("") == ""


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)