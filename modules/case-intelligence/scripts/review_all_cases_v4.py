#!/usr/bin/env python3
"""
批量审查脚本 v4 - 最终版（改进案由识别）
"""
import sys
import json
import re
from pathlib import Path

# 案例目录映射
CASE_DIRS = {
    "2024": "/Users/zhangyang/Desktop/往年案例/2024年度已结案",
    "2025": "/Users/zhangyang/Desktop/往年案例/2025年度已结案",
    "2026": "/Users/zhangyang/Desktop/往年案例/2026年度已结案",
}

# 原告映射表
PLAINTIFF_MAP = {
    "启韵": "深圳启韵文化传播有限公司",
    "立峰": "广州立峰音乐有限公司",
    "纽凯": "纽凯文化传播（杭州）有限公司",
    "宝生": "广州宝生无声文化传播有限公司",
    "繁星": "广州繁星音乐有限公司",
    "潮石": "北京潮石音乐科技有限公司",
    "腾讯/TME": "腾讯音乐娱乐科技（深圳）有限公司",
    "四季唱片": "香港四季唱片有限公司",
    "传世乐坊": "传世乐坊国际文化传媒（北京）有限公司",
    "新航道": "南京新航道语言培训有限公司",
    "太阳红": "太阳红文化传媒",
    "音集协": "中国音像著作权集体管理协会",
    "广州繁星": "广州繁星音乐有限公司",
    "深圳启韵": "深圳启韵文化传播有限公司",
    "广州立峰": "广州立峰音乐有限公司",
    "华声时代": "华声时代文化传播有限公司",
    "浙江广播电视": "浙江广播电视集团",
}

# 被告映射表
DEFENDANT_MAP = {
    "雷石": "北京雷石天地网络技术有限公司",
    "雷客": "北京雷客天地科技有限公司",
    "金麦客": "成都金麦客科技有限公司",
    "理想": "理想汽车",
    "埃安": "广汽埃安新能源汽车有限公司",
    "特斯拉": "特斯拉汽车（北京）有限公司",
    "移动": "中国移动通信集团有限公司",
    "电信": "中国电信集团有限公司",
    "联通": "中国联合网络通信集团有限公司",
    "当贝": "杭州当贝网络科技有限公司",
    "第九城市": "上海第九城市信息技术有限公司",
    "超卓": "超卓公司",
    "比亚迪": "比亚迪股份有限公司",
    "阑途": "阑途公司",
    "上海浦连": "上海浦连汽车租赁公司",
    "厦门面声源": "厦门面声源公司",
    "歌乐娱乐": "歌乐娱乐公司",
}

# 案由关键词（按优先级排列）
CAUSE_KEYWORDS = [
    ("信息网络传播权", "信息网络传播权纠纷"),
    ("著作权权属", "著作权权属纠纷"),
    ("著作权侵权", "著作权侵权纠纷"),
    ("著作权", "著作权纠纷"),
    ("合同纠纷", "合同纠纷"),
    ("劳动争议", "劳动争议纠纷"),
    ("肖像权", "肖像权纠纷"),
    ("不正当竞争", "不正当竞争纠纷"),
    ("执行异议之诉", "执行异议之诉"),
    ("执行异议", "执行异议之诉"),
    ("侵权纠纷", "侵权纠纷"),
    ("侵权", "侵权纠纷"),
    ("民诉", "民事诉讼"),
    ("民终", "民事终审"),
    ("劳动", "劳动争议"),
    ("仲裁", "仲裁"),
    ("劳人仲", "劳动人事争议仲裁"),
    ("催款", "催款纠纷"),
    ("案件", "纠纷"),
    ("纠纷", "纠纷"),
]

# 法院映射表
COURT_MAP = [
    ("北京互联网法院", "北互"),
    ("北京互联网法院", "京0491"),
    ("深圳市宝安区人民法院", "深圳宝安"),
    ("深圳市福田区人民法院", "深圳福田"),
    ("广州市天河区人民法院", "广州天河"),
    ("广州市白云区人民法院", "广州白云"),
    ("天津市和平区人民法院", "天津和平"),
    ("上海浦东新区人民法院", "上海浦东"),
    ("北京知识产权法院", "北知"),
    ("北京市朝阳区人民法院", "京朝"),
    ("北京", "京"),
    ("上海", "沪"),
    ("天津", "津"),
    ("广东", "粤"),
    ("四川", "川"),
    ("山东", "鲁"),
    ("河南", "豫"),
    ("山西", "晋"),
    ("海南", "琼"),
    ("江苏", "苏"),
    ("内蒙古", "内蒙"),
]

def extract_case_number(name: str) -> str:
    """从目录名提取案号"""
    patterns = [
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 1),
        (r'\((\d{4})\)[\)]?([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 2),
        (r'（(\d{4})\)([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 3),
        (r'\((\d{4})\)([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 4),
        (r'^(\d{4})-([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 5),
        (r'^(\d{4})([\u4e00-\u9fa5]{2,4}\d+?民初[\d、至号\s]+号)', 6),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民终[\d、至号\s]+号)', 7),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民诉[\d、至号\s]+号)', 8),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?仲[\w\d\u4e00-\u9fa5、至号\s]+号)', 9),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?劳人仲[\w\d\u4e00-\u9fa5、至号\s]+号)', 10),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?立[\d、至号\s]+号)', 11),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?执[\w\d\u4e00-\u9fa5、至号\s]+号)', 12),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民申[\d、至号\s]+号)', 13),
    ]
    
    for pattern, priority in patterns:
        match = re.search(pattern, name)
        if match:
            return f"({match.group(1)}){match.group(2).strip()}"
    return ""

def extract_cause(name: str) -> str:
    """从目录名提取案由"""
    for keyword, cause in CAUSE_KEYWORDS:
        if keyword in name:
            return cause
    return ""

def parse_dir_name(dir_name: str) -> dict:
    """从目录名解析案件信息"""
    info = {
        "case_number": extract_case_number(dir_name),
        "plaintiff": "",
        "defendant": "",
        "court": "",
        "cause": extract_cause(dir_name),
        "year": None,
    }
    
    # 提取年份
    date_match = re.match(r"^(\d{2})(\d{2})(\d{2})-", dir_name)
    if date_match:
        info["year"] = f"20{date_match.group(1)}"
    
    # 提取原告
    for short, full in PLAINTIFF_MAP.items():
        if short in dir_name:
            info["plaintiff"] = full
            break
    
    # 提取被告
    defendants = []
    for short, full in DEFENDANT_MAP.items():
        if short in dir_name:
            defendants.append(full)
    if defendants:
        info["defendant"] = "、".join(list(dict.fromkeys(defendants)))
    
    # 提取法院
    for full, short in COURT_MAP:
        if short in dir_name:
            info["court"] = full
            break
    
    return info

def assess_quality(info: dict) -> tuple[str, list]:
    """评估提取质量"""
    issues = []
    score = "A"
    
    if not info.get("case_number"):
        issues.append("案号缺失")
        score = "B" if score == "A" else score
    if not info.get("plaintiff"):
        issues.append("原告缺失")
        score = "C" if score in ["A", "B"] else score
    if not info.get("defendant"):
        issues.append("被告缺失")
        score = "C" if score in ["A", "B"] else score
    if not info.get("court"):
        issues.append("法院缺失")
        score = "B" if score == "A" else score
    if not info.get("cause"):
        issues.append("案由缺失")
        score = "C" if score in ["A", "B"] else score
    
    return score, issues

def main():
    """主函数"""
    all_results = []
    total = 0
    
    for year, base_dir in CASE_DIRS.items():
        base_path = Path(base_dir)
        if not base_path.exists():
            continue
        
        dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])
        print(f"\n📂 {year}年度 - {len(dirs)} 个")
        
        for case_dir in dirs:
            total += 1
            dir_name = case_dir.name
            
            is_non_case = any(kw in dir_name for kw in [
                "说明文件", "核实", "律师函", "音集协-鼎盛", "音集协-FHY", 
                "中音文化", "回复函", "音集协-LYG", "协助执行"
            ])
            
            info = parse_dir_name(dir_name)
            quality, issues = assess_quality(info)
            
            result = {
                "序号": total,
                "年度": year,
                "目录名": dir_name,
                "案号": info["case_number"],
                "原告": info["plaintiff"],
                "被告": info["defendant"],
                "法院": info["court"],
                "案由": info["cause"],
                "质量": quality,
                "问题": issues,
                "是否案件": "否" if is_non_case else "是",
            }
            all_results.append(result)
            
            quality_icon = {"A": "✅", "B": "⚠️", "C": "🔶", "D": "❌"}[quality]
            is_case_icon = "📋" if not is_non_case else "📄"
            print(f"[{total:02d}] {is_case_icon}{quality_icon} {dir_name[:35]}...")
    
    # 统计
    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    case_count = sum(1 for r in all_results if r["是否案件"] == "是")
    non_case_count = sum(1 for r in all_results if r["是否案件"] == "否")
    
    for r in all_results:
        quality_counts[r["质量"]] += 1
    
    print(f"\n\n{'='*60}")
    print(f"📊 共 {total} 个目录 | 正式案件 {case_count} 个")
    print('='*60)
    print(f"✅ A级: {quality_counts['A']} | ⚠️ B级: {quality_counts['B']} | 🔶 C级: {quality_counts['C']}")
    
    complete = quality_counts['A'] + quality_counts['B']
    print(f"\n📈 完整率: {complete}/{case_count} ({100*complete/case_count:.1f}%)")
    
    # 保存
    output_file = Path(__file__).parent / "review_results_v4.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存: {output_file}")

if __name__ == "__main__":
    main()
