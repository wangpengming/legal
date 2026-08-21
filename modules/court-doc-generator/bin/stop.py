#!/usr/bin/env python3
"""一键停止出庭手续生成器（后端 + 前端）。"""
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent
python = sys.executable

print("🛑 停止出庭手续生成器...")

for svc in ["frontend", "backend"]:
    stop_script = MODULE_ROOT / svc / "bin" / "stop.py"
    if stop_script.exists():
        subprocess.run([python, str(stop_script)], check=False)

print("✅ 全部已停止")