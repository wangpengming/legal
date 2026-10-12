#!/usr/bin/env python3
"""
批量审查脚本 v3 - 最终版
逐个审查99个案例，验证提取质量
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

# 原告映射表（简称 -> 全称）
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

# 案由映射表
CAUSE_MAP = {
    "信网权": "信息网络传播权纠纷",
    "著作权": "著作权纠纷",
    "劳动争议": "劳动争议纠纷",
    "肖像权": "肖像权纠纷",
    "不正当竞争": "不正当竞争纠纷",
    "执行异议": "执行异议之诉纠纷",
    "合同纠纷": "合同纠纷",
    "催款": "催款纠纷",
    "侵权": "侵权纠纷",
    "权属": "权属纠纷",
}

# 法院映射表（按优先级排列）
COURT_MAP = [
    # 长匹配优先
    ("北京互联网法院", "北互"),
    ("深圳市宝安区人民法院", "深圳宝安"),
    ("深圳市福田区人民法院", "深圳福田"),
    ("深圳市南山区人民法院", "深圳南山"),
    ("广州市天河区人民法院", "广州天河"),
    ("广州市白云区人民法院", "广州白云"),
    ("天津市和平区人民法院", "天津和平"),
    ("上海浦东新区人民法院", "上海浦东"),
    ("北京知识产权法院", "北知"),
    ("北京市朝阳区人民法院", "京朝"),
    ("北京市海淀区人民法院", "京海"),
    ("北京市高级人民法院", "北京市高院"),
    ("广东省高级人民法院", "广东高院"),
    ("江苏省盐城市人民法院", "盐城"),
    ("四川省成都市", "成都"),
    # 一字简称（放在后面）
    ("北京互联网法院", "京0491"),
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
]

def extract_case_number(name: str) -> str:
    """从目录名提取案号"""
    patterns = [
        # 民初格式
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 1),
        (r'\((\d{4})\)[\)]?([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 2),
        (r'（(\d{4})\)([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 3),
        (r'\((\d{4})\)([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 4),
        (r'^(\d{4})-([\w\d\u4e00-\u9fa5]{1,25}?民初[\d、至号\s]+号)', 5),
        (r'^(\d{4})([\u4e00-\u9fa5]{2,4}\d+?民初[\d、至号\s]+号)', 6),
        # 民终格式
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民终[\d、至号\s]+号)', 7),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民诉[\d、至号\s]+号)', 8),
        # 仲裁格式
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?仲[\w\d\u4e00-\u9fa5、至号\s]+号)', 9),
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?劳人仲[\w\d\u4e00-\u9fa5、至号\s]+号)', 10),
        # 立格式
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?立[\d、至号\s]+号)', 11),
        # 执格式
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?执[\w\d\u4e00-\u9fa5、至号\s]+号)', 12),
        # 民申格式（再审）
        (r'（(\d{4})）([\w\d\u4e00-\u9fa5]{1,25}?民申[\d、至号\s]+号)', 13),
    ]
    
    for pattern, priority in patterns:
        match = re.search(pattern, name)
        if match:
            year = match.group(1)
            rest = match.group(2).strip()
            return f"({year}){rest}"
    
    return ""

def parse_dir_name(dir_name: str) -> dict:
    """从目录名解析案件信息"""
    info = {
        "case_number": extract_case_number(dir_name),
        "plaintiff": "",
        "defendant": "",
        "court": "",
        "cause": "",
        "year": None,
    }
    
    # 提取日期前缀判断年份
    date_match = re.match(r"^(\d{2})(\d{2})(\d{2})-", dir_name)
    if date_match:
        year_short = date_match.group(1)
        info["year"] = f"20{year_short}"
    
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
    
    # 提取法院 - 长匹配优先
    for full, short in COURT_MAP:
        if short in dir_name:
            info["court"] = full
            break
    
    # 提取案由
    for short, full in CAUSE_MAP.items():
        if short in dir_name:
            info["cause"] = full
            break
    
    # 从目录名提取案由关键词
    if not info["cause"]:
        if "纠纷" in dir_name:
            info["cause"] = "侵权纠纷"
        elif "案件" in dir_name:
            info["cause"] = "纠纷"
    
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
        print(f"\n{'='*70}")
        print(f"📂 {year}年度 - {len(dirs)} 个")
        print('='*70)
        
        for case_dir in dirs:
            total += 1
            dir_name = case_dir.name
            
            # 非案件目录
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
            
            print(f"[{total:02d}] {is_case_icon}{quality_icon} {dir_name[:40]}...")
    
    # 统计
    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    case_count = sum(1 for r in all_results if r["是否案件"] == "是")
    non_case_count = sum(1 for r in all_results if r["是否案件"] == "否")
    
    for r in all_results:
        quality_counts[r["质量"]] += 1
    
    print(f"\n\n{'='*70}")
    print(f"📊 审查完成 - 共 {total} 个目录")
    print('='*70)
    print(f"\n📋 质量分布:")
    print(f"  ✅ A级: {quality_counts['A']} 个")
    print(f"  ⚠️ B级: {quality_counts['B']} 个")
    print(f"  🔶 C级: {quality_counts['C']} 个")
    print(f"\n📁 分类: 正式案件 {case_count} 个, 非案件 {non_case_count} 个")
    
    complete = quality_counts['A'] + quality_counts['B']
    print(f"\n📈 正式案件完整率: {complete}/{case_count} ({100*complete/case_count:.1f}%)")
    
    # 保存
    output_file = Path(__file__).parent / "review_results_final.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存: {output_file}")

if __name__ == "__main__":
    main()
