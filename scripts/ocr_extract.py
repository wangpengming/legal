#!/usr/bin/env python3
"""
OCR批量提取脚本
从PDF中提取缺失的案号、案由、原告、被告等信息
"""
import sys
import json
import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

@dataclass
class OCRResult:
    """OCR结果"""
    court: str
    case_number: str
    cause: str
    plaintiff: str
    defendant: str
    full_text: str

def extract_from_pdf(pdf_path: str) -> Optional[OCRResult]:
    """从PDF提取信息"""
    try:
        doc = fitz.open(pdf_path)
        
        # 提取文本
        text = ""
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
        
        # 如果无文本，尝试OCR第一页
        if not text.strip():
            page = doc[0]
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang='chi_sim')
        
        doc.close()
        
        if not text.strip():
            return None
        
        return parse_ocr_text(text)
        
    except Exception as e:
        print(f"  OCR错误: {e}")
        return None

def parse_ocr_text(text: str) -> OCRResult:
    """解析OCR文本"""
    result = OCRResult(
        court="",
        case_number="",
        cause="",
        plaintiff="",
        defendant="",
        full_text=text
    )
    
    lines = text.split("\n")
    
    # 提取法院（常见关键词）
    court_keywords = ["人民法院", "法院", "仲裁委员会"]
    for line in lines[:5]:  # 前几行通常是抬头
        for kw in court_keywords:
            if kw in line:
                result.court = line.strip()
                break
        if result.court:
            break
    
    # 提取案号（常见格式）
    case_patterns = [
        r'\((\d{4})\).*?民[\u4e00-\u9fa5]+?[\d、号\s]+号',
        r'（(\d{4})）.?.?民[\u4e00-\u9fa5]+?[\d、号\s]+号',
        r'(\d{4}).*?[\u4e00-\u9fa5]+?[\d、号\s]+号',
    ]
    for line in lines:
        for pattern in case_patterns:
            match = re.search(pattern, line)
            if match:
                result.case_number = match.group(0).strip()
                break
        if result.case_number:
            break
    
    # 提取案由（常见关键词）
    cause_keywords = ["纠纷", "侵权", "著作权", "合同", "劳动", "肖像", "竞争", "违约", "婚姻"]
    for line in lines:
        for kw in cause_keywords:
            if kw in line:
                # 找到包含案由的整行
                result.cause = line.strip()
                break
        if result.cause:
            break
    
    # 提取原告（常见关键词）
    plaintiff_keywords = ["原告", "上诉人", "申请人", "起诉人"]
    for line in lines:
        for kw in plaintiff_keywords:
            if kw in line:
                result.plaintiff = line.strip()
                break
        if result.plaintiff:
            break
    
    # 提取被告（常见关键词）
    defendant_keywords = ["被告", "被上诉人", "被申请人", "被起诉人"]
    for line in lines:
        for kw in defendant_keywords:
            if kw in line:
                result.defendant = line.strip()
                break
        if result.defendant:
            break
    
    return result

def find_pdf(case_dir: Path) -> Optional[str]:
    """查找案例目录中的PDF文件"""
    # 优先查找程序性事项中的传票
    procedural = case_dir / "程序性事项"
    if procedural.exists():
        for f in procedural.glob("*.pdf"):
            if "传票" in f.name or "立案" in f.name:
                return str(f)
        # 如果没有传票，返回第一个PDF
        pdfs = list(procedural.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])
    
    # 查找实体性事项
    substantive = case_dir / "实体性事项"
    if substantive.exists():
        pdfs = list(substantive.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])
    
    # 递归查找
    for f in case_dir.rglob("*.pdf"):
        return str(f)
    
    return None

def process_case(case_info: dict, base_dir: str) -> dict:
    """处理单个案例"""
    case_dir = Path(base_dir) / case_info["目录名"]
    
    if not case_dir.exists():
        return case_info
    
    pdf_path = find_pdf(case_dir)
    
    if not pdf_path:
        return case_info
    
    print(f"  正在处理: {case_info['目录名'][:40]}...")
    
    result = extract_from_pdf(pdf_path)
    
    if result:
        # 补充缺失信息
        if not case_info.get("案号") and result.case_number:
            case_info["案号"] = result.case_number
            case_info["问题"] = [p for p in case_info.get("问题", []) if p != "案号缺失"]
        
        if not case_info.get("法院") and result.court:
            case_info["法院"] = result.court
            case_info["问题"] = [p for p in case_info.get("问题", []) if p != "法院缺失"]
        
        if not case_info.get("案由") and result.cause:
            case_info["案由"] = result.cause
            case_info["问题"] = [p for p in case_info.get("问题", []) if p != "案由缺失"]
        
        if not case_info.get("原告") and result.plaintiff:
            case_info["原告"] = result.plaintiff
            case_info["问题"] = [p for p in case_info.get("问题", []) if p != "原告缺失"]
        
        if not case_info.get("被告") and result.defendant:
            case_info["被告"] = result.defendant
            case_info["问题"] = [p for p in case_info.get("问题", []) if p != "被告缺失"]
        
        # 更新质量等级
        issue_count = len(case_info.get("问题", []))
        if issue_count == 0:
            case_info["质量"] = "A"
        elif issue_count <= 2:
            case_info["质量"] = "B"
        else:
            case_info["质量"] = "C"
    
    return case_info

def main():
    """主函数"""
    # 读取审查结果
    results_file = Path(__file__).parent / "review_results_v4.json"
    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    # 筛选C级案例
    c_cases = [r for r in results if r["质量"] == "C" and r["是否案件"] == "是"]
    
    print(f"共有 {len(c_cases)} 个C级案例需要OCR提取")
    print("=" * 60)
    
    # 按年度分组处理
    for year in ["2024", "2025", "2026"]:
        year_cases = [r for r in c_cases if r["年度"] == year]
        if not year_cases:
            continue
        
        base_dir = f"/Users/zhangyang/Desktop/往年案例/{year}年度已结案"
        
        print(f"\n📂 {year}年度 ({len(year_cases)} 个)")
        print("-" * 40)
        
        for case in year_cases:
            process_case(case, base_dir)
    
    # 重新统计
    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        quality_counts[r["质量"]] += 1
    
    complete = quality_counts['A'] + quality_counts['B']
    case_count = sum(1 for r in results if r["是否案件"] == "是")
    
    print(f"\n\n{'='*60}")
    print(f"📊 OCR处理后统计")
    print('='*60)
    print(f"✅ A级: {quality_counts['A']} | ⚠️ B级: {quality_counts['B']} | 🔶 C级: {quality_counts['C']}")
    print(f"\n📈 完整率: {complete}/{case_count} ({100*complete/case_count:.1f}%)")
    
    # 保存结果
    output_file = Path(__file__).parent / "review_results_with_ocr.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存: {output_file}")

if __name__ == "__main__":
    main()
