"""测试 generator.sanitize_filename：文件名清理逻辑。"""
from generator import sanitize_filename


def test_safe_filename_unchanged():
    """正常文件名应保持不变（只保留 ASCII + 中文 + 数字）。"""
    assert sanitize_filename("（2026）京0101民初1234号") == "（2026）京0101民初1234号"


def test_unsafe_chars_replaced():
    """路径分隔符、shell 元字符应被替换为下划线。"""
    assert sanitize_filename("a/b\\c:d*e?f\"g<h>i|j") == "a_b_c_d_e_f_g_h_i_j"


def test_strip_leading_trailing_dots_and_spaces():
    """首尾空格 / 点应被去掉（Windows 兼容）。"""
    assert sanitize_filename("  ..foo..  ") == "foo"


def test_empty_string():
    """空字符串应返回下划线。"""
    assert sanitize_filename("") == "_"


def test_only_unsafe():
    """全是不安全字符时返回下划线。"""
    assert sanitize_filename("///") == "_"