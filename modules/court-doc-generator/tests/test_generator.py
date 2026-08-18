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
    """F-034 + F-035: values_for_power_of_attorney 返回 7 个值，按文档【】出现顺序：
    1=被授权人姓名, 2=身份证号, 3=案由描述, 4=案号, 5/6/7=年/月/日
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
    assert len(values) == 7, "应返回 7 个值"
    assert values[0] == "张三", "被授权人姓名"
    assert values[1] == "110101199001011234", "代理人身份证号"
    assert values[2] == "对方公司合同纠纷", "案由描述"
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
    assert values[0] == "", "缺失姓名 → 空字符串"
    assert values[1] == "", "缺失身份证号 → 空字符串"
    assert values[2] == "", "缺失案由描述 → 空字符串"
    assert values[3] == "（2026）京01民初123号"


def test_power_of_attorney_template_has_seven_placeholders():
    """F-034: templates/4.授权委托书.docx 含 7 个【】占位符。"""
    from docx import Document
    from pathlib import Path

    template_path = Path(__file__).resolve().parent.parent / "templates" / "4.授权委托书.docx"
    doc = Document(str(template_path))
    total = sum(p.text.count("【】") for p in doc.paragraphs)
    assert total == 7, f"模板应有 7 个【】占位符，实际 {total} 个"


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


# ============================================================
# F-032 多代理人材料动态绑定：save_agent_pdf 上传保存
# ============================================================

def test_save_agent_pdf_creates_file_and_returns_relative_path(tmp_path):
    """F-032: save_agent_pdf 创建文件 + 返回相对 PROJECT_ROOT 的路径。

    验证：①文件落地 ②目录自动创建 ③返回路径相对 PROJECT_ROOT
    """
    from generator import save_agent_pdf
    from config import PROJECT_ROOT

    # 用临时 PROJECT_ROOT（monkeypatch 改 PROJECT_ROOT）
    # 简化做法：直接观察返回值是否相对 PROJECT_ROOT
    fake_pdf = b"%PDF-1.4 fake content"

    rel_path = save_agent_pdf(999, fake_pdf, "contract")
    # 路径应在 PROJECT_ROOT 下
    abs_path = PROJECT_ROOT / rel_path
    assert abs_path.exists(), f"文件应存在于 {abs_path}"
    assert abs_path.read_bytes() == fake_pdf, "文件内容应一致"
    assert rel_path.startswith("static/agents/999/"), "路径应在 agents/999/ 子目录"
    assert rel_path.endswith(".pdf"), "扩展名应为 pdf"

    # 清理
    abs_path.unlink()
    try:
        abs_path.parent.rmdir()  # agents/999/
    except OSError:
        pass
    try:
        (PROJECT_ROOT / "static" / "agents").rmdir()  # agents/
    except OSError:
        pass


def test_save_agent_pdf_invalid_file_type_raises():
    """F-032: file_type 非法 → ValueError。"""
    from generator import save_agent_pdf
    import pytest

    with pytest.raises(ValueError, match="file_type 必须是"):
        save_agent_pdf(1, b"data", "invalid_type")


def test_save_agent_pdf_unique_filename_per_call():
    """F-032: 每次调用生成 UUID 唯一文件名（不冲突）。"""
    from generator import save_agent_pdf
    from config import PROJECT_ROOT

    paths = set()
    for _ in range(3):
        p = save_agent_pdf(1, b"data", "contract")
        paths.add(p)

    assert len(paths) == 3, "3 次调用应生成 3 个不同路径"

    # 清理
    for p in list(paths):
        abs_p = PROJECT_ROOT / p
        if abs_p.exists():
            abs_p.unlink()


# ============================================================
# F-036 法定代表人证明改为固定静态文件
# ============================================================

def test_legal_rep_cert_static_file_exists():
    """F-036: static/2.法定代表人证明.pdf 应作为固定静态源文件存在。"""
    from pathlib import Path
    from config import STATIC_DIR

    src = STATIC_DIR / "2.法定代表人证明.pdf"
    assert src.exists(), f"固定模板文件必须存在：{src}"
    assert src.stat().st_size > 0, "固定模板文件不能为空"
    # 验证是有效 PDF（≥1 页）
    import pypdf
    r = pypdf.PdfReader(str(src))
    assert len(r.pages) >= 1, "PDF 应至少 1 页"


def test_legal_rep_cert_not_in_dynamic_templates():
    """F-036: values_for_legal_rep_cert 函数应已被移除（02 改为静态复制）。"""
    import generator as g
    assert not hasattr(g, "values_for_legal_rep_cert"), \
        "values_for_legal_rep_cert 应已被移除（02 改为静态复制）"