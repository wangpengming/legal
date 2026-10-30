#!/usr/bin/env python3
"""
批量审查脚本
逐个审查99个案例，验证提取质量
"""
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# 案例目录映射
CASE_DIRS = {
    "2024": "/Users/zhangyang/Desktop/往年案例/2024年度已结案",
    "2025": "/Users/zhangyang/Desktop/往年案例/2025年度已结案",
    "2026": "/Users/zhangyang/Desktop/往年案例/2026年度已结案",
}

# 映射表
COURT_MAP = {
    "北互": "北京互联网法院",
    "北知": "北京知识产权法院",
    "朝阳": "北京市朝阳区人民法院",
    "海淀": "北京市海淀区人民法院",
    "广州白云": "广州市白云区人民法院",
    "广州天河": "广州市天河区人民法院",
    "深圳福田": "深圳市福田区人民法院",
    "上海浦东": "上海浦东新区人民法院",
    "上海闵行": "上海市闵行区人民法院",
    "天津和平": "天津市和平区人民法院",
    "四川": "四川省",
    "内蒙古赤峰": "内蒙古自治区赤峰市",
    "珠海": "珠海市",
    "梅州": "梅州市",
    "成都": "成都市",
    "青岛": "青岛市",
    "三亚": "三亚市",
    "济南": "济南市",
}

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
}

DEFENDANT_MAP = {
    "雷石": "北京雷石天地网络技术有限公司",
    "雷客": "北京雷客天地科技有限公司",
    "金麦客": "成都金麦客科技有限公司",
    "理想": "理想汽车",
    "埃安": "广汽埃安",
    "特斯拉": "特斯拉",
    "移动": "中国移动",
    "电信": "中国电信",
    "联通": "中国联通",
    "当贝": "杭州当贝网络科技有限公司",
    "第九城市": "上海第九城市信息技术有限公司",
    "超卓": "超卓公司",
}

CAUSE_MAP = {
    "信网权": "信息网络传播权纠纷",
    "著作权": "著作权纠纷",
    "劳动争议": "劳动争议纠纷",
    "肖像权": "肖像权纠纷",
    "不正当竞争": "不正当竞争纠纷",
    "执行异议": "执行异议之诉",
}

def parse_dir_name(dir_name: str) -> dict:
    """从目录名解析案件信息"""
    info = {
        "case_number": None,
        "plaintiff": None,
        "defendant": None,
        "court": None,
        "cause": None,
        "year": None,
        "source": "目录名解析",
    }
    
    # 提取日期前缀判断年份
    date_match = re.match(r"^(\d{2})(\d{2})(\d{2})-", dir_name)
    if date_match:
        year_short = date_match.group(1)
        month = date_match.group(2)
        day = date_match.group(3)
        info["year"] = f"20{year_short}"
    
    # 提取案号
    case_num_match = re.search(r"20\d{2}[京粤沪津川鲁琼豫晋内蒙鄂\d]+[民知执仲调罚行]*[\d零一二三四五六七八九十]+[号\s]+", dir_name)
    if case_num_match:
        info["case_number"] = case_num_match.group(0).strip()
    else:
        # 尝试无括号格式
        case_num_match2 = re.search(r"\((\d{4})\)(.+?)(?=-[^\(]*$)", dir_name)
        if case_num_match2:
            info["case_number"] = f"({case_num_match2.group(1)}){case_num_match2.group(2)}"
    
    # 提取原告
    for short, full in PLAINTIFF_MAP.items():
        if short in dir_name:
            info["plaintiff"] = full
            break
    
    # 提取被告
    for short, full in DEFENDANT_MAP.items():
        if short in dir_name:
            if info.get("defendant"):
                info["defendant"] += f"、" if not info["defendant"].endswith("等") else ""
                info["defendant"] += full
            else:
                info["defendant"] = full
            break
    
    # 提取法院
    for short, full in COURT_MAP.items():
        if short in dir_name:
            info["court"] = full
            break
    
    # 提取案由
    for short, full in CAUSE_MAP.items():
        if short in dir_name:
            info["cause"] = full
            break
    
    # 如果没有被告但有"诉"字，尝试提取
    if not info["defendant"] and "诉" in dir_name:
        parts = dir_name.split("诉")
        if len(parts) > 1:
            defendant_part = parts[1].split("-")[0].split("、")[0]
            for short, full in DEFENDANT_MAP.items():
                if short in defendant_part:
                    info["defendant"] = full
                    break
    
    return info

def assess_quality(info: dict) -> tuple[str, list]:
    """评估提取质量"""
    issues = []
    score = "A"
    
    # 检查案号
    if not info.get("case_number") or "待补充" in str(info.get("case_number", "")):
        issues.append("案号缺失")
        score = "B" if score == "A" else score
    
    # 检查原告
    if not info.get("plaintiff") or "待补充" in str(info.get("plaintiff", "")):
        issues.append("原告缺失")
        score = "C" if score in ["A", "B"] else score
    
    # 检查被告
    if not info.get("defendant") or "待补充" in str(info.get("defendant", "")):
        issues.append("被告缺失")
        score = "C" if score in ["A", "B"] else score
    
    # 检查法院
    if not info.get("court") or "待补充" in str(info.get("court", "")):
        issues.append("法院缺失")
        score = "B" if score == "A" else score
    
    # 检查案由
    if not info.get("cause") or "待补充" in str(info.get("cause", "")):
        issues.append("案由缺失")
        score = "C" if score in ["A", "B"] else score
    
    return score, issues

def get_case_count(directory: Path) -> int:
    """获取目录下PDF文件数量"""
    if not directory.exists():
        return 0
    return len(list(directory.glob("*.pdf")))

def main():
    """主函数"""
    all_results = []
    total = 0
    
    for year, base_dir in CASE_DIRS.items():
        base_path = Path(base_dir)
        if not base_path.exists():
            print(f"❌ 目录不存在: {base_dir}")
            continue
        
        dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])
        print(f"\n{'='*70}")
        print(f"📂 {year}年度已结案 - 共 {len(dirs)} 个案例")
        print('='*70)
        
        for i, case_dir in enumerate(dirs, 1):
            total += 1
            dir_name = case_dir.name
            
            # 检查是否为非案件目录
            is_non_case = any(keyword in dir_name for keyword in [
                "说明文件", "核实", "律师函", "音集协-鼎盛", "音集协-FHY", "中音文化"
            ])
            
            info = parse_dir_name(dir_name)
            quality, issues = assess_quality(info)
            
            pdf_count = get_case_count(case_dir)
            
            result = {
                "序号": total,
                "年度": year,
                "目录名": dir_name,
                "案号": info.get("case_number", ""),
                "原告": info.get("plaintiff", ""),
                "被告": info.get("defendant", ""),
                "法院": info.get("court", ""),
                "案由": info.get("cause", ""),
                "PDF数": pdf_count,
                "质量": quality,
                "问题": issues,
                "是否案件": "是" if not is_non_case else "否",
            }
            all_results.append(result)
            
            quality_icon = {"A": "✅", "B": "⚠️", "C": "🔶", "D": "❌"}[quality]
            is_case_icon = "📋" if not is_non_case else "📄"
            
            print(f"\n[{total:02d}] {is_case_icon} {quality_icon} {quality}级 | {dir_name[:45]}...")
            print(f"      案号: {info.get('case_number', '❌缺失') or '❌缺失'}")
            print(f"      原告: {info.get('plaintiff', '❌缺失') or '❌缺失'}")
            print(f"      被告: {info.get('defendant', '❌缺失') or '❌缺失'}")
            print(f"      法院: {info.get('court', '⚠️未识别') or '⚠️未识别'}")
            print(f"      案由: {info.get('cause', '⚠️未识别') or '⚠️未识别'}")
            if is_non_case:
                print(f"      ⛔ 非正式案件目录")
            if issues:
                print(f"      ⚠️ 问题: {', '.join(issues)}")
    
    # 统计
    print(f"\n\n{'='*70}")
    print(f"📊 审查完成 - 共 {total} 个目录")
    print('='*70)
    
    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    case_count = 0
    non_case_count = 0
    
    for r in all_results:
        quality_counts[r["质量"]] += 1
        if r["是否案件"] == "是":
            case_count += 1
        else:
            non_case_count += 1
    
    print(f"\n📋 质量分布:")
    print(f"  ✅ A级(完整): {quality_counts['A']} 个")
    print(f"  ⚠️ B级(良好): {quality_counts['B']} 个")
    print(f"  🔶 C级(一般): {quality_counts['C']} 个")
    print(f"  ❌ D级(差):   {quality_counts['D']} 个")
    
    print(f"\n📁 目录分类:")
    print(f"  📋 正式案件: {case_count} 个")
    print(f"  📄 非案件目录: {non_case_count} 个")
    
    # 完整率计算（排除非案件目录）
    complete_count = quality_counts['A'] + quality_counts['B']
    partial_count = quality_counts['C']
    failed_count = quality_counts['D']
    
    print(f"\n📈 正式案件提取质量:")
    print(f"  ✅ 完整提取: {complete_count}/{case_count} ({100*complete_count/case_count:.1f}%)")
    print(f"  🔶 部分提取: {partial_count}/{case_count} ({100*partial_count/case_count:.1f}%)")
    print(f"  ❌ 提取失败: {failed_count}/{case_count} ({100*failed_count/case_count:.1f}%)")
    
    # 保存结果
    output_file = Path(__file__).parent / "review_results_all.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 详细结果已保存到: {output_file}")
    
    return all_results

if __name__ == "__main__":
    main()
