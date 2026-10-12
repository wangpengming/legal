#!/usr/bin/env python3
"""
Prompts 规则库验证脚本
验证所有提示词文件是否完整可用
"""
import json
import sys
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# 提示词清单（按 prompts.yaml 索引）
# 格式说明: (文件路径, 名称, 描述, 是否需要输出格式)
EXPECTED_PROMPTS = [
    ("提取/1_新案材料提取_D1-D5.md", "新案材料提取_D1-D5", "核心5维度提取", True),
    ("提取/2_跨案归纳_Artifact汇聚.md", "跨案归纳_Artifact汇聚", "跨案归纳模板", True),
    ("提取/3_质量检查_提取物审核.md", "质量检查_提取物审核", "质量审核清单", False),
    ("匹配/4_新案匹配_相似案源检索.md", "新案匹配_相似案源检索", "相似案匹配", True),
    ("生成/5_答辩状生成.md", "答辩状生成", "答辩状生成", True),
    ("生成/6_质证意见生成.md", "质证意见生成", "质证意见生成", True),
    ("生成/7_当庭陈述生成.md", "当庭陈述生成", "当庭陈述生成", True),
    ("生成/8_证据目录生成.md", "证据目录生成", "证据目录生成", True),
]

# 必需元素检查清单
REQUIRED_ELEMENTS = {
    "version_header": ["版本", "version"],
    "role_definition": ["你是", "角色"],
    "output_format": ["输出", "格式"],
    "quality_check": ["审核", "检查", "验证"],
}


def check_prompt_file(file_path: Path) -> dict:
    """检查单个提示词文件"""
    result = {
        "file": file_path,
        "exists": file_path.exists(),
        "size": 0,
        "elements": {},
        "has_version": False,
        "has_role": False,
        "has_output_format": False,
        "has_quality_check": False,
        "line_count": 0,
        "issues": [],
    }
    
    if not file_path.exists():
        result["issues"].append("文件不存在")
        return result
    
    content = file_path.read_text(encoding="utf-8")
    result["size"] = len(content)
    result["line_count"] = len(content.splitlines())
    
    # 检查必需元素
    for key, keywords in REQUIRED_ELEMENTS.items():
        found = any(kw in content for kw in keywords)
        result["elements"][key] = found
        if key == "version_header":
            result["has_version"] = found
        elif key == "role_definition":
            result["has_role"] = found
        elif key == "output_format":
            result["has_output_format"] = found
        elif key == "quality_check":
            result["has_quality_check"] = found
    
    # 检查 YAML frontmatter
    if content.strip().startswith("---"):
        result["has_yaml_frontmatter"] = True
    else:
        result["has_yaml_frontmatter"] = False
        result["issues"].append("缺少 YAML frontmatter")
    
    return result


def main():
    print("=" * 70)
    print("Prompts 规则库验证报告")
    print("=" * 70)
    
    passed = 0
    failed = 0
    warnings = 0
    
    for rel_path, name, desc, needs_output in EXPECTED_PROMPTS:
        file_path = PROMPTS_DIR / rel_path
        result = check_prompt_file(file_path)
        
        print(f"\n📄 {name}")
        print(f"   描述: {desc}")
        
        if not result["exists"]:
            print(f"   ❌ 文件不存在")
            failed += 1
            continue
        
        # 显示基本信息
        print(f"   大小: {result['size']} 字节")
        print(f"   行数: {result['line_count']} 行")
        
        # 检查元素
        elements_status = []
        if result["has_version"]:
            elements_status.append("✅ 版本号")
        else:
            elements_status.append("⚠️ 缺少版本号")
            warnings += 1
        
        if result["has_role"]:
            elements_status.append("✅ 角色定义")
        else:
            elements_status.append("⚠️ 缺少角色定义")
            warnings += 1
        
        if needs_output:
            # 需要输出格式的提示词
            if result["has_output_format"]:
                elements_status.append("✅ 输出格式")
            else:
                elements_status.append("⚠️ 缺少输出格式")
                warnings += 1
        else:
            # 审核清单类提示词，不需要输出格式
            elements_status.append("ℹ️ 无需输出格式（审核清单）")
        
        if result["has_yaml_frontmatter"]:
            elements_status.append("✅ YAML frontmatter")
        else:
            elements_status.append("⚠️ 缺少 YAML frontmatter")
            warnings += 1
        
        for status in elements_status:
            print(f"   {status}")
        
        # 显示问题
        for issue in result["issues"]:
            print(f"   ⚠️ {issue}")
        
        # 判断是否通过
        if result["exists"] and result["has_version"] and result["has_role"]:
            if needs_output and not result["has_output_format"]:
                print(f"   ⚠️ 需修订（缺少输出格式）")
                warnings += 1
            else:
                print(f"   ✅ 通过验证")
                passed += 1
        else:
            print(f"   ⚠️ 需修订")
            warnings += 1
    
    # 统计
    print("\n" + "=" * 70)
    print("验证统计")
    print("=" * 70)
    print(f"  总计: {len(EXPECTED_PROMPTS)} 个")
    print(f"  ✅ 通过: {passed} 个")
    print(f"  ⚠️ 需修订: {warnings} 个")
    print(f"  ❌ 失败: {failed} 个")
    
    # 示例文件检查
    print("\n" + "=" * 70)
    print("示例文件检查")
    print("=" * 70)
    
    example_dir = PROMPTS_DIR / "示例"
    if example_dir.exists():
        example_files = list(example_dir.glob("*.md"))
        print(f"  共 {len(example_files)} 个示例文件:")
        for f in example_files:
            print(f"    - {f.name}")
    else:
        print("  ❌ 示例目录不存在")
    
    print("\n" + "=" * 70)
    
    # 返回状态码
    if failed > 0:
        print("❌ 验证失败：存在缺失文件")
        return 1
    elif warnings > 0:
        print("⚠️ 验证通过但有警告")
        return 0
    else:
        print("✅ 所有提示词验证通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
