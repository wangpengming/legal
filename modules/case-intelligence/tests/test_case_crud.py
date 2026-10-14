# =============================================
# test_case_crud.py - 案件编辑/删除（update_case / delete_case）
# 可 pytest 收集，亦可直接运行: python3 tests/test_case_crud.py
# =============================================
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import (  # noqa: E402
    create_case, get_case, update_case, delete_case,
    create_artifact, count_artifacts_by_case,
)


def _tmp_db():
    return Path(tempfile.mkdtemp()) / "test.db"


def test_update_case_fields():
    dbp = _tmp_db()
    case = create_case(case_name="测试案件", case_number="(2024)京0491民初1号",
                       plaintiff="甲", db_path=dbp)
    updated = update_case(case["id"], db_path=dbp, plaintiff="乙", cause="著作权侵权")
    assert updated["plaintiff"] == "乙"
    assert updated["cause"] == "著作权侵权"
    # 未传字段保持原值
    assert updated["case_number"] == "(2024)京0491民初1号"


def test_update_case_ignores_unknown_fields():
    dbp = _tmp_db()
    case = create_case(case_name="测试案件", db_path=dbp)
    # id / created_at 不在白名单，必须被忽略
    updated = update_case(case["id"], db_path=dbp, id="hacked", created_at="x", notes="ok")
    assert updated["id"] == case["id"]
    assert updated["notes"] == "ok"


def test_update_case_empty_fields_returns_case():
    dbp = _tmp_db()
    case = create_case(case_name="测试案件", db_path=dbp)
    same = update_case(case["id"], db_path=dbp)
    assert same["id"] == case["id"]


def test_delete_case_cascades_artifacts():
    dbp = _tmp_db()
    case = create_case(case_name="测试案件", db_path=dbp)
    create_artifact(case_id=case["id"], artifact_type="case_key_facts",
                    title="事实认定", content="x", db_path=dbp)
    create_artifact(case_id=case["id"], artifact_type="evidence_structure",
                    title="证据体系", content="y", db_path=dbp)
    assert count_artifacts_by_case(case["id"], db_path=dbp) == 2

    delete_case(case["id"], db_path=dbp)
    assert get_case(case["id"], db_path=dbp) is None
    assert count_artifacts_by_case(case["id"], db_path=dbp) == 0


def test_update_case_number_conflict():
    dbp = _tmp_db()
    a = create_case(case_name="A", case_number="(2024)京0491民初1号", db_path=dbp)
    b = create_case(case_name="B", case_number="(2024)京0491民初2号", db_path=dbp)
    try:
        update_case(b["id"], db_path=dbp, case_number="(2024)京0491民初1号")
    except ValueError:
        return
    raise AssertionError("重复案号应抛 ValueError")


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