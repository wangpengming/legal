#!/usr/bin/env python3
"""
批量对 ~/Desktop/往年案例/ 下的 99 个案例目录跑 AI D1-D5 提取入库。
使用升级后的 build_extraction_prompt（字段更全）。
"""
import subprocess
import time
from pathlib import Path

CASE_INTEL = Path(__file__).parent.parent.resolve()
DATA_ROOT  = Path.home() / "Desktop" / "往年案例"
YEARS = ["2024年度已结案", "2025年度已结案", "2026年度已结案"]

all_dirs = []
for year in YEARS:
    base = DATA_ROOT / year
    if not base.exists():
        continue
    dirs = sorted([d for d in base.iterdir() if d.is_dir()])
    all_dirs.extend(dirs)

total = len(all_dirs)
print(f"总计 {total} 个案例目录，开始批量 AI 提取...\n")

success = 0
failed  = 0
failed_dirs = []

for i, d in enumerate(all_dirs, 1):
    print(f"[{i}/{total}] {d.name}")
    cmd = [
        "python3", "bin/extract.py", "scan",
        str(d),
        "--ai", "--engine", "minimax", "--import", "-y"
    ]
    result = subprocess.run(
        cmd,
        cwd=str(CASE_INTEL),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if "入库成功" in result.stdout or "✅" in result.stdout:
        print("  ✅ OK")
        success += 1
    else:
        print(f"  ❌ FAILED: {result.stderr[-200:] if result.stderr else result.stdout[-200:]}")
        failed += 1
        failed_dirs.append(str(d))

    time.sleep(1)

print(f"\n=== 完成 ===")
print(f"成功: {success}/{total}")
print(f"失败: {failed}/{total}")
if failed_dirs:
    print("\n失败目录:")
    for fd in failed_dirs:
        print(f"  {fd}")
