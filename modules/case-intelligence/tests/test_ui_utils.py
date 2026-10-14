# =============================================
# test_ui_utils.py - 健康度口径统一（ui/utils.compute_health）
# 可 pytest 收集，亦可直接运行: python3 tests/test_ui_utils.py
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.utils import compute_health, HEALTH_TOTAL  # noqa: E402


def test_all_fields_present():
    case = {"case_number": "A", "plaintiff": "甲", "defendant": "乙", "cause": "案由", "court": "法院"}
    r = compute_health(case, artifact_count=3)
    assert r["health"] == 100
    assert r["passed"] == HEALTH_TOTAL == 6


def test_missing_fields_and_no_artifacts():
    case = {"case_number": "A", "plaintiff": "", "defendant": None, "cause": "", "court": ""}
    r = compute_health(case, artifact_count=0)
    assert r["passed"] == 1
    assert r["health"] == int(1 / 6 * 100)


def test_artifacts_count_as_check():
    case = {"case_number": "A", "plaintiff": "", "defendant": "", "cause": "", "court": ""}
    r = compute_health(case, artifact_count=1)
    assert r["passed"] == 2  # 案号 + 提取物
    assert any("提取物(1个)" in label for _, label in r["checks"])


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