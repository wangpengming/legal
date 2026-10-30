#!/usr/bin/env python3
"""
案例审查脚本
逐个审查已提取的案例，验证提取质量并记录问题
"""
import subprocess
import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class CaseReview:
    """案例审查结果"""
    dir_name: str
    case_path: str
    case_number: str
    plaintiff: str
    defendant: str
    court: str
    cause: str
    quality: str  # A/B/C/D
    issues: list
    notes: str

def extract_case(case_path: str) -> dict:
    """提取案例信息"""
    try:
        result = subprocess.run(
            [
                sys.executable, 
                "/Users/zhangyang/Desktop/code/legal/modules/case-intelligence/bin/extract.py",
                "scan", case_path,
                "--max-depth", "2",
                "--ai",
                "--engine", "basic"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output = result.stdout
        info = {
            "case_number": None,
            "plaintiff": None,
            "defendant": None,
            "court": None,
            "cause": None,
        }
        
        # 解析输出
        for line in output.split("\n"):
            if "**案号**:" in line:
                parts = line.split("**案号**:")
                if len(parts) > 1:
                    info["case_number"] = parts[1].strip()
            elif "原告:" in line and "公司" in line:
                parts = line.split("原告:")
                if len(parts) > 1:
                    info["plaintiff"] = parts[1].split("(")[0].strip()
            elif "被告:" in line and "公司" in line:
                parts = line.split("被告:")
                if len(parts) > 1:
                    info["defendant"] = parts[1].split("(")[0].strip()
            elif "**法院**:" in line:
                parts = line.split("**法院**:")
                if len(parts) > 1:
                    info["court"] = parts[1].strip()
            elif "**案由**:" in line:
                parts = line.split("**案由**:")
                if len(parts) > 1:
                    info["cause"] = parts[1].strip()
        
        return info
    except Exception as e:
        return {"error": str(e)}

def assess_quality(info: dict) -> tuple[str, list]:
    """评估提取质量"""
    issues = []
    score = "A"  # A=完整, B=良好, C=一般, D=差
    
    # 检查案号
    if not info.get("case_number") or "待补充" in str(info.get("case_number", "")):
        issues.append("案号缺失/待补充")
        score = "B" if score == "A" else score
    elif len(str(info.get("case_number", ""))) > 30:
        issues.append("案号可能含其他文字")
        score = "B" if score == "A" else score
    
    # 检查原告
    if not info.get("plaintiff") or "None" in str(info.get("plaintiff", "")):
        issues.append("原告缺失")
        score = "C" if score in ["A", "B"] else score
    
    # 检查被告
    if not info.get("defendant") or "None" in str(info.get("defendant", "")):
        issues.append("被告缺失")
        score = "C" if score in ["A", "B"] else score
    
    # 检查法院
    if not info.get("court") or "待补充" in str(info.get("court", "")):
        issues.append("法院缺失")
        score = "B" if score == "A" else score
    elif "东省" in str(info.get("court", "")) or "川省" in str(info.get("court", "")):
        issues.append("法院名称截断")
        score = "B" if score == "A" else score
    
    # 检查案由
    if not info.get("cause") or "待补充" in str(info.get("cause", "")):
        issues.append("案由缺失")
        score = "C" if score in ["A", "B"] else score
    
    return score, issues

def review_all_cases():
    """审查所有案例"""
    cases_2024 = [
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/(2024)鲁0481民初2332、2335、197号案-广州立峰诉雷石-WJY、FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/220427-劳动争议（刘杰-雷石）-LZP LSY WDN",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230203-（2022）晋民终508号-张璟、吕改萍诉雷石著作权权属侵权纠纷重审案-ZY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230320-京朝劳人仲字（2023）第14652号（崔天竺、雷石）-AY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230428-（2023）京0105民初50308号-赵丹丹诉雷石--LSY、HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/231204-（2023）豫0191民初26745号-郑州又一城诉雷石等执行异议之诉-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/231226-（2024）京0491民初682号-潮石vs雷石、理想等信网权-【车载】《无数》薛之谦9-北互-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240105-(2024)京0491民初1550-1555号-深圳启韵vs车载理想、雷石等信息网络传播权纠纷-北互-6案【车载】-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240111-广州宝生vs雷客信息网络传播权-北互-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240116-(2023)京0491民初23751号和23752号-TME诉雷石、特斯拉诉讼材料-WJY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240116-（2024）京0491民初2913号-腾讯（TME）诉雷石、理想诉讼材料-32件【车载】-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240122-（2024）京0491民初1152号-毕滢诉镭海肖像权纠纷-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240125-（2024）京0491民初3047、3048号-纽凯诉雷客、成都金麦客等信网权纠纷2案-北互-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240221-（2024）京0491民初2936号、（2024）京73民终2207号-纽凯文化诉特斯拉、雷石-WJY、FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240328-（2024）京仲案字第02193号-太阳红仲裁案件-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240428-（2024）津0319民初7847、7924、7925号-纽凯诉联通、天津金麦客、北京雷客3案-天津法院-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240507-2024京0491民初7776号-广州繁星诉雷石信息网络传播权纠纷-北互-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240517-（2024)京0491民初678号、679号、680号、681号-北京潮石VS雷石-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240522-（2024）京0491民初674号、675号、676号、677号-潮石诉雷石-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240522-（2024）京0491民初683号-北京潮石诉雷石、埃安-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240524-（2023）粤0111民诉18110号、18111号-立峰诉雷石-广州白云区法院-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240524-（2024）川0104民初9691号-启韵-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240531-（2024）内0402知民初156-173号-音集协诉雷石著作权纠纷【15案】-内蒙古赤峰红山区法院-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240605-（2024）粤0402民初10963号-立峰诉雷石、KTV-珠海法院-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240605-（2024）粤0402民初10964号-立峰诉雷石、KTV-珠海法院-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240611-（2024）京0491民初8617号、8618号-广州繁星诉雷石-北互-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240611-（2024）京0491民初8963号-广州繁星诉雷石-北互-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240617-（2024）粤1403民初1922号、1939号-四季唱片诉雷石等-梅州法院-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240626-（2024）沪0115民初55395号-深圳启韵诉雷石、上海第九城市、移动信网权纠纷-【iptv】-上海浦东-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240702-（2024）沪0115民初56069号-深圳启韵诉雷石、上海第九城市、移动-著作权纠纷-【iptv】-上海浦东-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240703-安雨琪枫核实-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240705-（2024）凉仲案字第16号四川吉佰汇-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240710-(2024)京0491民初10442号-潮石诉雷石、成都等信网权纠纷-【IPTV】-北互-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240725-（2024）川0104民初14030号-启韵诉雷石、超卓、电信-四川-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240725-（2024）川0104民初14222号-启韵诉雷石、超卓、电信-四川-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240909-深圳日博电子科技有限公司vs北京雷石等（第三人深圳如一探索科技）-执行异议之诉-深圳宝安区人民法院-HS",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241010-天津海柏说明文件-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241111-（2024）鲁0891民初4721号-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26497号-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26498号-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26499号-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/音集协-FHY",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/音集协-鼎盛",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/雷石-中音文化说明",
        "/Users/zhangyang/Desktop/往年案例/2024年度已结案/（2024）鲁0481民初2334号-立峰诉城郊缤纷、雷石-关联122号-FHY",
    ]
    
    results = []
    
    print(f"开始审查 {len(cases_2024)} 个2024年度案例...\n")
    
    for i, case_path in enumerate(cases_2024, 1):
        dir_name = Path(case_path).name
        print(f"[{i}/{len(cases_2024)}] 审查: {dir_name[:40]}...")
        
        info = extract_case(case_path)
        
        if "error" in info:
            print(f"  -> ❌ 错误: {info['error']}")
            continue
        
        quality, issues = assess_quality(info)
        
        result = {
            "dir_name": dir_name,
            "case_path": case_path,
            **info,
            "quality": quality,
            "issues": issues
        }
        results.append(result)
        
        quality_icon = {"A": "✅", "B": "⚠️", "C": "🔶", "D": "❌"}[quality]
        print(f"  -> {quality_icon} {quality}级 | 案号:{info.get('case_number', '缺失')[:25]}...")
        if issues:
            print(f"     问题: {', '.join(issues)}")
    
    # 统计
    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        quality_counts[r["quality"]] += 1
    
    print(f"\n{'='*60}")
    print(f"2024年度案例审查完成")
    print(f"  ✅ A级(完整): {quality_counts['A']} 个")
    print(f"  ⚠️ B级(良好): {quality_counts['B']} 个")
    print(f"  🔶 C级(一般): {quality_counts['C']} 个")
    print(f"  ❌ D级(差): {quality_counts['D']} 个")
    
    # 保存结果
    output_file = Path(__file__).parent.parent / "data" / "review_results_2024.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {output_file}")
    
    return results

if __name__ == "__main__":
    review_all_cases()
