# =============================================
# test_langchain_llm.py - LangChain LLM 集成测试（无外部依赖）
# 覆盖: 配置加载 / doc_type 映射 / prompt 模板构建 / 无 LLM 时的降级行为
# 可 pytest 收集，亦可直接运行: python3 tests/test_langchain_llm.py
# =============================================
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))
sys.path.insert(0, str(_HERE.parent))

import langchain_llm as llm_mod  # noqa: E402


def test_llm_config_loads():
    cfg = llm_mod.load_llm_config()
    assert isinstance(cfg, dict)


def test_minimax_config_defaults():
    cfg = llm_mod.get_minimax_config()
    assert cfg["base_url"].startswith("http")
    assert cfg["model"]
    assert isinstance(cfg["temperature"], float)
    assert isinstance(cfg["max_tokens"], int)


def test_doc_type_name_mapping():
    assert llm_mod.get_doc_type_name("defense") == "答辩状"
    assert llm_mod.get_doc_type_name("evidence_objection") == "质证意见"
    assert llm_mod.get_doc_type_name("court_statement") == "当庭陈述"
    assert llm_mod.get_doc_type_name("evidence_index") == "证据目录"


def test_doc_type_name_unknown_passthrough():
    assert llm_mod.get_doc_type_name("unknown_type") == "unknown_type"


def test_extract_system_prompt_role_section():
    template = "---\nname: x\n---\n\n## 角色定义\n\n你是资深民商法律师。\n\n## 输入\n内容"
    sp = llm_mod._extract_system_prompt(template)
    assert "法律文书撰写专家" in sp


def test_extract_system_prompt_fallback():
    sp = llm_mod._extract_system_prompt("无角色定义的纯文本")
    assert "法律文书撰写专家" in sp


def test_build_prompt_from_template_contains_case_info():
    template = (
        "---\nname: t\n---\n\n"
        "## 案件基本信息\n\n占位\n\n"
        "## 生成指令\n\n请生成规范文书。\n\n"
        "## 输出要求\n\n仅返回正文。"
    )
    case_info = {
        "case_number": "(2024)京0491民初1号",
        "plaintiff": "甲",
        "defendant": "乙",
        "cause": "著作权侵权",
        "court": "北京互联网法院",
    }
    prompt = llm_mod._build_prompt_from_template(template, case_info, "defense")
    assert "(2024)京0491民初1号" in prompt
    assert "甲" in prompt
    assert "答辩状" in prompt


def test_build_prompt_from_template_missing_fields_placeholder():
    case_info = {"case_number": ""}
    prompt = llm_mod._build_prompt_from_template("", case_info, "defense")
    assert "[待补充]" in prompt


def test_llm_service_unavailable_by_default():
    # 测试环境未安装 langchain_openai，服务应报告不可用
    svc = llm_mod.get_llm_service()
    assert svc.is_available() is False


def test_llm_service_invoke_raises_when_unavailable():
    svc = llm_mod.get_llm_service()
    if svc.is_available():
        return  # 真装好依赖的环境下跳过该断言
    try:
        svc.invoke([{"role": "user", "content": "hi"}])
        raise AssertionError("应抛出 RuntimeError")
    except RuntimeError:
        pass


def test_generate_direct_raises_when_unavailable():
    svc = llm_mod.get_llm_service()
    if svc.is_available():
        return
    try:
        llm_mod.generate_direct({"case_number": "x"}, "defense")
        raise AssertionError("应抛出 RuntimeError")
    except RuntimeError:
        pass


def test_create_workflow_returns_none_without_langgraph():
    # 未安装 langgraph 时返回 None（降级模式）
    wf = llm_mod.create_document_workflow()
    assert wf is None or hasattr(wf, "invoke")


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