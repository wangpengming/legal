# =============================================
# test_database_schema.py - DB 建表/迁移/字段透传（隔离临时库，不碰生产数据）
# 可 pytest 收集，亦可直接运行: python3 tests/test_database_schema.py
# =============================================
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import database as db  # noqa: E402


def _cols(path, table):
    con = sqlite3.connect(str(path))
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def test_fresh_db_supports_all_case_fields():
    """P0：全新库必须能直接 INSERT create_case 的全部字段（历史事故回归）。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "fresh.db"
        rec = db.create_case(
            case_name="测试案", case_number="（2024）京0491民初1号",
            plaintiff="甲", defendant="乙", cause="著作权", court="北京互联网法院",
            year=2024, result="胜诉", source_files="a.pdf", scene="车载KTV",
            defendant_auth_status="未获授权", quality="B", db_path=p,
        )
        assert rec["id"]
        assert _cols(p, "cases") >= {"court", "year", "source_files", "scene", "quality"}


def test_fresh_db_supports_artifact_governance_fields():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "fresh.db"
        case = db.create_case(case_name="测试案", db_path=p)
        art = db.create_artifact(
            case["id"], "case_key_facts", "D1: 事实认定", content="## x\n有料",
            generation_method="llm", model_version="MiniMax-Text-01", db_path=p,
        )
        con = sqlite3.connect(str(p))
        try:
            row = con.execute(
                "select generation_method, model_version from artifacts where id=?",
                (art["id"],),
            ).fetchone()
        finally:
            con.close()
        assert row == ("llm", "MiniMax-Text-01")


def test_migration_adds_missing_columns_to_legacy_db():
    """P0：老库（缺 court/scene/parent_id 等列）须被幂等迁移补齐。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "legacy.db"
        con = sqlite3.connect(str(p))
        con.executescript(
            """
            CREATE TABLE cases (
                id TEXT PRIMARY KEY, case_name TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )
        con.commit()
        con.close()

        # 触发迁移（_get_conn 内部 _init_schema → _ensure_columns），随后应能写全字段
        rec = db.create_case(
            case_name="老库案", court="北京市朝阳区人民法院", year=2023,
            scene="实体KTV", quality="C", db_path=p,
        )
        art = db.create_artifact(
            rec["id"], "case_key_facts", "D1: 事实认定", content="x",
            generation_method="manual", parent_id=None, db_path=p,
        )
        assert art["id"]
        assert _cols(p, "cases") >= {"court", "year", "scene", "quality"}
        assert _cols(p, "artifacts") >= {"content", "parent_id", "generation_method"}


def test_naming_single_source_of_truth():
    """P4：D1-D5 维度映射唯一真值，取值必须都在 ARTIFACT_TYPES 内且有中文名。"""
    assert set(db.DIMENSION_ARTIFACT_TYPES) == set(db.DIMENSIONS)
    assert set(db.DIMENSION_ARTIFACT_TYPES.values()) <= set(db.ARTIFACT_TYPES)
    assert set(db.ARTIFACT_TYPE_NAMES) == set(db.ARTIFACT_TYPES)


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