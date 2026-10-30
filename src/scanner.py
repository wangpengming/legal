# =============================================
# scanner.py - 目录扫描器
# 递归扫描目录，发现案件材料文件，识别类型，推断案件信息
# =============================================
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class FileType(Enum):
    """文件类型"""
    DOCX = "docx"
    PDF = "pdf"
    TXT = "txt"
    MD = "md"
    IMAGE = "image"
    OTHER = "other"


class FileCategory(Enum):
    """文件分类（基于文件名关键词）"""
    PLIFFING_STATEMENT = "起诉状"           # 起诉状/诉状
    DEFENSE_STATEMENT = "答辩状"           # 答辩状
    EVIDENCE_LIST = "证据清单"             # 证据/清单/目录
    CONTRACT = "合同协议"                   # 合同/协议/授权
    JUDGMENT = "裁判文书"                  # 判决/裁定/裁决
    SUMMONS = "程序文书"                   # 传票/通知
    CROSS_EXAM = "质证意见"                # 质证
    OTHER = "其他材料"


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    type: FileType
    category: FileCategory
    size: int
    modified: datetime
    content_preview: str = ""

    @property
    def size_kb(self) -> str:
        """文件大小（KB）"""
        return f"{self.size / 1024:.1f} KB"

    @property
    def name(self) -> str:
        """文件名"""
        return self.path.name


@dataclass
class CaseMetadata:
    """推断的案件元数据"""
    case_name: Optional[str] = None
    case_number: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    cause: Optional[str] = None
    court: Optional[str] = None
    filing_date: Optional[str] = None


@dataclass
class ScanResult:
    """目录扫描结果"""
    root_path: Path
    case_name: str
    files: list[FileInfo] = field(default_factory=list)
    metadata: CaseMetadata = field(default_factory=CaseMetadata)
    confidence: float = 0.0

    @property
    def file_count(self) -> int:
        """文件数量"""
        return len(self.files)

    @property
    def summary(self) -> str:
        """摘要信息"""
        cats = {}
        for f in self.files:
            cat = f.category.value
            cats[cat] = cats.get(cat, 0) + 1
        cat_str = ", ".join(f"{v}个{k}" for k, v in cats.items())
        return cat_str or "无文件"


# =============================================
# 文件类型识别
# =============================================

SUPPORTED_TYPES = {".docx", ".pdf", ".txt", ".md"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def get_file_type(path: Path) -> FileType:
    """根据扩展名识别文件类型"""
    ext = path.suffix.lower()
    if ext == ".docx":
        return FileType.DOCX
    elif ext == ".pdf":
        return FileType.PDF
    elif ext == ".txt":
        return FileType.TXT
    elif ext == ".md":
        return FileType.MD
    elif ext in IMAGE_TYPES:
        return FileType.IMAGE
    else:
        return FileType.OTHER


def is_supported_file(path: Path) -> bool:
    """判断是否为支持的文件类型（过滤 OCR 噪音）"""
    if path.suffix.lower() not in SUPPORTED_TYPES:
        return False
    # 过滤 OCR 噪音文件
    name_lower = path.name.lower()
    # 过滤包含页码+OCR参数的噪音文件
    # 如: __p001.txt, __p001_dpi400_psm11.txt, _p001.txt, page_001.txt
    if re.search(r'__p\d+.*\.txt$|_p\d+.*\.txt$|page_\d+.*\.txt$|^\d+\.txt$', name_lower):
        return False
    # 过滤无意义文件名（如纯数字.txt）
    if re.match(r'^\d+\.txt$', name_lower):
        return False
    return True


# =============================================
# 文件分类
# =============================================

# 分类关键词映射
CATEGORY_KEYWORDS = {
    FileCategory.PLIFFING_STATEMENT: [
        "起诉状", "诉状", "民事起诉", "起诉书", "起诉",
    ],
    FileCategory.DEFENSE_STATEMENT: [
        "答辩状", "答辩书", "答辩", "反诉状", "答辩意见",
    ],
    FileCategory.EVIDENCE_LIST: [
        "证据", "清单", "目录", "证据清单", "证据目录",
    ],
    FileCategory.CONTRACT: [
        "合同", "协议", "授权书", "授权委托", "许可协议",
        "合作协议", "授权许可",
    ],
    FileCategory.JUDGMENT: [
        "判决", "判决书", "裁定", "裁定书", "裁决", "裁决书",
        "调解", "调解书",
    ],
    FileCategory.SUMMONS: [
        "传票", "通知", "开庭通知", "立案通知", "应诉通知",
    ],
    FileCategory.CROSS_EXAM: [
        "质证", "质证意见", "质证清单", "质证要点",
    ],
}


def categorize_file(filename: str) -> FileCategory:
    """根据文件名分类"""
    filename_lower = filename.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in filename_lower:
                return category
    return FileCategory.OTHER


# =============================================
# 案件信息推断
# =============================================

# 案号正则表达式
CASE_NUMBER_PATTERNS = [
    r"[\u4e00-\u9fa5]{2,4}\d{2,4}[\u4e00-\u9fa5]\d+[\u9fa5民初]\d+号",
    r"\d{4}[\u5e74]\d{1,2}[\u6708]\d{1,2}[\u65e5].*?号",
    r"\([\u4e00-\u9fa5]*?\d{4}[\u5e74].*?号\)",
    r"\d{2,4}年[\u4e00-\u9fa5]+字第\d+号",
]

# 当事人关键词
PLAINTIFF_KEYWORDS = ["原告", "起诉人", "上诉人", "申请执行人"]
DEFENDANT_KEYWORDS = ["被告", "被起诉人", "被上诉人", "被执行人"]


def extract_case_number(text: str) -> Optional[str]:
    """从文本中提取案号"""
    for pattern in CASE_NUMBER_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def extract_parties(text: str) -> tuple[Optional[str], Optional[str]]:
    """从文本中提取当事人"""
    plaintiff = None
    defendant = None
    
    # 提取原告
    for kw in PLAINTIFF_KEYWORDS:
        pattern = rf"{kw}[:：]\s*([^\n，,。]+)"
        match = re.search(pattern, text)
        if match:
            plaintiff = match.group(1).strip()
            break
    
    # 提取被告
    for kw in DEFENDANT_KEYWORDS:
        pattern = rf"{kw}[:：]\s*([^\n，,。]+)"
        match = re.search(pattern, text)
        if match:
            defendant = match.group(1).strip()
            break
    
    return plaintiff, defendant


def extract_cause(text: str) -> Optional[str]:
    """从文本中提取案由"""
    cause_keywords = [
        "案由", "纠纷类型", "案件类型",
    ]
    for kw in cause_keywords:
        pattern = rf"{kw}[:：]\s*([^\n，,。]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    
    # 常见案由关键词
    common_causes = [
        "著作权侵权", "侵害作品", "信息网络传播权",
        "合同纠纷", "借款合同", "买卖合同",
        "劳动争议", "追偿权", "侵权责任",
        "商标权", "专利权", "不正当竞争",
    ]
    text_lower = text.lower()
    for cause in common_causes:
        if cause in text_lower:
            return cause
    
    return None


def infer_case_name_from_path(path: Path) -> str:
    """从路径推断案件名称"""
    # 取目录名
    name = path.name
    # 清理常见前缀
    name = re.sub(r"^\d+[.、-]\s*", "", name)
    name = re.sub(r"^【.*?】\s*", "", name)
    return name.strip() or path.parent.name


def infer_metadata_from_files(files: list[FileInfo]) -> CaseMetadata:
    """从文件列表推断案件元数据"""
    metadata = CaseMetadata()
    
    # 合并所有文件的前500字内容
    combined_text = "\n".join(f.content_preview for f in files if f.content_preview)
    
    if combined_text:
        metadata.case_number = extract_case_number(combined_text)
        metadata.plaintiff, metadata.defendant = extract_parties(combined_text)
        metadata.cause = extract_cause(combined_text)
    
    return metadata


# =============================================
# 目录扫描
# =============================================

def scan_directory(
    root_path: Path,
    recursive: bool = True,
    max_depth: int = 3,
    current_depth: int = 0,
) -> ScanResult:
    """
    扫描目录，返回扫描结果
    
    Args:
        root_path: 根目录路径
        recursive: 是否递归扫描
        max_depth: 最大递归深度
        current_depth: 当前深度
    
    Returns:
        ScanResult: 扫描结果
    """
    root_path = Path(root_path).resolve()
    
    if not root_path.exists():
        raise FileNotFoundError(f"目录不存在: {root_path}")
    
    if not root_path.is_dir():
        raise NotADirectoryError(f"不是目录: {root_path}")
    
    files: list[FileInfo] = []
    
    # 扫描文件
    if recursive and current_depth < max_depth:
        # 递归扫描子目录
        try:
            for item in sorted(root_path.iterdir()):
                if item.is_dir():
                    files.extend(scan_directory(
                        item, recursive=True, 
                        max_depth=max_depth, 
                        current_depth=current_depth + 1
                    ).files)
                elif is_supported_file(item):
                    files.append(_create_file_info(item))
        except PermissionError:
            pass
    else:
        # 仅扫描当前目录
        try:
            for item in sorted(root_path.iterdir()):
                if item.is_file() and is_supported_file(item):
                    files.append(_create_file_info(item))
        except PermissionError:
            pass
    
    # 推断案件名称
    case_name = infer_case_name_from_path(root_path)
    
    # 推断元数据
    metadata = infer_metadata_from_files(files)
    metadata.case_name = case_name
    
    # 计算置信度
    confidence = _calculate_confidence(metadata, files)
    
    return ScanResult(
        root_path=root_path,
        case_name=case_name,
        files=files,
        metadata=metadata,
        confidence=confidence,
    )


def _create_file_info(path: Path) -> FileInfo:
    """创建文件信息"""
    stat = path.stat()
    file_type = get_file_type(path)
    category = categorize_file(path.name)
    
    return FileInfo(
        path=path,
        type=file_type,
        category=category,
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime),
    )


def _calculate_confidence(metadata: CaseMetadata, files: list[FileInfo]) -> float:
    """计算元数据推断置信度"""
    score = 0.0
    
    if metadata.case_number:
        score += 0.3
    if metadata.plaintiff:
        score += 0.2
    if metadata.defendant:
        score += 0.2
    if metadata.cause:
        score += 0.2
    
    # 文件数量加成
    if len(files) >= 3:
        score += 0.1
    
    return min(score, 1.0)


# =============================================
# 格式化输出
# =============================================

def format_scan_result(result: ScanResult) -> str:
    """格式化扫描结果为可读字符串"""
    lines = [
        f"📁 扫描目录: {result.root_path}",
        f"{'━' * 50}",
        f"📋 案件名称: {result.case_name}",
        f"   置信度: {result.confidence * 100:.0f}%",
        f"",
        f"📄 发现文件 ({result.file_count} 个):",
    ]
    
    for f in result.files:
        cat_emoji = {
            FileCategory.PLIFFING_STATEMENT: "📝",
            FileCategory.DEFENSE_STATEMENT: "🛡️",
            FileCategory.EVIDENCE_LIST: "📋",
            FileCategory.CONTRACT: "📄",
            FileCategory.JUDGMENT: "⚖️",
            FileCategory.SUMMONS: "📨",
            FileCategory.CROSS_EXAM: "🔍",
            FileCategory.OTHER: "📎",
        }.get(f.category, "📎")
        lines.append(
            f"   {cat_emoji} {f.name:<40} [{f.category.value}] {f.size_kb}"
        )
    
    lines.append("")
    lines.append("🔍 推断信息:")
    
    m = result.metadata
    if m.case_number:
        lines.append(f"   案号: {m.case_number}")
    if m.plaintiff:
        lines.append(f"   原告: {m.plaintiff}")
    if m.defendant:
        lines.append(f"   被告: {m.defendant}")
    if m.cause:
        lines.append(f"   案由: {m.cause}")
    if m.court:
        lines.append(f"   法院: {m.court}")
    
    if not any([m.case_number, m.plaintiff, m.defendant, m.cause, m.court]):
        lines.append("   （无法从文件名推断，请检查文件内容）")
    
    return "\n".join(lines)
