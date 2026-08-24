#!/usr/bin/env python3
"""一键状态查询（后端 + 前端）。"""
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent
python = sys.executable

print("⚖️  出庭手续生成器 v2.2.5 · 服务状态")
print("=" * 50)

for svc in ["backend", "frontend"]:
    status_script = MODULE_ROOT / svc / "bin" / "status.py"
    if status_script.exists():
        subprocess.run([python, str(status_script)])
        print()