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
    """空字符串应返回'未命名'。"""
    assert sanitize_filename("") == "未命名"


def test_only_unsafe():
    """全是不安全字符时返回'未命名'。"""
    assert sanitize_filename("///") == "未命名"


# ============================================================
# F-035 多代理人材料动态绑定：values_for_power_of_attorney 补充 agent 字段
# ============================================================

def test_values_for_power_of_attorney_includes_agent():
    """F-038: values_for_power_of_attorney 返回 9 个值，按真实模板【】出现顺序：

    1=受委托人姓名, 2=职务, 3=电话, 4=对方当事人, 5=案由, 6=案号, 7/8/9=年/月/日
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
        "gender": "男",
        "id_card": "110101199001011234",
        "position": "法务经理",
        "phone": "13800138000",
    }
    values = values_for_power_of_attorney(case, company, agent)
    assert len(values) == 9, "应返回 9 个值"
    assert values[0] == "张三", "受委托人姓名"
    assert values[1] == "法务经理", "职务"
    assert values[2] == "13800138000", "电话"
    assert values[3] == "对方公司", "对方当事人"
    assert values[4] == "合同纠纷", "案由"
    assert values[5] == "（2026）京01民初123号", "案号"
    assert values[6] == "2026", "年"
    assert values[7] == "9", "月"
    assert values[8] == "15", "日"


def test_values_for_power_of_attorney_handles_missing_agent_fields():
    """F-038: agent 字段缺失时不能崩，应用空字符串代替。"""
    from generator import values_for_power_of_attorney

    case = {"case_number": "（2026）京01民初123号", "hearing_date": "2026-09-15"}
    company = {}
    agent = {}  # 完全没有字段
    values = values_for_power_of_attorney(case, company, agent)
    assert values[0] == "", "缺失姓名 → 空字符串"
    assert values[1] == "", "缺失职务 → 空字符串"
    assert values[2] == "", "缺失电话 → 空字符串"
    assert values[3] == "", "缺失对方 → 空字符串"
    assert values[4] == "", "缺失案由 → 空字符串"
    assert values[5] == "（2026）京01民初123号"


def test_values_for_recommendation_includes_agent_and_case():
    """F-038: values_for_recommendation 返回 11 个值，按真实模板【】出现顺序：

    1=法院, 2=员工姓名, 3=性别, 4=身份证号, 5=职务, 6=对方, 7=案由, 8=案号, 9/10/11=年/月/日
    """
    from generator import values_for_recommendation

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
        "name": "李四",
        "gender": "女",
        "id_card": "110101199203054321",
        "position": "法务专员",
        "phone": "13900139000",
    }
    values = values_for_recommendation(case, company, agent)
    assert len(values) == 12, "应返回 12 个值（F-051 加 phone）"
    assert values[0] == "北京一中院", "法院"
    assert values[1] == "李四", "员工姓名"
    assert values[2] == "女", "性别"
    assert values[3] == "110101199203054321", "身份证号"
    assert values[4] == "法务专员", "职务"
    assert values[5] == "13900139000", "电话（F-051 新增）"
    assert values[6] == "对方公司", "对方当事人"
    assert values[7] == "合同纠纷", "案由"
    assert values[8] == "（2026）京01民初123号", "案号"
    assert values[9] == "2026", "年"
    assert values[10] == "9", "月"
    assert values[11] == "15", "日"


def test_power_of_attorney_template_has_nine_placeholders():
    """F-038: templates/4.授权委托书.docx 含 9 个【】占位符。"""
    from docx import Document
    from pathlib import Path

    template_path = Path(__file__).resolve().parent.parent / "templates" / "4.授权委托书.docx"
    doc = Document(str(template_path))
    total = sum(p.text.count("【】") for p in doc.paragraphs)
    assert total == 9, f"模板应有 9 个【】占位符，实际 {total} 个"


def test_recommendation_template_has_twelve_placeholders():
    """F-051: templates/5.推荐信.docx 含 12 个【】占位符（加 agent.phone）。"""
    from docx import Document
    from pathlib import Path

    template_path = Path(__file__).resolve().parent.parent / "templates" / "5.推荐信.docx"
    doc = Document(str(template_path))
    total = sum(p.text.count("【】") for p in doc.paragraphs)
    assert total == 12, f"模板应有 12 个【】占位符，实际 {total} 个"


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
# F-041 validate_agent_paths 路径校验
# ============================================================

def test_validate_agent_paths_all_valid(tmp_path):
    """F-041: 所有路径都存在 → 返回空字典。"""
    from generator import validate_agent_paths

    # 创建两个有效文件
    valid_file = tmp_path / "test.pdf"
    valid_file.write_bytes(b"%PDF fake")

    # 但 validate_agent_paths 用 PROJECT_ROOT 作根，不是 tmp_path
    # 所以用真实路径结构
    from config import PROJECT_ROOT
    agent_dir = PROJECT_ROOT / "static" / "agents" / "_test_vap"
    agent_dir.mkdir(parents=True, exist_ok=True)
    pdf1 = agent_dir / "valid.pdf"
    pdf1.write_bytes(b"%PDF fake")

    agents = [{
        "id": 99,
        "name": "测试",
        "contract_pdf_path": "static/agents/_test_vap/valid.pdf",
        "id_card_pdf_path": None,
    }]
    result = validate_agent_paths(agents)
    assert result == {}, f"全部有效应返回空字典，实际：{result}"

    # 清理
    pdf1.unlink()
    agent_dir.rmdir()


def test_validate_agent_paths_detects_missing(tmp_path):
    """F-041: 路径不存在 → 在结果中标记 invalid。"""
    from generator import validate_agent_paths

    agents = [{
        "id": 100,
        "name": "测试",
        "contract_pdf_path": "static/agents/100/contract_missing.pdf",
        "id_card_pdf_path": "static/agents/100/id_card_also_missing.pdf",
    }]
    result = validate_agent_paths(agents)

    assert 100 in result
    assert result[100]["agent_name"] == "测试"
    assert "contract_pdf_path" in result[100]["invalid"]
    assert "id_card_pdf_path" in result[100]["invalid"]
    assert result[100]["valid"] == []


def test_validate_agent_paths_mixed(tmp_path):
    """F-041: 一有效一失效 → 只记录失效字段。"""
    from generator import validate_agent_paths
    from config import PROJECT_ROOT

    # 创建 1 个有效文件
    agent_dir = PROJECT_ROOT / "static" / "agents" / "_test_vap_mix"
    agent_dir.mkdir(parents=True, exist_ok=True)
    valid_pdf = agent_dir / "valid.pdf"
    valid_pdf.write_bytes(b"%PDF fake")

    agents = [{
        "id": 101,
        "name": "混合",
        "contract_pdf_path": "static/agents/_test_vap_mix/valid.pdf",  # 存在
        "id_card_pdf_path": "static/agents/_test_vap_mix/missing.pdf",   # 不存在
    }]
    result = validate_agent_paths(agents)

    assert 101 in result
    assert "contract_pdf_path" in result[101]["valid"]
    assert "id_card_pdf_path" in result[101]["invalid"]

    # 清理
    valid_pdf.unlink()
    agent_dir.rmdir()


def test_validate_agent_paths_empty_field_ok():
    """F-041: 空字段（未上传）不算失效。"""
    from generator import validate_agent_paths

    agents = [{
        "id": 102,
        "name": "新代理人",
        "contract_pdf_path": None,
        "id_card_pdf_path": "",
    }]
    result = validate_agent_paths(agents)
    assert result == {}, "空字段不算失效"


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


# ============================================================
# F-037 在线打印：print_pdf_to_default_printer
# ============================================================

def test_print_pdf_to_default_printer_file_not_exists(tmp_path):
    """F-037: PDF 不存在时返回 (False, 错误消息)。"""
    from generator import print_pdf_to_default_printer

    fake_pdf = tmp_path / "non_existent.pdf"
    success, msg = print_pdf_to_default_printer(fake_pdf)
    assert success is False
    assert "不存在" in msg


def test_print_pdf_to_default_printer_success_mac(monkeypatch, tmp_path):
    """F-037: macOS/Linux 调 lp 命令成功 → 返回 (True, stdout)。"""
    import platform
    if platform.system() not in ("Darwin", "Linux"):
        import pytest
        pytest.skip("本测试仅在 macOS / Linux 运行")

    from generator import print_pdf_to_default_printer
    import subprocess

    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    class FakeResult:
        returncode = 0
        stdout = "request id is HP-LaserJet-1 (1 file(s))"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())

    success, msg = print_pdf_to_default_printer(fake_pdf)
    assert success is True
    assert "HP-LaserJet-1" in msg


def test_print_pdf_to_default_printer_lp_failure(monkeypatch, tmp_path):
    """F-037: lp 命令失败 → 返回 (False, stderr)。"""
    from generator import print_pdf_to_default_printer
    import subprocess

    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "lp: The printer or class does not exist."

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())

    success, msg = print_pdf_to_default_printer(fake_pdf)
    assert success is False
    assert "lp 失败" in msg


def test_print_pdf_to_default_printer_timeout(monkeypatch, tmp_path):
    """F-037: subprocess 超时 → 返回 (False, 超时提示)。"""
    from generator import print_pdf_to_default_printer
    import subprocess

    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="lp", timeout=30)

    monkeypatch.setattr(subprocess, "run", fake_run)

    success, msg = print_pdf_to_default_printer(fake_pdf)
    assert success is False
    assert "超时" in msg


def test_print_pdf_to_default_printer_unsupported_os(monkeypatch, tmp_path):
    """F-037: 不支持的系统（如 FreeBSD）→ 返回 (False, 错误消息)。"""
    from generator import print_pdf_to_default_printer
    import platform

    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(platform, "system", lambda: "FreeBSD")

    success, msg = print_pdf_to_default_printer(fake_pdf)
    assert success is False
    assert "不支持的系统" in msg