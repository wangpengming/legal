# =============================================
# test_case_matcher.py - 相似案件匹配（规则打分）
# 可 pytest 收集，亦可直接运行: python3 tests/test_case_matcher.py
# =============================================
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.case_matcher import match_cases  # noqa: E402
from src.database import create_case, create_artifact  # noqa: E402


def _tmp_db():
    return Path(tempfile.mkdtemp()) / "test.db"


def _seed(dbp):
    base = create_case(
        case_name="基准案", case_number="(2024)粤0105民初100号",
        cause="著作权侵权", court="广州市海珠区人民法院", year=2024,
        scene="实体KTV", db_path=dbp,
    )
    same_cause = create_case(
        case_name="同案由案", case_number="(2024)粤0105民初101号",
        cause="著作权侵权", year=2024, scene="实体KTV", db_path=dbp,
    )
    diff_cause = create_case(
        case_name="异案由案", case_number="(2022)京0491民初9号",
        cause="商标侵权", year=2022, scene="线上平台", db_path=dbp,
    )
    for t in ("case_key_facts", "evidence_structure"):
        create_artifact(case_id=base["id"], artifact_type=t, title=t, content="x", db_path=dbp)
        create_artifact(case_id=same_cause["id"], artifact_type=t, title=t, content="x", db_path=dbp)
    return base, same_cause, diff_cause


def test_same_cause_scores_higher():
    dbp = _tmp_db()
    base, same, diff = _seed(dbp)
    results = match_cases(base["id"], limit=5, db_path=dbp)
    assert results, "应有匹配结果"
    assert results[0]["id"] == same["id"], f"同案由案应排第一，实际 {results[0]['case_name']}"
    assert results[0]["score"] > 0
    # reasons 覆盖案由/年份/场景/维度
    joined = "；".join(results[0]["reasons"])
    assert "案由一致" in joined


def test_zero_overlap_excluded():
    dbp = _tmp_db()
    base = create_case(case_name="孤立案", cause="", db_path=dbp)
    create_case(case_name="另一案", cause="", db_path=dbp)
    results = match_cases(base["id"], limit=5, db_path=dbp)
    assert results == [], "无任何信号重合时应返回空"


def test_unknown_case_returns_empty():
    dbp = _tmp_db()
    assert match_cases("nonexistent", db_path=dbp) == []


def test_limit_applied():
    dbp = _tmp_db()
    base, same, diff = _seed(dbp)
    results = match_cases(base["id"], limit=1, db_path=dbp)
    assert len(results) == 1


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