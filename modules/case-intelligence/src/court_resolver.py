# =============================================
# court_resolver.py - 从案号派生法院（纯函数，无 IO）
# 案号代字 → 法院名。仅映射"已核验"条目；未知一律返回 ""（留空，由审计报告收集补齐）。
# 案号形如：(2024)京0491民初1152号 / (2022)晋民终508号 / (2024)京73民终2207号
# =============================================
import re
from typing import Optional, Tuple

# 案号 = (年份) + 省级简称(单字) + [编号(1-4位数字)] + 案件类型
_CASE_NO_RE = re.compile(r"[（(]\s*(\d{4})\s*[)）]\s*([\u4e00-\u9fa5])")

# 省级简称（单字）全集（含常见异写：黔/贵、内/蒙、蜀/川）
_PROVINCE_MAP = {
    "京": "北京市", "沪": "上海市", "津": "天津市", "渝": "重庆市",
    "冀": "河北省", "晋": "山西省", "蒙": "内蒙古自治区", "内": "内蒙古自治区",
    "辽": "辽宁省", "吉": "吉林省", "黑": "黑龙江省",
    "苏": "江苏省", "浙": "浙江省", "皖": "安徽省", "闽": "福建省", "赣": "江西省",
    "鲁": "山东省", "豫": "河南省", "鄂": "湖北省", "湘": "湖南省",
    "粤": "广东省", "桂": "广西壮族自治区", "琼": "海南省",
    "川": "四川省", "蜀": "四川省", "黔": "贵州省", "贵": "贵州省",
    "云": "云南省", "滇": "云南省", "藏": "西藏自治区",
    "陕": "陕西省", "秦": "陕西省", "甘": "甘肃省", "陇": "甘肃省",
    "青": "青海省", "宁": "宁夏回族自治区", "新": "新疆维吾尔自治区",
}

# 已核验：省字+编号 → 法院（仅收录可确证者，避免臆断）
_COURT_CODE_MAP = {
    "京0491": "北京互联网法院",
    "京0105": "北京市朝阳区人民法院",
    "京73": "北京知识产权法院",
    "沪0115": "上海市浦东新区人民法院",
}


def extract_court_token(case_number: Optional[str]) -> str:
    """取案号法院代字（省字+编号 / 省字 / 省字+仲）；无法识别返回 ""。

    "（2024）京0104民初14030号" → "京0104"
    "（2022）晋民终508号"       → "晋"
    "(2024)京73民终2207号"      → "京73"
    "（2023）京仲100号"         → "京仲"
    """
    if not case_number:
        return ""
    m = _CASE_NO_RE.search(case_number)
    if not m:
        return ""
    prov = m.group(2)
    if prov not in _PROVINCE_MAP:
        return ""
    tail = case_number[m.end():]
    digits = re.match(r"(\d{1,4})", tail)
    if digits:
        return prov + digits.group(1)
    if tail.startswith("仲"):
        return prov + "仲"
    return prov


def resolve_court(case_number: Optional[str]) -> str:
    """从案号解析法院名；无法确证时返回 ""（不臆断）。"""
    token = extract_court_token(case_number)
    if not token:
        return ""
    if token.endswith("仲"):          # 仲裁机构，非法院
        return ""
    if token in _COURT_CODE_MAP:
        return _COURT_CODE_MAP[token]
    prov, rest = token[0], token[1:]
    if rest:                          # 有编号但未收录 → 未知（交由审计收集补表）
        return ""
    # 无编号 = 省级高级人民法院（如 晋民终 → 山西省高级人民法院）
    return f"{_PROVINCE_MAP[prov]}高级人民法院"


def resolve(case_number: Optional[str]) -> Tuple[str, str]:
    """返回 (法院名, 代字)。法院名可能为 ""（未知）。"""
    return resolve_court(case_number), extract_court_token(case_number)


def year_from_case_number(case_number: Optional[str]) -> Optional[int]:
    """取案号受理年份；无则 None。"""
    if not case_number:
        return None
    m = _CASE_NO_RE.search(case_number)
    return int(m.group(1)) if m else None