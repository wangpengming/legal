#!/usr/bin/env python3
"""
增强版案例录入脚本
完善扫描和识别能力，提取完整产物
"""
import sys
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import re
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
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

# 简称映射
COMPANY_MAPPING = {
    "广州繁星": "广州繁星互娱信息科技有限公司",
    "广州立峰": "广州立峰音乐有限公司",
    "深圳启韵": "深圳启韵文化传播有限公司",
    "北京潮石": "北京潮石音乐科技有限公司",
    "纽凯": "纽凯文化传播（杭州）有限公司",
    "华声时代": "华声时代文化传播有限公司",
    "太阳红": "太阳红文化传媒",
    "四季唱片": "香港四季唱片有限公司",
    "中国音像": "中国音像著作权集体管理协会",
    "音集协": "中国音像著作权集体管理协会",
    "腾讯音乐": "腾讯音乐娱乐（珠海）有限公司",
    "TME": "腾讯音乐娱乐（珠海）有限公司",
    "雷石": "北京雷石天地网络技术有限公司",
    "雷客": "北京雷客天地科技有限公司",
    "歌尔": "歌尔股份有限公司",
}

COURT_MAPPING = {
    "北互": "北京互联网法院",
    "广州互法院": "广州互联网法院",
    "深圳互法院": "深圳前海合作区人民法院",
    "知产法院": "北京知识产权法院",
    "山东高院": "山东省高级人民法院",
    "广东高院": "广东省高级人民法院",
    "北京高院": "北京市高级人民法院",
}

CAUSE_MAPPING = {
    "信网权": "侵害作品信息网络传播权纠纷",
    "信息网络传播权": "侵害作品信息网络传播权纠纷",
    "著作权": "著作权权属、侵权纠纷",
    "录音录像": "著作权权属、侵权纠纷",
    "放映权": "著作权权属、侵权纠纷",
}

def normalize_company(name: str) -> str:
    """标准化公司名称"""
    if not name:
        return ""
    name = name.strip()
    for short, full in COMPANY_MAPPING.items():
        if short in name:
            return full
    return name

def normalize_court(name: str) -> str:
    """标准化法院名称"""
    if not name:
        return ""
    name = name.strip()
    for short, full in COURT_MAPPING.items():
        if short in name:
            return full
    return name

def normalize_cause(name: str) -> str:
    """标准化案由"""
    if not name:
        return ""
    name = name.strip()
    for short, full in CAUSE_MAPPING.items():
        if short in name:
            return full
    return name

def parse_directory_name(dir_name: str) -> dict:
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
    patterns = [
        r'[\（\(](\d{4})[\）\)][^\(（]*?[民行刑][^\)）]*?[\d、号]+号?',
        r'(\d{6})[\-‐](?:(\d{4})[^_\-]*?_)?[^\-‐]*?_?([^\-‐]+)诉',
        r'[\（\(](\d{4})[\）\)].*?[\d]+号',
    ]
    for p in patterns:
        m = re.search(p, dir_name)
        if m:
            info["case_number"] = m.group(0)
            break
    
    # 提取原告
    m = re.search(r'^[\d\-‐]*?([^\-‐]+?)\s*(?:诉|vs|VS)', dir_name)
    if m:
        plaintiff = m.group(1).strip()
        # 清理常见前缀
        plaintiff = re.sub(r'^[^\w\u4e00-\u9fa5]+', '', plaintiff)
        info["plaintiff"] = normalize_company(plaintiff)
    
    # 提取被告
    if '诉' in dir_name:
        parts = re.split(r'\s*诉\s*', dir_name)
        if len(parts) >= 2:
            defendant_part = parts[1]
            # 取第一个顿号/逗号前的部分
            defendant = re.split(r'[、，,]', defendant_part)[0].strip()
            # 清理常见后缀
            defendant = re.sub(r'[\-‐].*$', '', defendant)
            defendant = normalize_company(defendant)
            # 排除非公司名
            if defendant and len(defendant) > 2:
                info["defendant"] = defendant
    
    # 提取法院
    court_patterns = [
        r'([^\-‐]*?(?:人民法院|法院|仲裁委员会)[^\-‐]*)',
        r'([^\-‐]*?互[联网]*?法院[^\-‐]*)',
    ]
    for p in court_patterns:
        m = re.search(p, dir_name)
        if m:
            info["court"] = normalize_court(m.group(1))
            break
    
    # 提取案由
    cause_keywords = {
        "信网权": "侵害作品信息网络传播权纠纷",
        "信息网络传播权": "侵害作品信息网络传播权纠纷",
        "著作权侵权": "著作权权属、侵权纠纷",
        "著作权纠纷": "著作权权属、侵权纠纷",
        "著作权": "著作权权属、侵权纠纷",
        "录音录像制作者权": "著作权权属、侵权纠纷",
        "放映权": "著作权权属、侵权纠纷",
        "合同纠纷": "合同纠纷",
        "劳动争议": "劳动争议纠纷",
        "肖像权": "肖像权纠纷",
        "不正当竞争": "不正当竞争纠纷",
    }
    for kw, cause in cause_keywords.items():
        if kw in dir_name:
            info["cause"] = cause
            break
    
    return info

def extract_text_from_pdf(pdf_path: str, use_ocr: bool = True) -> str:
    """从PDF提取文本"""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            t = page.get_text()
            if t.strip():
                text += t + "\n"
        doc.close()
        
        if not text.strip() and use_ocr:
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                t = pytesseract.image_to_string(img, lang='chi_sim')
                text += t + "\n"
            doc.close()
    except Exception as e:
        pass
    return text

def extract_text_from_docx(docx_path: str) -> str:
    """从DOCX提取文本"""
    try:
        from docx import Document
        doc = Document(docx_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except:
        return ""

def find_main_document(dir_path: Path) -> Optional[dict]:
    """查找主要文档"""
    priority_kws = ['起诉', '判决', '民事', '裁定', '裁决', '申请书']
    skip_kws = ['营业执照', '身份证', '授权委托', '劳动合同', '收据', '发票']
    
    for f in dir_path.rglob('*'):
        if f.suffix.lower() not in ['.pdf', '.docx', '.doc']:
            continue
        
        # 跳过非主要文档
        is_main = False
        for kw in priority_kws:
            if kw in f.name:
                is_main = True
                break
        if not is_main:
            continue
        
        for kw in skip_kws:
            if kw in f.name:
                is_main = False
                break
        if not is_main:
            continue
        
        return {"path": str(f), "name": f.name, "type": f.suffix}
    
    return None

def parse_document_text(text: str) -> dict:
    """解析文档文本提取信息"""
    info = {
        "plaintiff": "",
        "defendant": "",
        "cause": "",
        "court": "",
    }
    
    if not text:
        return info
    
    lines = text.split('\n')
    
    # 提取原告
    for line in lines[:20]:
        m = re.search(r'原\s*告\s*[:：]\s*(.+)', line)
        if m:
            info["plaintiff"] = normalize_company(m.group(1).strip())
            break
    
    # 提取被告
    for line in lines[:30]:
        m = re.search(r'被\s*告\s*[:：]\s*(.+)', line)
        if m:
            info["defendant"] = normalize_company(m.group(1).strip())
            break
    
    # 提取案由
    for line in lines[:50]:
        m = re.search(r'案\s*由\s*[:：]\s*(.+)', line)
        if m:
            info["cause"] = normalize_cause(m.group(1).strip())
            break
    
    # 提取法院
    for line in lines[:10]:
        for kw in ['人民法院', '法院', '仲裁委员会']:
            if kw in line:
                info["court"] = normalize_court(line.strip())
                break
        if info["court"]:
            break
    
    return info

def process_case(dir_path: Path, year: str) -> dict:
    """处理单个案例"""
    result = {
        "year": year,
        "dir_name": dir_path.name,
        "dir_path": str(dir_path),
        "case_number": "",
        "plaintiff": "",
        "defendant": "",
        "cause": "",
        "court": "",
        "case_name": dir_path.name,
        "file_count": 0,
        "text_length": 0,
        "quality": "C",
        "issues": [],
    }
    
    # 1. 从目录名解析
    dir_info = parse_directory_name(dir_path.name)
    result.update({k: v for k, v in dir_info.items() if v})
    
    # 2. 扫描文件
    files = []
    for ext in ['*.pdf', '*.docx', '*.doc', '*.txt']:
        files.extend(list(dir_path.rglob(ext)))
    result["file_count"] = len(files)
    
    # 3. 查找主要文档并提取
    main_doc = find_main_document(dir_path)
    if main_doc:
        if main_doc["type"] == ".pdf":
            text = extract_text_from_pdf(main_doc["path"], use_ocr=True)
        else:
            text = extract_text_from_docx(main_doc["path"])
        
        result["text_length"] = len(text)
        
        if text:
            doc_info = parse_document_text(text)
            # 补充缺失信息
            if not result["plaintiff"] and doc_info["plaintiff"]:
                result["plaintiff"] = doc_info["plaintiff"]
            if not result["defendant"] and doc_info["defendant"]:
                result["defendant"] = doc_info["defendant"]
            if not result["cause"] and doc_info["cause"]:
                result["cause"] = doc_info["cause"]
            if not result["court"] and doc_info["court"]:
                result["court"] = doc_info["court"]
    
    # 4. 评估质量
    if not result["case_number"]:
        result["issues"].append("案号缺失")
    if not result["plaintiff"]:
        result["issues"].append("原告缺失")
    if not result["defendant"]:
        result["issues"].append("被告缺失")
    if not result["cause"]:
        result["issues"].append("案由缺失")
    
    issue_count = len(result["issues"])
    if issue_count == 0:
        result["quality"] = "A"
    elif issue_count <= 2:
        result["quality"] = "B"
    else:
        result["quality"] = "C"
    
    return result

def save_to_db(case_info: dict) -> str:
    """保存到数据库"""
    from src import database as db
    
    # 检查是否已存在
    if case_info.get("case_number"):
        existing = db.search_cases(case_info["case_number"])
        for e in existing:
            if e.get("case_number") == case_info["case_number"]:
                return f"已存在: {e['id'][:20]}"
    
    case_id = db.create_case(
        case_name=case_info.get("case_name", "")[:200],
        case_number=case_info.get("case_number", ""),
        plaintiff=case_info.get("plaintiff", ""),
        defendant=case_info.get("defendant", ""),
        cause=case_info.get("cause", ""),
        court=case_info.get("court", ""),
        source_path=case_info.get("dir_path", ""),
        year=int(case_info.get("year", 2024)) if case_info.get("year", "").isdigit() else None,
        status="pending",
    )
    
    return case_id

def main():
    print("=" * 70)
    print("案例完整录入 - 增强版")
    print("=" * 70)
    
    all_results = []
    stats = {"A": 0, "B": 0, "C": 0, "skipped": 0}
    
    for year, base_dir in BASE_DIRS.items():
        print(f"\n\n{'=' * 70}")
        print(f"处理 {year} 年度")
        print(f"{'=' * 70}")
        
        base_path = Path(base_dir)
        dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])
        
        for i, dir_path in enumerate(dirs, 1):
            print(f"\n[{i}/{len(dirs)}] {dir_path.name[:50]}", end="", flush=True)
            
            try:
                result = process_case(dir_path, year)
                
                # 保存到数据库
                db_result = save_to_db(result)
                
                quality_icon = {"A": "✅", "B": "⚠️", "C": "🔶"}[result["quality"]]
                print(f" {quality_icon} {result['quality']}", end="")
                
                if result["issues"]:
                    print(f" - {', '.join(result['issues'][:2])}", end="")
                
                print(f" | 文件:{result['file_count']} 文本:{result['text_length']}", end="")
                
                stats[result["quality"]] += 1
                all_results.append(result)
                
            except Exception as e:
                print(f" ❌ {e}", end="")
                stats["skipped"] += 1
    
    # 统计
    print("\n\n" + "=" * 70)
    print("统计报告")
    print("=" * 70)
    total = len(all_results)
    print(f"总案例数: {total}")
    print(f"✅ A级(完整): {stats['A']} ({100*stats['A']/total:.1f}%)")
    print(f"⚠️ B级(良好): {stats['B']} ({100*stats['B']/total:.1f}%)")
    print(f"🔶 C级(一般): {stats['C']} ({100*stats['C']/total:.1f}%)")
    if stats['skipped']:
        print(f"❌ 跳过: {stats['skipped']}")
    
    # 保存报告
    report_path = PROJECT_ROOT / "data" / "intake_report_enhanced.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 报告: {report_path}")
    
    return all_results

if __name__ == "__main__":
    main()
