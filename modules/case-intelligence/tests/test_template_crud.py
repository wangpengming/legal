# =============================================
# test_template_crud.py - 模板 update/delete（DB + 文件同步）
# 可 pytest 收集，亦可直接运行: python3 tests/test_template_crud.py
# =============================================
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import database as db  # noqa: E402
from src import template_store  # noqa: E402


def _tmp_db():
    return Path(tempfile.mkdtemp()) / "test.db"


def test_update_template_fields():
    dbp = _tmp_db()
    t = db.create_template(name="旧名", content="旧内容", category="答辩状", db_path=dbp)
    updated = db.update_template(t["id"], db_path=dbp, name="新名", content="新内容")
    assert updated["name"] == "新名"
    assert updated["content"] == "新内容"
    assert updated["category"] == "答辩状"  # 未传 → 不变


def test_update_template_ignores_none_and_unknown():
    dbp = _tmp_db()
    t = db.create_template(name="名", content="内容", category="答辩状", db_path=dbp)
    updated = db.update_template(t["id"], db_path=dbp, content=None, id="hacked")
    assert updated["content"] == "内容"
    assert updated["id"] == t["id"]


def test_update_template_invalid_category():
    dbp = _tmp_db()
    t = db.create_template(name="名", content="内容", category="答辩状", db_path=dbp)
    try:
        db.update_template(t["id"], db_path=dbp, category="不存在的分类")
    except ValueError:
        return
    raise AssertionError("非法分类应抛 ValueError")


def test_store_update_rewrites_file(tmp_path=None):
    # template_store 写文件到模块 output_templates/；此处验证 DB 侧 + 返回值
    dbp = _tmp_db()
    t = template_store.create_template(name="归档模板A", content="C1", category="其他", db_path=dbp)
    assert t["file_path"] and Path(t["file_path"]).exists()
    updated = template_store.update_template(t["id"], name="归档模板A2", content="C2", db_path=dbp)
    assert updated["name"] == "归档模板A2"
    # 清理生成的模板文件，避免污染仓库
    for p in (t.get("file_path"), updated.get("file_path")):
        if p and Path(p).exists():
            Path(p).unlink()
    template_store.delete_template(t["id"], db_path=dbp)


def test_delete_template_removes_row():
    dbp = _tmp_db()
    t = db.create_template(name="待删", content="x", category="其他", db_path=dbp)
    db.delete_template(t["id"], db_path=dbp)
    assert db.get_template(t["id"], db_path=dbp) is None


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