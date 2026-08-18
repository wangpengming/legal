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


# ============================================================
# F-035 多代理人材料动态绑定：values_for_power_of_attorney 补充 agent 字段
# ============================================================

def test_values_for_power_of_attorney_includes_agent():
    """F-035: values_for_power_of_attorney 返回 7 个元素，包含 agent 姓名 + 身份证号。

    占位符 1=案由描述, 2=被授权人姓名, 3=身份证号, 4=案号, 5/6/7=年/月/日
    """
    from generator import values_for_power_of_attorney

    case = {
        "case_number": "（2026）京01民初123号",
        "case_cause": "合同纠纷",
        "court": "北京一中院",
        "hearing_date": "2026-09-15",
        "opposing_party": "对方公司",
        "our_role": "原告",
    }
    company = {"name": "测试公司"}
    agent = {
        "name": "张三",
        "id_card": "110101199001011234",
        "gender": "男",
    }
    values = values_for_power_of_attorney(case, company, agent)
    assert len(values) == 7, "应返回 7 个值（5→7 增加 2 个 agent 字段）"
    assert values[0] == "对方公司合同纠纷", "案由描述"
    assert values[1] == "张三", "被授权人姓名"
    assert values[2] == "110101199001011234", "代理人身份证号"
    assert values[3] == "（2026）京01民初123号", "案号"
    assert values[4] == "2026", "年"
    assert values[5] == "9", "月"
    assert values[6] == "15", "日"


def test_values_for_power_of_attorney_handles_missing_agent_fields():
    """F-035: agent 字段缺失时不能崩，应用空字符串代替。"""
    from generator import values_for_power_of_attorney

    case = {"case_number": "（2026）京01民初123号", "hearing_date": "2026-09-15"}
    company = {}
    agent = {}  # 完全没有字段
    values = values_for_power_of_attorney(case, company, agent)
    assert values[1] == "", "缺失姓名 → 空字符串"
    assert values[2] == "", "缺失身份证号 → 空字符串"
    assert values[3] == "（2026）京01民初123号"


# ============================================================
# F-033 多代理人材料动态绑定：_resolve_agent_pdf 路径解析
# ============================================================

def test_resolve_agent_pdf_uses_custom_relative_path(tmp_path, monkeypatch):
    """F-033: agent.contract_pdf_path 存在且路径有效 → 使用该文件。

    用法：路径相对 PROJECT_ROOT（数据库存相对路径，便于整包分发）。
    """
    from generator import _resolve_agent_pdf
    from config import PROJECT_ROOT

    # 在 PROJECT_ROOT 下创建临时 PDF（确保 relative_to 能解析）
    custom_pdf = PROJECT_ROOT / "static" / "agents" / "_test_contract.pdf"
    custom_pdf.parent.mkdir(parents=True, exist_ok=True)
    custom_pdf.write_bytes(b"%PDF-1.4 fake")

    try:
        # agent 用相对路径（相对 PROJECT_ROOT）
        rel_path = "static/agents/_test_contract.pdf"
        agent = {"contract_pdf_path": rel_path}
        result = _resolve_agent_pdf(agent, "06_代理人劳动合同.pdf", "代理人劳动合同.pdf")
        assert result is not None
        assert result.exists()
        assert result.name == "_test_contract.pdf"
    finally:
        # 清理测试文件
        if custom_pdf.exists():
            custom_pdf.unlink()
        # 清理空目录
        try:
            custom_pdf.parent.rmdir()
        except OSError:
            pass


def test_resolve_agent_pdf_uses_absolute_path(tmp_path):
    """F-033: 绝对路径有效 → 使用该文件。"""
    from generator import _resolve_agent_pdf

    custom_pdf = tmp_path / "id_card_lisi.pdf"
    custom_pdf.write_bytes(b"%PDF-1.4 fake")
    agent = {"id_card_pdf_path": str(custom_pdf)}

    result = _resolve_agent_pdf(agent, "07_代理人身份证.pdf", "代理人身份证.pdf")
    assert result is not None
    assert result == custom_pdf


def test_resolve_agent_pdf_fallback_when_empty(tmp_path):
    """F-033: agent 字段为空 → fallback 到默认 STATIC_DIR 文件。"""
    from generator import _resolve_agent_pdf
    from config import STATIC_DIR

    agent = {}  # 字段缺失
    fallback_name = "代理人劳动合同.pdf"
    fallback_path = STATIC_DIR / fallback_name

    if fallback_path.exists():
        result = _resolve_agent_pdf(agent, "06_代理人劳动合同.pdf", fallback_name)
        assert result is not None
        assert result.name == fallback_name
    else:
        # 如果默认 fallback 不存在（如测试环境），应返回 None
        result = _resolve_agent_pdf(agent, "06_代理人劳动合同.pdf", fallback_name)
        assert result is None


def test_resolve_agent_pdf_returns_none_when_path_missing(tmp_path):
    """F-033: agent 路径无效且 fallback 不存在 → 返回 None（不崩）。"""
    from generator import _resolve_agent_pdf

    agent = {"contract_pdf_path": "this/path/does/not/exist.pdf"}
    result = _resolve_agent_pdf(
        agent, "06_代理人劳动合同.pdf", "non_existent_fallback.pdf"
    )
    assert result is None, "路径失效且 fallback 缺失 → 返回 None（调用方应跳过）"