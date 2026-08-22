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


# 双通道 PSM 模式：3=自动分页、6=统一文本块。
# 真实起诉状照片实测两通道互补：psm6 对印刷标签行（案由/被告抬头）更准，
# psm3 对正文中当事人全名更准，故每张图双通道各跑一次并拼接，提升信息召回。
_PSM_MODES = (3, 6)


def _ocr_one(image_path: Path, lang: str, psm: int) -> str:
    """单次 tesseract OCR（指定 PSM 模式）。

    返回识别文本；语言包缺失时自动回退英文；异常返回空串。
    """
    try:
        result = subprocess.run(
            [_TESSERACT, str(image_path), "-", "-l", lang, "--psm", str(psm)],
            capture_output=True, text=True, errors="ignore", timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        if "chi_sim" in lang and "Failed loading language" in (result.stderr or ""):
            # 语言包缺失，回退到英文
            result = subprocess.run(
                [_TESSERACT, str(image_path), "-", "-l", "eng", "--psm", str(psm)],
                capture_output=True, text=True, errors="ignore", timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def extract_text(image_paths: List[Path], lang: str | None = None) -> str:
    """多张图 OCR 提取文字（每图双 PSM 通道交叉识别后拼接）。

    参数：
        image_paths: 图片路径列表（jpg/png/pdf 等）
        lang: Tesseract 语言（默认自动检测：chi_sim+eng 或 eng）

    返回：
        拼接后的纯文本（多张图用换行分隔，多图信息天然合并）
    """
    if not image_paths:
        return ""
    lang = lang or _LANG

    all_text = []
    for i, img_path in enumerate(image_paths):
        if not Path(img_path).exists():
            continue
        channel_texts = [_ocr_one(img_path, lang, psm) for psm in _PSM_MODES]
        channel_texts = [t for t in channel_texts if t]
        if channel_texts:
            all_text.append(f"=== 图片 {i+1} ===\n" + "\n".join(channel_texts))

    return "\n\n".join(all_text)


# ---- 字段抽取鲁棒化辅助 ----

# 法院「人民法院」形近字映射（OCR 常见误读，如 法→活、院→区）
_FUZZY_COURT_CHAR = {
    "活": "法", "洁": "法", "合": "法", "泊": "法", "泫": "法", "沽": "法",
    "区": "院", "完": "院", "皖": "院", "立": "院", "阮": "院",
}

# 当事人名称后的关键信息词（用于截断名称边界）
_PARTY_STOP_WORDS = (
    "住所地", "住址", "地址", "统一社会信用代码", "法定代表人",
    "负责人", "经营场所", "联系电话", "联系方式", "委托诉讼代理人",
)

# 机构特征词（当事人名称完整度评分用）
_PARTY_CORP_WORDS = re.compile(r"(有限公司|股份公司|有限责任公司|事务所|集团|中心|银行|法院|检察院|委员会)")

# 复合案由词表：文本命中关键词 → 标准案由（词表顺序即优先级）
_CAUSE_KEYWORDS = (
    ("侵害作品信息网络传播权", "侵害作品信息网络传播权纠纷"),
    ("信息网络传播权", "侵害作品信息网络传播权纠纷"),
    ("著作权", "著作权侵权纠纷"),
    ("商标权", "侵害商标权纠纷"),
    ("专利权", "侵害专利权纠纷"),
    ("名誉权", "名誉权纠纷"),
    ("肖像权", "肖像权纠纷"),
    ("买卖合同", "买卖合同纠纷"),
    ("合同纠纷", "合同纠纷"),
)


def _extract_court(text: str) -> Optional[str]:
    """法院抽取：匹配「XX人民YY」，YY 经形近字映射后为「法院」即接受，候选取最长。

    例：北京市朝阳区人民活区 → 北京市朝阳区人民法院
    """
    best = None
    for m in re.finditer(r"([\u4e00-\u9fa5]{2,10}人民)([\u4e00-\u9fa5]{1,2})", text):
        tail = "".join(_FUZZY_COURT_CHAR.get(ch, ch) for ch in m.group(2))
        # group(1) 以「人民」结尾，取「人民」之前的地名前缀
        prefix = m.group(1)[:-2]
        if tail == "法院" and (best is None or len(prefix) > len(best)):
            best = prefix + "人民法院"
    return best


def _extract_party(text: str, role: str) -> Optional[str]:
    """当事人抽取：收集 role 全部出现位置，取后续一段为候选。

    候选清洗：去掉开头冒号/分隔符 → 按标点切首段 → 在身份信息词处截断。
    评分：含机构特征词 +10；名称长度 4-30 +5；长度近 20 加分；略减长名。
    """
    best, best_score = None, -1.0
    for m in re.finditer(role, text):
        seg = text[m.end():m.end() + 120]
        seg = re.sub(r"^[:：,，—\s|、]+", "", seg)
        seg = re.split(r"[，。；;、\n]", seg)[0]
        for stop in _PARTY_STOP_WORDS:
            idx = seg.find(stop)
            if idx != -1:
                seg = seg[:idx]
                break
        # 公司尾词截断：截到机构公司词结尾，滤掉「有限公司经合法转授权…」类正文噪声
        comp = re.search(r"(有限责任公司|股份有限公司|有限公司|股份公司|公司)", seg)
        if comp:
            seg = seg[:comp.end()]
        seg = seg.strip(" ，。、")
        if len(seg) < 2:
            continue
        score = 10.0 if _PARTY_CORP_WORDS.search(seg) else 0.0
        # 标签行「原告：/被告：」置信最高，正文「判令被告支付…」类噪声不得压过标签候选
        if text[m.end():m.end() + 1] in "：:":
            score += 20.0
        score += min(len(seg), 20)
        if 4 <= len(seg) <= 30:
            score += 5.0
        score -= len(seg) / 100.0
        if score > best_score:
            best, best_score = seg, score
    return best


def _extract_cause(text: str) -> Optional[str]:
    """案由四级抽取策略：

    ① 案由标签行（打印件常见，如「案由: 侵害作品信息网络传播权纠纷」）
    ② 复合案由词表（信息网络传播权 → 侵害作品信息网络传播权纠纷）
    ③ 「XX纠纷」正则（清洗常见前缀，放弃超短结果防误配）
    ④ 常见案由关键词（文本含「侵权/纠纷」但无明确词时兜底）
    """
    m = re.search(r"案由[:：,，]?\s*([\u4e00-\u9fa5（）()、·]{2,24})", text)
    if m:
        cause = re.split(r"[，。；;、\n]", re.sub(r"^[:：,，\s]+", "", m.group(1)))[0].strip()
        if len(cause) >= 4:
            return cause
    for keyword, standard in _CAUSE_KEYWORDS:
        if keyword in text:
            return standard
    m = re.search(r"([\u4e00-\u9fa5]{2,8}纠纷)", text)
    if m:
        cause = re.sub(r"^(本案系|本案|系|属|因|为)", "", m.group(1))
        if len(cause) >= 4:
            return cause
    for keyword in ("侵权", "纠纷"):
        idx = text.find(keyword)
        if idx != -1:
            head = re.split(r"[，。；;、\n：:\s]", text[max(0, idx - 8):idx])[-1]
            head = re.sub(r"^[:：,，\s]+", "", head)
            if head:
                return head + "纠纷"
    return None


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

    # 法院：XX人民法院（形近字模糊匹配，候选最长优先）
    result["法院"] = _extract_court(text)

    # 案由：四级策略（案由标签行 → 复合词表 → XX纠纷正则 → 关键词兜底）
    result["案由"] = _extract_cause(text)

    # 原告 / 被告：全候选 + 身份信息词截断 + 完整度评分
    result["原告"] = _extract_party(text, "原告")
    result["被告"] = _extract_party(text, "被告")

    # 开庭时间：2026年X月X日 X:X / 2026-X-X
    # 三级回退：紧邻 → 标签跨行（表头/值分离）→ 容忍竖线噪声（数字被表格线粘连误读为 |/｜/l/I）
    hearing_date_match = re.search(
        r'开庭时间[:：]?\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?(?:日)?)',
        text
    )
    if not hearing_date_match:
        # 回退1：表格表头「开庭时间」与日期值跨行分布（传票表头行/值行分离）
        hearing_date_match = re.search(
            r'开庭时间[\s\S]{0,30}?(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)',
            text
        )
    if not hearing_date_match:
        # 回退2：日期数字被误读为竖线（| ｜ l I），放宽标签距离并容忍该噪声
        hearing_date_match = re.search(
            r'(?:开庭|审理)[\s\S]{0,50}?(\d{4}[-年]\d{1,2}[-月]\s*[\d|il｜lI]{1,2}\s*日?)',
            text
        )
    if hearing_date_match:
        date = (hearing_date_match.group(1)
                .replace("年", "-").replace("月", "-").replace("日", ""))
        # 竖线噪声无法还原真实数字，以 ? 标记待人工核对
        date = re.sub(r'[|il｜lI]{1,2}', '?', date).strip("-")
        result["开庭时间"] = date

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
