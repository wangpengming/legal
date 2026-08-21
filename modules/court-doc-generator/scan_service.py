"""F-052 拍照扫描服务：OCR + 字段抽取。

技术栈：
- OCR: Tesseract 5.5.2（macOS Homebrew）+ chi_sim（中文）
- 字段抽取: 正则 + 关键词匹配（零 LLM 依赖，覆盖率高）

设计：
- extract_text(image_paths) -> str：多张图 → OCR → 拼接
- extract_fields(text) -> dict：正则抽取关键字段
- scan_documents(image_paths) -> dict：一站式扫描+抽取
- download_and_scan_url(url) -> dict：URL → 下载 → OCR（绕过 file_uploader 限制）
"""
import re
import shutil
import subprocess
import tempfile
import urllib.request
import ssl
from pathlib import Path
from typing import List, Dict, Optional


# Tesseract 命令路径
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"

# 自动检测中文语言包是否可用（tessdata 目录）
def _detect_lang() -> str:
    tessdata_dir = Path(shutil.which(_TESSERACT)).parent.parent / "share" / "tessdata"
    if not tessdata_dir.exists():
        return "eng"
    available = {p.stem for p in tessdata_dir.glob("*.traineddata")}
    if "chi_sim" in available:
        return "chi_sim+eng"
    return "eng"

_LANG = _detect_lang()


def extract_text(image_paths: List[Path], lang: str | None = None) -> str:
    """多张图 OCR 提取文字（拼接返回）。

    参数：
        image_paths: 图片路径列表（jpg/png/pdf 等）
        lang: Tesseract 语言（默认自动检测：chi_sim+eng 或 eng）

    返回：
        拼接后的纯文本（多张图用换行分隔）
    """
    if not image_paths:
        return ""
    lang = lang or _LANG

    all_text = []
    for i, img_path in enumerate(image_paths):
        if not Path(img_path).exists():
            continue
        try:
            # errors="ignore" 防止 tesseract 在 stderr 输出非 UTF-8 字节导致 UnicodeDecodeError
            result = subprocess.run(
                [_TESSERACT, str(img_path), "-", "-l", lang],
                capture_output=True, text=True, errors="ignore", timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text:
                    all_text.append(f"=== 图片 {i+1} ===\n{text}")
            elif "chi_sim" in lang and "Failed loading language" in (result.stderr or ""):
                # 语言包缺失，回退到英文
                result2 = subprocess.run(
                    [_TESSERACT, str(img_path), "-", "-l", "eng"],
                    capture_output=True, text=True, errors="ignore", timeout=30,
                )
                if result2.returncode == 0 and result2.stdout.strip():
                    all_text.append(f"=== 图片 {i+1} ===\n{result2.stdout.strip()}")
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


def download_and_scan_url(url: str, timeout: int = 30) -> Dict:
    """从 URL 下载图片并进行 OCR 扫描。

    用途：绕过 Streamlit file_uploader 的程序化上传限制，
          用户可以直接粘贴图片 URL 进行扫描。

    支持格式：jpg, jpeg, png, pdf, bmp, tiff, gif, webp

    参数：
        url: 图片 URL（支持 http/https）
        timeout: 下载超时（秒）

    返回：
        {
            "text": str,  # OCR 原始文本
            "fields": dict,  # 抽取的字段
            "filename": str,  # 下载的文件名
            "error": str | None,  # 错误信息（成功时为 None）
        }
    """
    if not url or not url.strip():
        return {"text": "", "fields": {}, "filename": "", "error": "URL 为空"}

    url = url.strip()

    # 验证 URL 格式
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"text": "", "fields": {}, "filename": "", "error": "仅支持 http/https URL"}

    try:
        # 从 URL 提取文件名
        parsed = urllib.parse.urlparse(url)
        path_part = parsed.path.split("/")[-1]
        if path_part and "." in path_part:
            filename = path_part
        else:
            # 根据 Content-Type 猜测扩展名
            filename = "downloaded_image.jpg"

        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix="_" + filename) as tmp:
            tmp_path = Path(tmp.name)

        # 下载文件
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        # 创建 SSL 上下文（macOS Python 需要）
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            content = response.read()
            tmp_path.write_bytes(content)

        # 检查文件是否有效（不为空）
        if len(content) < 100:
            tmp_path.unlink(missing_ok=True)
            return {"text": "", "fields": {}, "filename": filename, "error": "下载的文件过小或为空"}

        # 调用现有 scan_documents 处理
        result = scan_documents([tmp_path])

        # 清理临时文件
        tmp_path.unlink(missing_ok=True)

        return {
            "text": result["text"],
            "fields": result["fields"],
            "filename": filename,
            "error": None,
        }

    except urllib.error.URLError as e:
        return {"text": "", "fields": {}, "filename": filename if "filename" in dir() else "", "error": f"网络错误：{e.reason}"}
    except Exception as e:
        return {"text": "", "fields": {}, "filename": "", "error": f"下载失败：{str(e)}"}
