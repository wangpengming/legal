"""文档生成器：替换模板【】占位符 + 复制静态 PDF + 打包 zip。

占位符策略：【】按出现顺序（从左到右、从上到下）依次替换。
例：模板「【】年【】月【】日」+ values=['2026','9','15'] →「2026年9月15日」
"""
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from docx import Document

from .config import (
    OUTPUTS_DIR,
    STATIC_DIR,
    get_template_path,
)


# ============================================================
# 占位符替换核心（按位置）
# ============================================================

PLACEHOLDER_PATTERN = re.compile(r"【】")


def replace_placeholders_by_position(paragraph, values: list) -> int:
    """按位置顺序替换段落中的【】占位符。

    参数：
        paragraph: docx 段落对象
        values: 按位置分配的替换值列表（按【】出现顺序）

    返回：成功替换的数量
    """
    full_text = "".join(run.text for run in paragraph.runs)
    if "【" not in full_text or "】" not in full_text:
        return 0

    matches = list(PLACEHOLDER_PATTERN.finditer(full_text))
    if not matches:
        return 0

    if len(values) < len(matches):
        # 不足的值用空字符串
        values = list(values) + [""] * (len(matches) - len(values))

    # 从后往前替换，避免位置偏移
    new_text = full_text
    for i in range(len(matches) - 1, -1, -1):
        match = matches[i]
        value = str(values[i]) if values[i] is not None else ""
        new_text = new_text[: match.start()] + value + new_text[match.end() :]

    if new_text != full_text:
        if paragraph.runs:
            paragraph.runs[0].text = new_text
            for run in paragraph.runs[1:]:
                run.text = ""

    return len(matches)


def replace_placeholders_in_doc(doc: Document, values: list) -> int:
    """替换整个 docx 中的【】占位符（按文档顺序）。"""
    total = 0
    # 段落
    for p in doc.paragraphs:
        total += replace_placeholders_by_position(p, values)
        if total >= len(values):
            break  # 所有值都用完了
    # 表格（如果有）
    if total < len(values):
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        used = replace_placeholders_by_position(p, values[total:])
                        total += used
                        if total >= len(values):
                            break
    return total


# ============================================================
# 数据准备
# ============================================================

def build_case_description(case: dict, our_label: str = "我单位") -> str:
    """生成案由描述。

    原告：我单位诉{对方}{案由}
    被告：{对方}诉我单位{案由}
    第三人：{对方}与我单位{案由}
    """
    opposing = (case.get("opposing_party") or "").strip()
    cause = (case.get("case_cause") or "").strip()
    role = case.get("our_role", "").strip()

    if role == "原告":
        prefix = f"{our_label}诉{opposing}" if opposing else our_label
    elif role == "被告":
        prefix = f"{opposing}诉{our_label}" if opposing else our_label
    elif role == "第三人":
        prefix = f"{opposing}与{our_label}" if opposing else our_label
    else:
        prefix = f"{opposing}与{our_label}" if opposing else our_label

    if cause:
        return f"{prefix}{cause}"
    return prefix


def parse_hearing_date(hearing_date: str) -> dict:
    """从'YYYY-MM-DD' 解析日期，返回 {年, 月, 日}。"""
    if not hearing_date:
        return {"年": "____", "月": "__", "日": "__"}
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            dt = datetime.strptime(hearing_date, fmt)
            return {"年": str(dt.year), "月": str(dt.month), "日": str(dt.day)}
        except ValueError:
            continue
    return {"年": "____", "月": "__", "日": "__"}


# ============================================================
# 模板专用 values 构造（按【】位置顺序）
# ============================================================

def values_for_legal_rep_cert(case: dict, company: dict) -> list:
    """法定代表人证明模板：【】年【】月【】日"""
    parts = parse_hearing_date(case.get("hearing_date"))
    return [parts["年"], parts["月"], parts["日"]]


def values_for_power_of_attorney(case: dict, company: dict, agent: dict) -> list:
    """授权委托书模板（5 个【】，按位置）：
      1. 【】纠纷  → 案由描述
      2. （案号：【】）  → 案号
      3. 日期：【】年【】月【】日  → 年、月、日
    """
    description = build_case_description(case)
    case_number = case.get("case_number", "")
    parts = parse_hearing_date(case.get("hearing_date"))
    return [
        description,        # 1. 【】纠纷
        case_number,        # 2. （案号：【】）
        parts["年"],        # 3. 日期：【】年
        parts["月"],        # 4. 【】月
        parts["日"],        # 5. 【】日
    ]


def values_for_recommendation(case: dict, company: dict, agent: dict) -> list:
    """推荐信模板（5 个【】，按位置）：
      1. 【】人民法院  → 法院
      2. 与【】纠纷  → 案由描述
      3. （案号：【】）  → 案号
      4. 【】年【】月【】日  → 年、月、日
    """
    court = case.get("court", "")
    description = build_case_description(case)
    case_number = case.get("case_number", "")
    parts = parse_hearing_date(case.get("hearing_date"))
    return [
        court,              # 1. 【】人民法院
        description,        # 2. 与【】纠纷
        case_number,        # 3. （案号：【】）
        parts["年"],        # 4. 【】年
        parts["月"],        # 5. 【】月
        parts["日"],        # 6. 【】日
    ]


# ============================================================
# 生成与打包
# ============================================================

def generate_dynamic_docx(template_key: str, values: list, output_path: Path) -> int:
    """根据模板生成填充后的 docx，返回替换的占位符数量。"""
    template_path = get_template_path(template_key)
    doc = Document(str(template_path))
    count = replace_placeholders_in_doc(doc, values)
    doc.save(str(output_path))
    return count


def generate_court_matters(case: dict, company: dict, agent: dict) -> Path:
    """生成完整出庭手续，返回输出目录路径。

    输出结构：
      outputs/YYYY-MM-DD_<案号>/
        ├── 01_营业执照.pdf
        ├── 02_法定代表人证明_<案号>.docx
        ├── 03_法人身份证.pdf
        ├── 04_授权委托书_<案号>.docx
        ├── 05_推荐信_<案号>.docx
        ├── 06_代理人劳动合同.pdf
        ├── 07_代理人身份证.pdf
        └── 出庭手续全套_<案号>.zip
    """
    case_number = case.get("case_number", "未命名案件")
    hearing_date = case.get("hearing_date") or datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{hearing_date}_{sanitize_filename(case_number)}"
    output_dir = OUTPUTS_DIR / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_case = sanitize_filename(case_number)

    # === 动态生成 3 份 docx ===
    legal_values = values_for_legal_rep_cert(case, company)
    legal_rep_path = output_dir / f"02_法定代表人证明_{safe_case}.docx"
    generate_dynamic_docx("legal_rep_cert", legal_values, legal_rep_path)

    poa_values = values_for_power_of_attorney(case, company, agent)
    poa_path = output_dir / f"04_授权委托书_{safe_case}.docx"
    generate_dynamic_docx("power_of_attorney", poa_values, poa_path)

    rec_values = values_for_recommendation(case, company, agent)
    rec_path = output_dir / f"05_推荐信_{safe_case}.docx"
    generate_dynamic_docx("recommendation", rec_values, rec_path)

    # === 复制静态 PDF（按出庭顺序）===
    static_files = [
        ("01_营业执照.pdf", STATIC_DIR / "1.营业执照复印件.pdf"),
        ("03_法人身份证.pdf", STATIC_DIR / "法人身份证.pdf"),
        ("06_代理人劳动合同.pdf", STATIC_DIR / "代理人劳动合同.pdf"),
        ("07_代理人身份证.pdf", STATIC_DIR / "代理人身份证.pdf"),
    ]
    for target_name, src_path in static_files:
        if src_path.exists():
            shutil.copy2(src_path, output_dir / target_name)

    # === 打包 zip ===
    zip_path = output_dir / f"出庭手续全套_{safe_case}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(output_dir.iterdir()):
            if file.suffix == ".zip":
                continue
            zf.write(file, arcname=file.name)

    return output_dir


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    if not name:
        return "未命名"
    cleaned = re.sub(r'[\\/:*?"<>|\s]', "_", name).strip("_")
    return cleaned[:80] or "未命名"


def open_in_finder(path: Path):
    """在 macOS Finder 中打开文件/目录。"""
    import subprocess
    subprocess.Popen(["open", str(path)])
