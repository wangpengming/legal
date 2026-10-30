#!/usr/bin/env python3
"""
批量导入往年案例
"""
import sys
import os
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent
VENV_PYTHON = "/Users/zhangyang/Desktop/code/legal/modules/court-doc-generator/.venv/bin/python3"
BASE_DIRS = [
    "/Users/zhangyang/Desktop/往年案例/2024年度已结案",
    "/Users/zhangyang/Desktop/往年案例/2025年度已结案",
    "/Users/zhangyang/Desktop/往年案例/2026年度已结案",
]

def main():
    all_cases = []
    for base_dir in BASE_DIRS:
        if os.path.exists(base_dir):
            for name in sorted(os.listdir(base_dir)):
                case_dir = os.path.join(base_dir, name)
                if os.path.isdir(case_dir):
                    all_cases.append(case_dir)
    
    print(f"找到 {len(all_cases)} 个案例")
    print()
    
    success = 0
    failed = []
    
    for i, case_dir in enumerate(all_cases, 1):
        case_name = os.path.basename(case_dir)
        print(f"[{i}/{len(all_cases)}] 处理: {case_name[:50]}...", end=" ", flush=True)
        
        try:
            result = subprocess.run(
                [VENV_PYTHON, str(PROJECT_ROOT / "bin" / "extract.py"), 
                 "scan", case_dir, "--ai", "--import", "-y"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(PROJECT_ROOT),
            )
            
            if "✅ 入库成功" in result.stdout or result.returncode == 0:
                # 提取提取物数量
                for line in result.stdout.split("\n"):
                    if "提取物:" in line:
                        print(line.strip().split("提取物:")[1])
                        break
                else:
                    print("✅")
                success += 1
            else:
                print("❌")
                failed.append((case_name, result.stderr[-200:] if result.stderr else ""))
                
        except subprocess.TimeoutExpired:
            print("⏱️ 超时")
            failed.append((case_name, "超时"))
        except Exception as e:
            print(f"❌ 错误: {e}")
            failed.append((case_name, str(e)))
    
    print()
    print("=" * 50)
    print(f"导入完成: {success} 成功, {len(failed)} 失败")
    
    if failed:
        print()
        print("失败列表:")
        for name, err in failed[:10]:
            print(f"  - {name[:40]}: {err[:80]}")
        if len(failed) > 10:
            print(f"  ... 还有 {len(failed) - 10} 个失败")

if __name__ == "__main__":
    main()
