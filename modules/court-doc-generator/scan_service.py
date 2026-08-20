"""F-052 拍照扫描服务：OCR + 字段抽取。

技术栈：
- OCR: Tesseract 5.5.2（macOS Homebrew）+ chi_sim（中文）
- 字段抽取: 正则 + 关键词匹配（零 LLM 依赖，覆盖率高）

设计：
- extract_text(image_paths) -> str：多张图 → OCR → 拼接
- extract_fields(text) -> dict：正则抽取关键字段
- scan_documents(image_paths) -> dict：一站式扫描+抽取
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional


# Tesseract 命令路径
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"


def extract_text(image_paths: List[Path], lang: str = "chi_sim+eng") -> str:
    """多张图 OCR 提取文字（拼接返回）。

    参数：
        image_paths: 图片路径列表（jpg/png/pdf 等）
        lang: Tesseract 语言（默认中文+英文）

    返回：
        拼接后的纯文本（多张图用换行分隔）
    """
    if not image_paths:
        return ""

    all_text = []
    for i, img_path in enumerate(image_paths):
        if not Path(img_path).exists():
            continue
        try:
            result = subprocess.run(
                [_TESSERACT, str(img_path), "-", "-l", lang],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text:
                    all_text.append(f"=== 图片 {i+1} ===\n{text}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            all_text.append(f"=== 图片 {i+1} 错误：{e} ===")

    return "\n\n".join(all_text)


def extract_fields(text: str) -> Dict[str, Optional[str]]:
    """从法律文书 OCR 文本抽取关键字段。

    抽取字段：
    - 案号: （2024）京01民初123号
    - 法院: XX人民法院
    - 案由: XX纠纷（如合同纠纷/侵权纠纷等）
    - 原告: 当事人名称
    - 被告: 当事人名称
    - 开庭时间: 2026年X月X日 / 2026-X-X
    - 立案日期: 同上格式
    - 标的金额: 数字（元）

    返回：
        dict: {字段名: 值}，未找到的字段为 None
    """
    if not text:
        return {}

    result = {
        "案号": None,
        "法院": None,
        "案由": None,
        "原告": None,
        "被告": None,
        "开庭时间": None,
        "立案日期": None,
        "标的金额": None,
    }

    # 案号：（2024）京01民初123号 之类
    case_no_match = re.search(
        r'[（(]\s*(\d{4})\s*[）)]\s*([\u4e00-\u9fa5\d]+民初\d+号)',
        text
    )
    if case_no_match:
        result["案号"] = f"（{case_no_match.group(1)}）{case_no_match.group(2)}"

    # 法院：XX人民法院（前面有"北京市"等修饰）
    court_match = re.search(
        r'([\u4e00-\u9fa5]{2,8}人民法院)',
        text
    )
    if court_match:
        result["法院"] = court_match.group(1)

    # 案由：XX纠纷
    cause_match = re.search(
        r'([\u4e00-\u9fa5]{2,8}纠纷)',
        text
    )
    if cause_match:
        result["案由"] = cause_match.group(1)

    # 原告：原告：XX / 原告 XX
    plaintiff_match = re.search(
        r'原告[:：]?\s*([\u4e00-\u9fa5（）()\u4e00-\u9fa5A-Za-z0-9·\u3000\s]{2,40})(?:\n|，|,|。|被告)',
        text
    )
    if plaintiff_match:
        result["原告"] = plaintiff_match.group(1).strip()

    # 被告：被告：XX
    defendant_match = re.search(
        r'被告[:：]?\s*([\u4e00-\u9fa5（）()\u4e00-\u9fa5A-Za-z0-9·\u3000\s]{2,40})(?:\n|，|,|。)',
        text
    )
    if defendant_match:
        result["被告"] = defendant_match.group(1).strip()

    # 开庭时间：2026年X月X日 X:X / 2026-X-X
    hearing_date_match = re.search(
        r'开庭时间[:：]?\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?(?:日)?)',
        text
    )
    if not hearing_date_match:
        # 备用：匹配"开庭"前后的日期
        hearing_date_match = re.search(
            r'(?:开庭|审理).{0,5}(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)',
            text
        )
    if hearing_date_match:
        result["开庭时间"] = hearing_date_match.group(1).replace("年", "-").replace("月", "-").replace("日", "").strip("-")

    # 立案日期
    filing_match = re.search(
        r'(?:立案|受理).{0,5}(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)',
        text
    )
    if filing_match:
        result["立案日期"] = filing_match.group(1).replace("年", "-").replace("月", "-").replace("日", "").strip("-")

    # 标的金额：人民币XX元 / XX元
    amount_match = re.search(
        r'(?:人民币)?\s*([\d,，\.]+)\s*元',
        text
    )
    if amount_match:
        result["标的金额"] = amount_match.group(1).replace(",", "").replace("，", "")

    return result


def scan_documents(image_paths: List[Path]) -> Dict:
    """一站式扫描：OCR + 字段抽取。

    参数：
        image_paths: 图片路径列表

    返回：
        {
            "text": str,  # OCR 原始文本
            "fields": dict,  # 抽取的字段
        }
    """
    text = extract_text(image_paths)
    fields = extract_fields(text)
    return {"text": text, "fields": fields}
