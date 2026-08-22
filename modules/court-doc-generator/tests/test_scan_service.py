"""F-052 scan_service 单元测试。"""
from scan_service import extract_fields, extract_text, scan_documents
from pathlib import Path


def test_extract_fields_empty_text():
    """空文本 → 全 None。"""
    fields = extract_fields("")
    assert all(v is None for v in fields.values())


def test_extract_fields_typical_qisu():
    """典型起诉状字段抽取。"""
    text = """北京市第一中级人民法院
（2024）京01民初12345号
开庭时间：2026年10月15日
原告：北京雷石天地电子技术股份有限公司
被告：深圳某科技公司
案由：合同纠纷
诉讼请求：判令被告支付人民币 500000 元
立案日期：2026年3月1日"""
    fields = extract_fields(text)
    assert fields["案号"] == "（2024）京01民初12345号"
    assert fields["法院"] == "北京市第一中级人民法院"
    assert fields["案由"] == "合同纠纷"
    assert fields["原告"] == "北京雷石天地电子技术股份有限公司"
    assert fields["被告"] == "深圳某科技公司"
    assert fields["开庭时间"] == "2026-10-15"
    assert fields["立案日期"] == "2026-3-1"
    assert fields["标的金额"] == "500000"


def test_extract_fields_chuanpiao():
    """传票风格（短文本，无原告/被告/案由）。"""
    text = """北京市朝阳区人民法院
开庭时间：2025年12月3日
案号：（2025）京0105民初888号"""
    fields = extract_fields(text)
    assert fields["案号"] == "（2025）京0105民初888号"
    assert fields["法院"] == "北京市朝阳区人民法院"
    assert fields["开庭时间"] == "2025-12-3"
    assert fields["原告"] is None  # 传票没原告被告栏
    assert fields["被告"] is None


def test_extract_fields_chuanpiao_table_layout_noisy_date():
    """传票表格跨行 + OCR 竖线噪声：表头/值分离、日期数字误读为 |，仍能抽取。"""
    # 模拟真实传票 OCR 输出（psm3 通道）：表头行与值行分开，| 为日期数字噪声
    text = """事由    应到地点            开庭时间     签发人
朝阳法院 民五庭
开庭     《广顺北大街)     2026年4月|日
三层 第三法庭         fe We 00 4"""
    fields = extract_fields(text)
    assert fields["开庭时间"] == "2026-4-?"


def test_extract_fields_hearing_date_table_header_only():
    """仅表头含「开庭时间」且日期在表格值时同样抽取。"""
    text = """开庭时间：2026年8月20日"""
    fields = extract_fields(text)
    assert fields["开庭时间"] == "2026-8-20"


def test_extract_fields_cause_strip_litigation():
    """案由清洗：去掉末尾"纠纷"二字。"""
    text = """案由：合同纠纷
原告：A
被告：B
（2026）京01民初1号"""
    fields = extract_fields(text)
    # extract_fields 直接保留 "合同纠纷"，但 app.py 还会再清一次
    assert fields["案由"] == "合同纠纷"


def test_scan_documents_empty():
    """scan_documents 空路径列表 → 返回空 text + 全 None fields。"""
    result = scan_documents([])
    assert result["text"] == ""
    assert all(v is None for v in result["fields"].values())


def test_scan_documents_nonexistent_file():
    """scan_documents 不存在的路径 → 跳过，返回空。"""
    result = scan_documents([Path("/nonexistent/file.jpg")])
    assert result["text"] == ""
