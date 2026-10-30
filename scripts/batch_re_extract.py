#!/usr/bin/env python3
"""
批量重提取脚本
对之前提取失败的案例进行重新提取，利用目录名解析增强功能
"""
import subprocess
import sys
from pathlib import Path

# 之前提取失败的案例目录
FAILED_CASES = [
    # 2024年度
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/220427-劳动争议（刘杰-雷石）-LZP LSY WDN",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230203-（2022）晋民终508号-张璟、吕改萍诉雷石著作权权属侵权纠纷重审案-ZY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230320-京朝劳人仲字（2023）第14652号（崔天竺、雷石）-AY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/230428-（2023）京0105民初50308号-赵丹丹诉雷石--LSY、HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240105-(2024)京0491民初1550-1555号-深圳启韵vs车载理想、雷石等信息网络传播权纠纷-北互-6案【车载】-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240111-广州宝生vs雷客信息网络传播权-北互-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240122-（2024）京0491民初1152号-毕滢诉镭海肖像权纠纷-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240125-（2024）京0491民初3047、3048号-纽凯诉雷客、成都金麦客等信网权纠纷2案-北互-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240221-（2024）京0491民初2936号、（2024）京73民终2207号-纽凯文化诉特斯拉、雷石-WJY、FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240328-（2024）京仲案字第02193号-太阳红仲裁案件-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240524-（2023）粤0111民诉18110号、18111号-立峰诉雷石-广州白云区法院-HS",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240524-（2024）川0104民初9691号-启韵-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240617-（2024）粤1403民初1922号、1939号-四季唱片诉雷石等-梅州法院-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240725-（2024）川0104民初14030号-启韵诉雷石、超卓、电信-四川-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/240725-（2024）川0104民初14222号-启韵诉雷石、超卓、电信-四川-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241010-天津海柏说明文件-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241111-（2024）鲁0891民初4721号-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26497号-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26498号-FHY",
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案/241202-（2024）琼0271民诉前调26499号-FHY",
    # 2025年度
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/230331-京仲劳人仲字（2023）第13150号-苗椿馀诉北京雷石天地-AY、FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/240223-(2024)京0491民初2947、2948号-传世乐坊诉雷石、理想、广汽埃安等2案-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241011-（2024）京0491民初15593号-南京新航道诉雷石-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241015-（2024）京0491民初15370号-南京新航道诉雷石-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241107-（2024）粤0192民初19136号-腾讯IPTV-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241119-（2024）粤0106立24988号-酷狗诉爱之尚、和音元视、雷石-不正当竞争纠纷-广州市天河区人民法院-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241206-(2024)京0491民初18729号-纽凯诉雷客、金麦客-北互-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241206-(2024)京0491民初19781号-纽凯诉雷客、金麦客-北互-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241206-(2024)京0491民初19782号-纽凯诉雷客、金麦客-北互-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241220-（2024）京0491民初19204号-传世乐坊诉雷石、埃安-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/241220-（2024）京0491民初19207号-传世乐坊诉雷石、理想-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/250113-（2025）鲁1311民初152号-广西唱作者诉宝丽悦尚歌厅、雷石-FHY",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/250114-（2025）京0105民初4504号-雷石vs王亮-劳动争议【一审】-朝阳法院-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/250318-（2025）川0193民初5570号-纽凯诉雷客、金麦客等信网权纠纷-四川自由贸易试验区-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/250403-（2025）川0193民初6641号-纽凯诉雷客、金麦客等信网权纠纷-四川自由贸易试验区-HS",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案/251029-纽凯诉金麦客、雷客、杭州当贝系列案件-四川自由贸易区-37件-HS",
    # 2026年度
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/240929-湖北星天雷石-催款【撤诉】-FHY、LYG",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/250411-【催款-执行终本】2024京0103民初31217号-雷石vs厦门面声源-HS",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/250904-纽凯诉雷客、金麦客、杭州当贝著作权纠纷-13392号-四川自由贸易试验区人民法院-HS",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/250909-广西唱作者诉青岛同乐迪餐饮、雷石-著作权纠纷-青岛市南山区人民法院-（2025）鲁0202民初13043号-HS",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/250926-北京雷石 纽凯v雷石、特斯拉北互系列5案-LYG",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/251114-深圳市北测检测-律师函-【和解结案】-HS",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案/260427-厦门面声源vs雷石-合同纠纷-北京市高院-再审案-HS",
]

def main():
    script_dir = Path(__file__).parent.parent
    extract_cmd = script_dir / "bin" / "extract.py"
    
    success = 0
    failed = 0
    
    print(f"开始批量重提取 {len(FAILED_CASES)} 个案例...\n")
    
    for i, case_path in enumerate(FAILED_CASES, 1):
        print(f"[{i}/{len(FAILED_CASES)}] 提取: {Path(case_path).name}")
        
        try:
            result = subprocess.run(
                [
                    sys.executable, str(extract_cmd),
                    "scan", case_path,
                    "--max-depth", "2",
                    "--ai",
                    "--engine", "basic"
                ],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # 检查输出中是否有"案号"字段
            if "案号" in result.stdout:
                success += 1
                # 提取案号信息
                for line in result.stdout.split("\n"):
                    if "案号" in line and ":" in line:
                        print(f"  -> {line.strip()}")
                        break
            else:
                failed += 1
                print(f"  -> ❌ 提取失败")
                
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"  -> ❌ 超时")
        except Exception as e:
            failed += 1
            print(f"  -> ❌ 错误: {e}")
    
    print(f"\n{'='*60}")
    print(f"批量重提取完成: 成功 {success}/{len(FAILED_CASES)}, 失败 {failed}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
