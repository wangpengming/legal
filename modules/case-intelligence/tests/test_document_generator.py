# =============================================
# test_document_generator.py - 文书生成器测试（无外部依赖）
# 覆盖: 文书类型 / 占位符填充 / 上下文构建 / 模板路径 / fallback 路径
# 可 pytest 收集，亦可直接运行: python3 tests/test_document_generator.py
# =============================================
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))
sys.path.insert(0, str(_HERE.parent))

from document_generator import (  # noqa: E402
    DocumentGenerator,
    CaseContext,
    GenerationRequest,
)


def _ctx():
    return CaseContext(
        case_id="c1",
        case_number="(2024)京0491民初123号",
        case_name="甲诉乙案",
        plaintiff="甲公司",
        defendant="乙公司",
        cause="著作权侵权",
        court="北京互联网法院",
    )


def _gen():
    gen = DocumentGenerator()
    # 阻止初始化真实 AI 引擎（避免任何外部调用），保持测试纯净
    gen._init_ai_engine = lambda: None
    gen.ai_engine = None
    return gen


def test_doc_types_mapping():
    assert DocumentGenerator.DOC_TYPES["defense"] == "答辩状"
    assert DocumentGenerator.DOC_TYPES["evidence_objection"] == "质证意见"
    assert DocumentGenerator.DOC_TYPES["court_statement"] == "当庭陈述"
    assert DocumentGenerator.DOC_TYPES["evidence_index"] == "证据目录"


def test_fill_template_replaces_known_placeholders():
    gen = _gen()
    template = "原告:{{plaintiff}} 被告:{{defendant}} 案号:{{case_number}}"
    out = gen._fill_template(template, _ctx())
    assert "甲公司" in out
    assert "乙公司" in out
    assert "(2024)京0491民初123号" in out
    assert "{{" not in out


def test_fill_template_leaves_unknown_placeholder():
    gen = _gen()
    out = gen._fill_template("未知:{{unknown_key}}", _ctx())
    assert "{{unknown_key}}" in out


def test_build_context_contains_case_fields():
    gen = _gen()
    req = GenerationRequest(doc_type="defense", case_context=_ctx())
    ctx_text = gen._build_context(req)
    assert "(2024)京0491民初123号" in ctx_text
    assert "甲公司" in ctx_text
    assert "著作权侵权" in ctx_text


def test_build_context_includes_reference_artifacts():
    gen = _gen()
    req = GenerationRequest(
        doc_type="defense",
        case_context=_ctx(),
        reference_artifacts=[
            {"artifact_type": "D3", "title": "攻防策略", "content": "四层递进论证"}
        ],
    )
    ctx_text = gen._build_context(req)
    assert "D3" in ctx_text
    assert "四层递进论证" in ctx_text


def test_generate_fallback_when_no_template_no_llm():
    gen = _gen()
    req = GenerationRequest(doc_type="defense", case_context=_ctx())
    res = gen.generate(req)
    assert res.success is True
    assert res.source == "fallback"
    assert "答辩状" in res.content


def test_generate_uses_template_when_provided():
    gen = _gen()
    req = GenerationRequest(
        doc_type="defense",
        case_context=_ctx(),
        reference_templates=[
            {"id": "t1", "name": "标准答辩状", "content": "# 答辩状\n被告:{{defendant}}"}
        ],
    )
    res = gen.generate(req)
    assert res.success is True
    # LLM 不可用时走纯模板路径
    assert res.source == "template"
    assert "乙公司" in res.content


def test_generate_fallback_metadata():
    gen = _gen()
    req = GenerationRequest(doc_type="evidence_index", case_context=_ctx())
    res = gen.generate(req)
    assert res.metadata["doc_type"] == "evidence_index"
    assert res.metadata["has_template"] is False


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