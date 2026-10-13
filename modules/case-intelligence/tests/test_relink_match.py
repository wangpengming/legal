# =============================================
# test_relink_match.py - 孤儿归位的名称匹配（bigram 覆盖率，内存库）
# 可 pytest 收集，亦可直接运行: python3 tests/test_relink_match.py
# =============================================
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import relink_artifacts as ra  # noqa: E402


def _con(names):
    con = sqlite3.connect(":memory:")
    con.execute("create table cases (id text primary key, case_name text)")
    for i, n in enumerate(names):
        con.execute("insert into cases values (?, ?)", (f"id{i:04d}", n))
    con.commit()
    return con


def test_bigrams_splits_cjk_runs_and_strips_suffix():
    g = ra._bigrams("浙江广电诉雷石:广汽埃安案件")
    assert "浙江" in g and "雷石" in g and "广汽" in g
    assert "案件" not in g  # 通用后缀已被剥离


def test_coverage_high_for_related_low_for_unrelated():
    og = ra._bigrams("浙江广电诉雷石:广汽埃安案件")
    near = ra._coverage(og, "浙江广播电视集团诉雷石、广汽埃安、上海浦连汽车租赁公司-信息网络传播权纠纷")
    far = ra._coverage(og, "广州立峰诉雷石著作权权属、侵权纠纷案")
    assert near > 0.6 > far


def test_suggest_exact_match():
    con = _con(["某某诉雷石案"])
    m = ra._suggest_match(con, "某某诉雷石案")
    assert m["mode"] == "exact" and m["id"] == "id0000"


def test_suggest_strong_vs_ambiguous():
    con = _con([
        "浙江广播电视集团诉雷石、广汽埃安、上海浦连汽车租赁公司-信息网络传播权纠纷",
        "传世乐坊诉雷石、理想、广汽埃安等2案-HS",
    ])
    m = ra._suggest_match(con, "浙江广电诉雷石:广汽埃安案件")
    assert m["mode"] in ("strong", "ambiguous")
    assert m["candidates"][0][1] == "id0000"  # 浙江广电 案应排第一


def test_suggest_none_for_unrelated():
    con = _con(["完全无关的另一桩买卖合同纠纷案"])
    m = ra._suggest_match(con, "腾讯音乐诉北京雷石侵权纠纷案")
    assert m["mode"] == "none"


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