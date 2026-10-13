# =============================================
# test_court_resolver.py - 案号派生法院（纯函数，无外部依赖）
# 可 pytest 收集，亦可直接运行: python3 tests/test_court_resolver.py
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from court_resolver import extract_court_token, resolve_court  # noqa: E402


def _check(desc, got, want):
    assert got == want, f"{desc}: got={got!r} want={want!r}"


def test_token_extraction():
    _check("京0104", extract_court_token("（2024）京0104民初14030号"), "京0104")
    _check("京73", extract_court_token("(2024)京73民终2207号"), "京73")
    _check("晋民终→晋", extract_court_token("(2022)晋民终508号"), "晋")
    _check("京仲", extract_court_token("（2023）京仲100号"), "京仲")
    _check("半角括号", extract_court_token("(2024)粤0111民诉18110号"), "粤0111")
    _check("空", extract_court_token(""), "")
    _check("无年份", extract_court_token("京0105民初1号"), "")


def test_resolve_verified():
    _check("京0491", resolve_court("(2024)京0491民初1152号"), "北京互联网法院")
    _check("京0105", resolve_court("(2023)京0105民初50308号"), "北京市朝阳区人民法院")
    _check("京73", resolve_court("(2024)京73民终2207号"), "北京知识产权法院")
    _check("沪0115", resolve_court("(2022)沪0115民初79405号"), "上海市浦东新区人民法院")
    _check("沪0112", resolve_court("(2024)沪0112民初1号"), "上海市闵行区人民法院")
    _check("津0101", resolve_court("(2024)津0101民初1号"), "天津市和平区人民法院")
    _check("川0104", resolve_court("(2023)川0104民初25328号"), "四川省成都市锦江区人民法院")
    _check("川0193", resolve_court("(2024)川0193民初9413号"), "四川自由贸易试验区人民法院")
    _check("豫0191", resolve_court("(2023)豫0191民初26745号"), "河南省郑州高新技术产业开发区人民法院")
    _check("鲁0481", resolve_court("(2022)鲁0481民初491号"), "山东省滕州市人民法院")
    _check("琼0271", resolve_court("(2019)琼0271民初10326号"), "海南省三亚市城郊人民法院")
    _check("粤0115", resolve_court("(2024)粤0115民初5950号"), "广东省广州市南沙区人民法院")
    _check("粤0192", resolve_court("(2024)粤0192民初3229号"), "广州互联网法院")
    _check("粤0402", resolve_court("(2023)粤0402民初8677号"), "广东省珠海市香洲区人民法院")


def test_resolve_province_high_court():
    _check("晋民终", resolve_court("(2022)晋民终508号"), "山西省高级人民法院")
    _check("粤民终", resolve_court("(2023)粤民终100号"), "广东省高级人民法院")


def test_token_space_between_code_and_digits():
    # 案号常写作「（2025）鲁 0281 民初…」：代字与数字间空格不得退化为省高院（不臆断）
    _check("鲁 0281 token", extract_court_token("（2025）鲁 0281 民初 5427 号"), "鲁0281")
    _check("鲁 0281 未收录→空", resolve_court("（2025）鲁 0281 民初 5427 号"), "")
    # 已收录代字带空格仍可正确解析
    _check("川 0193 空格", resolve_court("（2025）川 0193 民初 13392 号"), "四川自由贸易试验区人民法院")


def test_resolve_unknown_stays_empty():
    # 未收录的基层法院编号 → 留空（不臆断）
    _check("粤0111?", resolve_court("(2024)粤0111民诉18110号"), "")
    _check("仲裁", resolve_court("（2023）京仲100号"), "")
    _check("空", resolve_court(None), "")


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