"""文档生成器：替换模板【】占位符 + 复制静态 PDF + 打包 zip。

占位符策略：【】按出现顺序（从左到右、从上到下）依次替换。
例：模板「【】年【】月【】日」+ values=['2026','9','15'] →「2026年9月15日」

公共 API（v1.1.2）：
- generate_court_matters(case, company, agent) → 写到 OUTPUTS_DIR（写入数据库由调用方负责）
- generate_preview(case, company, agent) → 写到临时目录（不写数据库）

设计原则（中天经验）：
- 抽离 _generate_to_dir 内部函数，两种入口共享逻辑
- 仅预览不污染 outputs 历史、不写数据库
"""
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Tuple

import platform

from docx import Document

from config import (  # noqa: F401  # 顶层平铺
    OUTPUTS_DIR,
    PROJECT_ROOT,
    STATIC_DIR,
    AGENT_STATIC_FALLBACK,
    get_template_path,
)
from docx_to_pdf import docx_to_pdf
from pdf_merger import merge_pdfs


# ============================================================
# F-033 辅助函数：解析代理人级 PDF 路径
# ============================================================

# 输出文件名 → 数据库字段映射
_AGENT_PATH_KEYS = {
    "06_代理人劳动合同.pdf": "contract_pdf_path",
    "07_代理人身份证.pdf": "id_card_pdf_path",
}


def _resolve_agent_pdf(agent: dict, target_name: str, fallback_filename: str):
    """F-033 解析代理人级 PDF 源路径。

    优先级：
        1. agent[path_key]（按 target_name 选 contract_pdf_path / id_card_pdf_path）
           - 相对路径相对 PROJECT_ROOT 解析
           - 文件不存在则跳过
        2. STATIC_DIR / fallback_filename（默认 fallback）
        3. 都找不到返回 None

    返回：
        Path 对象；None 表示该文件应跳过（不影响其他文件生成）

    设计：
    - 纯函数，易测试（不依赖 docx 模板 / 数据库）
    - 与 _generate_to_dir 解耦
    """
    path_key = _AGENT_PATH_KEYS.get(target_name)
    if path_key:
        custom = agent.get(path_key)
        if custom:
            candidate = Path(custom)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            if candidate.exists():
                return candidate
    fallback = STATIC_DIR / fallback_filename
    if fallback.exists():
        return fallback
    return None


def validate_agent_paths(agents: list) -> dict:
    """F-041 校验代理人的 PDF 路径。

    返回：
        dict[int, dict]，键是 agent_id，值含 "valid"（存在的字段名列表）和 "invalid"（失效字段名列表）
        只返回有失效字段的 agent；空字典表示所有路径都 OK。

    用途：UI 启动/侧边栏加载时校验，失效的 agent 在 UI 上标红 + 提示"请重新上传"。

    注意：空字段（未上传）不算失效；相对路径相对 PROJECT_ROOT 解析。
    """
    result = {}
    for agent in agents:
        agent_id = agent["id"]
        valid = []
        invalid = []
        for key in ("contract_pdf_path", "id_card_pdf_path"):
            rel_path = agent.get(key)
            if not rel_path:
                continue
            full = PROJECT_ROOT / rel_path
            if full.exists():
                valid.append(key)
            else:
                invalid.append(key)
        if invalid:
            result[agent_id] = {
                "agent_name": agent.get("name", ""),
                "valid": valid,
                "invalid": invalid,
            }
    return result


def save_agent_pdf(agent_id: int, file_bytes: bytes, file_type: str) -> str:
    """F-032 保存代理人上传的 PDF 到 static/agents/<id>/。

    参数：
        agent_id: 代理人 ID（用于创建子目录）
        file_bytes: PDF 二进制内容（来自 st.file_uploader.read()）
        file_type: "contract"（劳动合同）或 "id_card"（身份证）

    返回：
        相对 PROJECT_ROOT 的路径字符串（存入数据库）

    特性：
        - UUID 8 位哈希命名（避免冲突 + 不含敏感信息）
        - 自动创建目录
        - 异常时清理已创建文件
    """
    if file_type not in ("contract", "id_card"):
        raise ValueError(f"file_type 必须是 'contract' 或 'id_card'，实际 {file_type}")

    agent_dir = STATIC_DIR / "agents" / str(agent_id)
    agent_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{file_type}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = agent_dir / file_name
    try:
        file_path.write_bytes(file_bytes)
    except OSError:
        if file_path.exists():
            file_path.unlink()
        raise

    return str(file_path.relative_to(PROJECT_ROOT))


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
    """替换整个 docx 中的【】占位符（按文档顺序）。

    ⚠️ 修复 v1.1.1：每段调用 replace_placeholders_by_position 时必须传 values[total:] 切片，
    否则同一段落或后续段落会从 values[0] 重新使用，导致 description/案号 错位。
    """
    total = 0
    # 段落
    for p in doc.paragraphs:
        used = replace_placeholders_by_position(p, values[total:])
        total += used
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
    """生成案由描述主体（不含「我单位诉」/「诉我单位」/「与我单位」前缀，由模板拼装）。

    完整语义模板「我单位与【】一案」+ description「上海某某科技公司买卖合同纠纷」
    →「我单位与上海某某科技公司买卖合同纠纷一案」✅ 正确。

    ⚠️ 修复 v1.1.1：避免「我单位与我单位诉...」重复。
    description 只返回主体「{对方}{案由}」，模板负责拼装「我单位」与「一案」字样。
    """
    opposing = (case.get("opposing_party") or "").strip()
    cause = (case.get("case_cause") or "").strip()

    # 只拼接「对方 + 案由」，不带「我单位」也不带「诉/与」字样
    if opposing and cause:
        return f"{opposing}{cause}"
    if cause:
        return cause
    if opposing:
        return opposing
    return ""


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
# F-036 注：法定代表人证明改为固定静态文件（不再 dynamic 生成）。
# 模板 templates/2.法定代表人证明.docx 废除；改从 static/2.法定代表人证明.doc 复制。
# 理由：法定代表人证明是公司级静态材料（与具体案件/日期无关），保留"马杰"版即可。


def values_for_power_of_attorney(case: dict, company: dict, agent: dict) -> list:
    """授权委托书模板（9 个【】，按文档出现顺序，F-038 调整）：

      [5]  受委托人：【】       → 1. 代理人姓名（agent.name）
      [7]  职务：【】          → 2. 代理人职务（agent.position）
      [7]  电话：【】          → 3. 代理人电话（agent.phone）
      [9]  与【】纠纷          → 4. 对方当事人（case.opposing_party）
      [9]  【】纠纷（案号：【】）→ 5. 案由（case.case_cause）
      [9]  （案号：【】）      → 6. 案号（case.case_number）
      [14] 【】年【】月【】日  → 7-9. 年、月、日

    F-038 调整：模板已改回"受委托人【】/职务【】/电话【】"（不要身份证号）。
    案由描述不再拼装（description 函数），改为独立【】对方 + 【】案由。
    """
    agent_name = (agent.get("name") or "").strip()
    agent_position = (agent.get("position") or "").strip()
    agent_phone = (agent.get("phone") or "").strip()
    opposing = (case.get("opposing_party") or "").strip()
    cause = (case.get("case_cause") or "").strip()
    case_number = case.get("case_number", "")
    parts = parse_hearing_date(case.get("hearing_date"))
    return [
        agent_name,         # 1. 【】受委托人
        agent_position,     # 2. 【】职务
        agent_phone,        # 3. 【】电话
        opposing,           # 4. 与【】（对方当事人）
        cause,              # 5. 【】（案由）
        case_number,        # 6. （案号：【】）
        parts["年"],        # 7. 【】年
        parts["月"],        # 8. 【】月
        parts["日"],        # 9. 【】日
    ]


def values_for_recommendation(case: dict, company: dict, agent: dict) -> list:
    """推荐信模板（11 个【】，按文档出现顺序，F-038 调整）：

      【】人民法院：                       → 1. 法院（case.court）
      兹推荐本公司员工【】                 → 2. 代理人姓名（agent.name）
      性别：【】                            → 3. 代理人性别（agent.gender）
      身份证号：【】                        → 4. 代理人身份证（agent.id_card）
      职务：【】                            → 5. 代理人职务（agent.position）
      与【】纠纷                            → 6. 对方当事人（case.opposing_party）
      【】纠纷（案号：【】）                  → 7. 案由（case.case_cause）
      （案号：【】）                        → 8. 案号（case.case_number）
      【】年【】月【】日                    → 9-11. 年、月、日

    F-038 调整：模板已改回"员工【】/性别【】/身份证号【】/职务【】"。
    案由描述不再拼装，改为独立【】对方 + 【】案由。
    """
    court = case.get("court", "")
    agent_name = (agent.get("name") or "").strip()
    agent_gender = (agent.get("gender") or "").strip()
    agent_id = (agent.get("id_card") or "").strip()
    agent_position = (agent.get("position") or "").strip()
    agent_phone = (agent.get("phone") or "").strip()  # F-051 新增
    opposing = (case.get("opposing_party") or "").strip()
    cause = (case.get("case_cause") or "").strip()
    case_number = case.get("case_number", "")
    parts = parse_hearing_date(case.get("hearing_date"))
    return [
        court,              # 1. 【】人民法院
        agent_name,         # 2. 兹推荐本公司员工【】
        agent_gender,       # 3. 性别：【】
        agent_id,           # 4. 身份证号：【】
        agent_position,     # 5. 职务：【】
        agent_phone,        # 6. 电话：【】（F-051 新增）
        opposing,           # 7. 与【】（对方当事人）
        cause,              # 8. 【】（案由）
        case_number,        # 9. （案号：【】）
        parts["年"],        # 10. 【】年
        parts["月"],        # 11. 【】月
        parts["日"],        # 12. 【】日
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


def _generate_to_dir(case: dict, company: dict, agent: dict, output_dir: Path) -> Path:
    """把案件材料生成到指定目录（不写数据库，纯文件系统操作）。

    这是所有生成入口的内部核心：动态 docx + 静态 PDF 拷贝 + 合并 + zip 打包。

    参数：
        case: 案件数据（来自表单或数据库）
        company: 公司数据
        agent: 代理人数据
        output_dir: 输出目录（必须已创建）

    返回：
        output_dir

    F-043 物理隔离：若 output_dir 已存在（同案号重新生成场景），先清空整个
    目录再重建，避免新旧文件混合导致二次污染。临时目录（tmp）每次 mkdtemp
    都不存在，无需清空。
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    safe_case = sanitize_filename(case.get("case_number", "未命名案件"))

    # === 动态生成 2 份 docx + PDF（F-036 调整：02 法定代表人证明改为静态复制）===
    dynamic_templates = [
        ("power_of_attorney", values_for_power_of_attorney(case, company, agent), "04_授权委托书"),
        ("recommendation", values_for_recommendation(case, company, agent), "05_推荐信"),
    ]
    for template_key, values, base_name in dynamic_templates:
        docx_path = output_dir / f"{base_name}_{safe_case}.docx"
        pdf_path = output_dir / f"{base_name}_{safe_case}.pdf"
        template_path = get_template_path(template_key)
        doc = Document(str(template_path))
        replace_placeholders_in_doc(doc, values)
        doc.save(str(docx_path))
        # DOCX → PDF（鲁棒降级：失败仅警告，不阻塞）
        try:
            docx_to_pdf(docx_path, pdf_path)
        except Exception as e:  # noqa: BLE001
            import warnings
            warnings.warn(f"DOCX→PDF 转换失败（跳过）: {docx_path.name} → {e}", stacklevel=2)

    # === 复制静态 PDF ===
    # 公司级（与代理人无关，固定）
    from config import COMPANY_STATIC
    for src_name in COMPANY_STATIC:
        src_path = STATIC_DIR / src_name
        if src_path.exists():
            # 输出文件名映射：1.营业执照复印件.pdf → 01_营业执照.pdf
            target_idx = "01" if "营业执照" in src_name else "03"
            target_suffix = "营业执照" if "营业执照" in src_name else "法人身份证"
            target_name = f"{target_idx}_{target_suffix}.pdf"
            shutil.copy2(src_path, output_dir / target_name)

    # F-036 法定代表人证明：固定静态 PDF 文件（从 static/2.法定代表人证明.pdf 复制）
    # 输出为 .pdf（与 04/05 一样进入 00_合并出庭手续.pdf）
    legal_rep_src = STATIC_DIR / "2.法定代表人证明.pdf"
    if legal_rep_src.exists():
        shutil.copy2(legal_rep_src, output_dir / f"02_法定代表人证明_{safe_case}.pdf")

    # 代理人级（F-033：按当前 agent 路径取，fallback 到默认文件）
    for target_name, fallback_filename in AGENT_STATIC_FALLBACK.items():
        src_path = _resolve_agent_pdf(agent, target_name, fallback_filename)
        if src_path:
            shutil.copy2(src_path, output_dir / target_name)

    # === 合并 7 份 PDF 为 1 份 ===
    all_pdfs = sorted(output_dir.glob("0?_*.pdf"))  # 匹配 01-07
    if all_pdfs:
        merged_pdf = output_dir / f"00_合并出庭手续_{safe_case}.pdf"
        try:
            merge_pdfs(all_pdfs, merged_pdf)
        except ValueError:
            # 没有任何可合并的 PDF（所有 PDF 都生成失败）
            pass

    # === 打包 zip（合并 PDF 置顶 + 其余按出庭顺序）===
    zip_path = output_dir / f"出庭手续全套_{safe_case}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 合并 PDF 最先
        merged = output_dir / f"00_合并出庭手续_{safe_case}.pdf"
        if merged.exists():
            zf.write(merged, arcname=merged.name)
        # 2. 其余按编号顺序
        for file in sorted(output_dir.iterdir()):
            if file.suffix == ".zip":
                continue
            if file.name == merged.name:
                continue  # 上面已写
            zf.write(file, arcname=file.name)

    return output_dir


def generate_court_matters(case: dict, company: dict, agent: dict) -> Path:
    """生成完整出庭手续到 OUTPUTS_DIR，返回输出目录路径。

    v1.1.2 重构：内部委托 _generate_to_dir（与 generate_preview 共享核心逻辑）。

    输出结构：
      outputs/YYYY-MM-DD_<案号>/
        ├── 00_合并出庭手续_<案号>.pdf       （7 份 PDF 合一份）
        ├── 01_营业执照.pdf
        ├── 02_法定代表人证明_<案号>.docx
        ├── 02_法定代表人证明_<案号>.pdf
        ├── 03_法人身份证.pdf
        ├── 04_授权委托书_<案号>.docx
        ├── 04_授权委托书_<案号>.pdf
        ├── 05_推荐信_<案号>.docx
        ├── 05_推荐信_<案号>.pdf
        ├── 06_代理人劳动合同.pdf
        ├── 07_代理人身份证.pdf
        └── 出庭手续全套_<案号>.zip

    鲁棒性（NFR-5.6）：
    - 任一 DOCX→ PDF 转换失败只跳过该份 PDF，不阻塞其他文件
    - 静态 PDF 缺失则跳过该份，不阻塞
    - 最终的合并 PDF 也被加进 ZIP
    """
    case_number = case.get("case_number", "未命名案件")
    hearing_date = case.get("hearing_date") or datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{hearing_date}_{sanitize_filename(case_number)}"
    output_dir = OUTPUTS_DIR / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return _generate_to_dir(case, company, agent, output_dir)


def generate_preview(case: dict, company: dict, agent: dict) -> Path:
    """仅预览：生成到临时目录，不写 outputs 不写数据库。

    v1.1.2 新增（中天经验，task-018.jsonl line 143）：
    - 用户点「仅预览」时实际生成 PDF，不污染 outputs 历史
    - 复用 _generate_to_dir 完整生成逻辑
    - 返回临时目录路径，调用方负责清理（用 shutil.rmtree）

    返回：
        临时目录路径（包含 00_合并出庭手续_*.pdf 等所有文件）
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="court_preview_"))
    return _generate_to_dir(case, company, agent, tmp_dir)


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


def print_pdf_to_default_printer(pdf_path: Path) -> Tuple[bool, str]:
    """F-037 在线打印：直接把 PDF 送到系统默认打印机（绕过浏览器对话框）。

    实现思路：调系统命令行工具（macOS `lp` / Linux `lp` / Windows PowerShell），
    区别于 `window.print()`（浏览器 API，总会弹打印对话框）。

    返回：
        (success: bool, message: str)
        - success=True → message 是 lp 的 stdout（含 request id）
        - success=False → message 是错误描述（用于 UI 显示）

    跨平台：
        - macOS： `lp <file>`  → CUPS 默认打印机
        - Linux： `lp <file>`  → CUPS 默认打印机
        - Windows： `Start-Process -FilePath <file> -Verb Print` → ShellExecute 静默打印
    """
    if not pdf_path.exists():
        return False, f"PDF 不存在: {pdf_path}"

    system = platform.system()

    try:
        if system in ("Darwin", "Linux"):
            # CUPS lp 命令（macOS / Linux）
            result = subprocess.run(
                ["lp", str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # lp 输出例: "request id is HP-LaserJet-1 (1 file(s))"
                return True, result.stdout.strip() or "打印任务已提交"
            return False, f"lp 失败 (code={result.returncode}): {result.stderr.strip()}"

        elif system == "Windows":
            # PowerShell 调 ShellExecute 静默打印（不弹 Adobe Reader 对话框）
            ps_cmd = (
                f'Start-Process -FilePath "{pdf_path}" -Verb Print'
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, "打印任务已提交（Windows ShellExecute）"
            return False, f"PowerShell 失败: {result.stderr.strip()}"

        else:
            return False, f"不支持的系统: {system}（仅 macOS / Linux / Windows）"

    except subprocess.TimeoutExpired:
        return False, "打印命令超时（30s）— 请检查打印机状态"
    except FileNotFoundError as e:
        return False, f"系统打印命令未找到: {e}"
    except Exception as e:
        return False, f"打印异常: {e}"
