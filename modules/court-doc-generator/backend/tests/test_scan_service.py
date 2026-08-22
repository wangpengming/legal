"""scan_service OCR 字段抽取测试（拍照扫描 → 新建案件集成场景）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from scan_service import extract_fields


def test_extract_fields_full_document():
    """宋体起诉状扫描场景：全字段抽取。"""
    text = (
        "民事起诉状\n"
        "原告: 北京XX科技有限公司\n"
        "被告: 上海YY贸易有限公司\n\n"
        "案号: (2026) 京0105民初8888号\n\n"
        "本案系买卖合同纠纷。\n\n"
        "此致\n"
        "北京市朝阳区人民法院\n\n"
        "开庭时间: 2026年9月15日\n"
    )
    f = extract_fields(text)
    assert f["案号"] == "（2026）京0105民初8888号"
    assert f["法院"] == "北京市朝阳区人民法院"
    assert f["案由"] == "买卖合同纠纷"  # 前缀「本案系」应被清洗
    assert f["原告"] == "北京XX科技有限公司"
    assert f["被告"] == "上海YY贸易有限公司"
    assert f["开庭时间"] == "2026-9-15"


def test_extract_fields_halfwidth_colon():
    """OCR 常把全角冒号识别为半角，须兼容。"""
    f = extract_fields("原告: 北京XX科技有限公司\n被告: 上海YY贸易有限公司\n")
    assert f["原告"] == "北京XX科技有限公司"
    assert f["被告"] == "上海YY贸易有限公司"


def test_extract_fields_cause_common_prefix():
    """案由常见前缀（本案/本案系/系/属/因/为）需清洗，避免污染表单案由。"""
    for prefix in ["本案", "本案系", "系", "属", "因", "为"]:
        f = extract_fields(f"双方签订合同，{prefix}合同纠纷，诉至法院。")
        assert f["案由"] == "合同纠纷", f"prefix={prefix} -> {f['案由']}"


def test_extract_fields_names_span_noise():
    """当事人名称内部 OCR 空格噪音由前端清洗，字段提取本身不作拼接裁剪。"""
    f = extract_fields("被告: 上海YY 贸易有限公司\n原告: 北京XX科技有限公司\n")
    assert f["被告"] == "上海YY 贸易有限公司" or "上海YY" in f["被告"]


# ---- 真实起诉状照片场景（2026-08-22 腾讯音乐诉北京雷石著作权案，双图实测） ----


def test_extract_fields_court_fuzzy_chars():
    """法院「人民法院」形近字误读（法→活、院→区）应模糊还原。

    真实照片 OCR 输出「北京市朝阳区人民活区」，须还原为北京市朝阳区人民法院。
    """
    f = extract_fields("此致\n北京市朝阳区人民活区")
    assert f["法院"] == "北京市朝阳区人民法院"


def test_extract_fields_cause_label_row():
    """起诉状打印件「案由: XX纠纷」标签行直接命中，不再依赖正文关键词。"""
    f = extract_fields("案由: 侵害作品信息网络传播权纠纷")
    assert f["案由"] == "侵害作品信息网络传播权纠纷"


def test_extract_fields_cause_keyword_fallback():
    """无「案由」标签行时，正文命中复合词表（信息网络传播权）→ 标准案由。"""
    f = extract_fields("原告主张被告侵害其作品信息网络传播权并索赔。")
    assert f["案由"] == "侵害作品信息网络传播权纠纷"


def test_extract_fields_party_real_ocr_noise():
    """真实 OCR 段落：被告行带「住所地」噪声、原告行后混入正文句子，须截断到位。"""
    f = extract_fields(
        "被告，北京雷石天地电子技术股份有限公司住所地: ORR科技园\n"
        "原告: 腾讯音乐娱乐(珠海) 有限公司经合法转授权获得了杰威尔曲库版权"
    )
    assert f["被告"] == "北京雷石天地电子技术股份有限公司"
    assert f["原告"] == "腾讯音乐娱乐(珠海) 有限公司"


def test_extract_fields_multi_page_merge():
    """多图/多页合并文本：字段分散在不同页，须从拼接文本整合抽取。"""
    text = (
        "=== 图片 1 ===\n"
        "原告: 腾讯音乐娱乐(珠海) 有限公司\n"
        "被告: 北京雷石天地电子技术股份有限公司\n"
        "案由: 侵害作品信息网络传播权纠纷\n"
        "诉讼请求: 判令被告支付赔偿金 2260000元\n"
        "\n"
        "=== 图片 2 ===\n"
        "此致\n北京市朝阳区人民活区"
    )
    f = extract_fields(text)
    assert f["法院"] == "北京市朝阳区人民法院"
    assert f["案由"] == "侵害作品信息网络传播权纠纷"
    assert f["原告"] == "腾讯音乐娱乐(珠海) 有限公司"
    assert f["被告"] == "北京雷石天地电子技术股份有限公司"
    assert f["标的金额"] == "2260000"