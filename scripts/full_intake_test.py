#!/usr/bin/env python3
"""
完整案例录入测试脚本
对桌面往年案例目录下的所有案例执行完整的录入流程
"""
import sys
import os
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import re
import json
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import fitz
import pytesseract
from PIL import Image
import io

# 配置
BASE_DIRS = {
    "2024": "/Users/zhangyang/Desktop/往年案例/2024年度已结案",
    "2025": "/Users/zhangyang/Desktop/往年案例/2025年度已结案",
    "2026": "/Users/zhangyang/Desktop/往年案例/2026年度已结案",
}

@dataclass
class CaseInfo:
    """案例信息"""
    year: str
    dir_name: str
    dir_path: Path
    case_number: str = ""
    plaintiff: str = ""
    defendant: str = ""
    cause: str = ""
    court: str = ""
    case_name: str = ""
    files: List[str] = field(default_factory=list)
    ocr_text: str = ""
    status: str = "pending"  # pending/extracted/failed
    quality: str = "C"  # A/B/C
    issues: List[str] = field(default_factory=list)
    artifacts: int = 0

def parse_directory_name(dir_name: str, year: str) -> dict:
    """从目录名解析基本信息"""
    info = {
        "case_number": "",
        "plaintiff": "",
        "defendant": "",
        "cause": "",
        "court": "",
        "case_name": dir_name,
    }
    
    # 提取案号
    case_patterns = [
        r'(\d{6}[-‐]?\d{4}[^\d\-‐]*?[民行刑][^\d\-‐]*?[\d号]+号?)',
        r'（(\d{4})）.?.?[民行刑][\u4e00-\u9fa5]+?[\d、号\s]+号',
        r'\((\d{4})\)[^\(]*?[民行刑][^\)]*?[\d、号\s]+号?',
        r'[\（\(](\d{4})[\）\)][^\（\)]*[民行刑][^\)]*?[\d、号\s]+号?',
    ]
    for pattern in case_patterns:
        match = re.search(pattern, dir_name)
        if match:
            info["case_number"] = match.group(0)
            break
    
    # 提取原告（诉前）
    plaintiff_match = re.search(r'^(\d{6}[-‐])?([^\-‐诉]+?)\s*诉', dir_name)
    if plaintiff_match:
        info["plaintiff"] = plaintiff_match.group(2).strip()
    
    # 提取被告（诉后）
    if '诉' in dir_name:
        parts = re.split(r'\s*诉\s*', dir_name)
        if len(parts) >= 2:
            # 被告在第二部分，取第一个顿号/逗号前的部分
            defendant_part = parts[1]
            defendant = re.split(r'[、，,]', defendant_part)[0].strip()
            info["defendant"] = defendant
    
    # 提取法院
    court_keywords = ["人民法院", "法院", "仲裁委员会", "互联网法院"]
    for kw in court_keywords:
        if kw in dir_name:
            idx = dir_name.index(kw)
            start = max(0, idx - 20)
            info["court"] = dir_name[start:idx + len(kw)]
            break
    
    # 提取案由
    cause_keywords = {
        "信网权": "侵害作品信息网络传播权纠纷",
        "著作权": "著作权纠纷",
        "合同纠纷": "合同纠纷",
        "劳动争议": "劳动争议纠纷",
        "肖像权": "肖像权纠纷",
        "不正当竞争": "不正当竞争纠纷",
        "侵权": "侵权纠纷",
    }
    for kw, full_cause in cause_keywords.items():
        if kw in dir_name:
            info["cause"] = full_cause
            break
    
    return info

def scan_directory(dir_path: Path) -> List[dict]:
    """扫描目录，返回文件列表"""
    files = []
    for ext in ['*.pdf', '*.docx', '*.doc', '*.txt', '*.md']:
        for f in dir_path.rglob(ext):
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
            })
    return files

def extract_from_pdf(pdf_path: str) -> str:
    """从PDF提取文本（PyMuPDF + OCR）"""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
        doc.close()
        
        # 如果无文本，尝试OCR
        if not text.strip():
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                ocr_text = pytesseract.image_to_string(img, lang='chi_sim')
                text += ocr_text + "\n"
            doc.close()
    except Exception as e:
        print(f"    OCR错误: {e}")
    return text

def extract_from_docx(docx_path: str) -> str:
    """从DOCX提取文本"""
    try:
        from docx import Document
        doc = Document(docx_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""

def find_main_document(dir_path: Path) -> Optional[str]:
    """查找主要文档（起诉状/判决书等）"""
    priority_names = ['起诉', '判决', '民事', '裁定', '裁决']
    
    for f in dir_path.rglob('*'):
        if f.suffix.lower() in ['.pdf', '.docx', '.doc']:
            for kw in priority_names:
                if kw in f.name:
                    return str(f)
    
    # 如果没找到，返回第一个PDF
    for f in dir_path.rglob('*.pdf'):
        return str(f)
    
    return None

def parse_ocr_text(text: str) -> dict:
    """解析OCR文本提取信息"""
    info = {
        "plaintiff": "",
        "defendant": "",
        "cause": "",
    }
    
    lines = text.split('\n')
    
    # 提取原告
    for line in lines[:10]:
        if '原告' in line and ':' in line:
            match = re.search(r'[原告][：:]\s*(.+)', line)
            if match:
                info["plaintiff"] = match.group(1).strip()
                break
    
    # 提取被告
    for line in lines[:10]:
        if '被告' in line and ':' in line:
            match = re.search(r'[被告][：:]\s*(.+)', line)
            if match:
                info["defendant"] = match.group(1).strip()
                break
    
    # 提取案由
    for line in lines[:20]:
        if '案由' in line or '纠纷' in line or '侵权' in line:
            if '案由' in line:
                match = re.search(r'[案由][：:]\s*(.+)', line)
                if match:
                    info["cause"] = match.group(1).strip()
                    break
            elif '纠纷' in line:
                match = re.search(r'([^，。\n]+纠纷)', line)
                if match:
                    info["cause"] = match.group(1).strip()
                    break
    
    return info

def process_case(dir_path: Path, year: str) -> CaseInfo:
    """处理单个案例"""
    case = CaseInfo(
        year=year,
        dir_name=dir_path.name,
        dir_path=dir_path,
    )
    
    print(f"\n处理: {dir_path.name[:50]}")
    
    # 1. 从目录名解析基本信息
    basic_info = parse_directory_name(dir_path.name, year)
    case.case_number = basic_info["case_number"]
    case.plaintiff = basic_info["plaintiff"]
    case.defendant = basic_info["defendant"]
    case.cause = basic_info["cause"]
    case.court = basic_info["court"]
    case.case_name = basic_info["case_name"]
    
    # 2. 扫描文件
    files = scan_directory(dir_path)
    case.files = [f["name"] for f in files]
    print(f"  发现文件: {len(files)}个")
    
    # 3. 查找主要文档并提取内容
    main_doc = find_main_document(dir_path)
    if main_doc:
        print(f"  主要文档: {Path(main_doc).name[:30]}")
        if main_doc.endswith('.pdf'):
            case.ocr_text = extract_from_pdf(main_doc)
        elif main_doc.endswith(('.docx', '.doc')):
            case.ocr_text = extract_from_docx(main_doc)
        
        if case.ocr_text:
            print(f"  提取文本: {len(case.ocr_text)}字符")
            
            # 4. 从OCR文本补充信息
            ocr_info = parse_ocr_text(case.ocr_text)
            if not case.plaintiff and ocr_info["plaintiff"]:
                case.plaintiff = ocr_info["plaintiff"]
            if not case.defendant and ocr_info["defendant"]:
                case.defendant = ocr_info["defendant"]
            if not case.cause and ocr_info["cause"]:
                case.cause = ocr_info["cause"]
    else:
        case.issues.append("无主要文档")
    
    # 5. 评估质量
    case.issues = []
    if not case.case_number:
        case.issues.append("案号缺失")
    if not case.plaintiff:
        case.issues.append("原告缺失")
    if not case.defendant:
        case.issues.append("被告缺失")
    if not case.cause:
        case.issues.append("案由缺失")
    if not case.files:
        case.issues.append("无文件")
    
    # 质量等级
    issue_count = len(case.issues)
    if issue_count == 0:
        case.quality = "A"
    elif issue_count <= 2:
        case.quality = "B"
    else:
        case.quality = "C"
    
    case.status = "extracted" if issue_count < 3 else "pending"
    
    return case

def save_to_database(case: CaseInfo):
    """保存到数据库"""
    from src import database as db
    
    # 检查是否已存在
    existing = db.search_cases(case.case_number) if case.case_number else []
    if existing:
        for e in existing:
            if e.get('case_number') == case.case_number:
                print(f"  ⚠️ 案号已存在，跳过")
                return None
    
    # 创建案件
    case_id = db.create_case(
        case_name=case.case_name[:200],
        case_number=case.case_number,
        plaintiff=case.plaintiff,
        defendant=case.defendant,
        cause=case.cause,
        court=case.court,
        source_path=str(case.dir_path),
        source_files=", ".join(case.files[:10]),
        year=int(case.year) if case.year.isdigit() else None,
        status=case.status,
    )
    
    print(f"  ✅ 入库成功: {case_id[:20]}...")
    return case_id

def main():
    """主函数"""
    print("=" * 70)
    print("案例完整录入测试")
    print("=" * 70)
    
    all_cases = []
    stats = {"A": 0, "B": 0, "C": 0, "failed": 0}
    
    for year, base_dir in BASE_DIRS.items():
        print(f"\n\n{'=' * 70}")
        print(f"处理 {year} 年度")
        print(f"{'=' * 70}")
        
        base_path = Path(base_dir)
        dirs = [d for d in base_path.iterdir() if d.is_dir()]
        dirs.sort()
        
        print(f"共 {len(dirs)} 个目录")
        
        for i, dir_path in enumerate(dirs, 1):
            print(f"\n[{i}/{len(dirs)}]", end="")
            
            try:
                case = process_case(dir_path, year)
                all_cases.append(case)
                
                # 保存到数据库
                case_id = save_to_database(case)
                if case_id:
                    case.case_id = case_id
                
                stats[case.quality] += 1
                
                # 打印质量
                quality_icon = {"A": "✅", "B": "⚠️", "C": "🔶"}[case.quality]
                print(f" {quality_icon} {case.quality}级", end="")
                if case.issues:
                    print(f" - {', '.join(case.issues[:2])}", end="")
                print()
                
            except Exception as e:
                print(f" ❌ 失败: {e}")
                stats["failed"] += 1
    
    # 打印统计
    print("\n\n" + "=" * 70)
    print("统计报告")
    print("=" * 70)
    total = len(all_cases)
    print(f"总案例数: {total}")
    print(f"✅ A级(完整): {stats['A']} ({100*stats['A']/total:.1f}%)")
    print(f"⚠️ B级(良好): {stats['B']} ({100*stats['B']/total:.1f}%)")
    print(f"🔶 C级(一般): {stats['C']} ({100*stats['C']/total:.1f}%)")
    print(f"❌ 失败: {stats['failed']}")
    
    # 导出详细报告
    report_path = PROJECT_ROOT / "data" / "full_intake_report.json"
    report_path.parent.mkdir(exist_ok=True)
    
    report = []
    for case in all_cases:
        report.append({
            "年度": case.year,
            "目录名": case.dir_name,
            "案号": case.case_number,
            "原告": case.plaintiff,
            "被告": case.defendant,
            "案由": case.cause,
            "法院": case.court,
            "质量": case.quality,
            "状态": case.status,
            "问题": case.issues,
            "文件数": len(case.files),
            "文本长度": len(case.ocr_text),
        })
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细报告已保存: {report_path}")
    
    return all_cases

if __name__ == "__main__":
    main()
