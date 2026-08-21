#!/usr/bin/env python3
"""后端重启。"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
python = sys.executable

# 停止
print("🛑 停止旧服务...")
subprocess.run([python, str(SCRIPT_DIR / "stop.py")], check=False)

# 启动
print("🚀 启动新服务...")
subprocess.run([python, str(SCRIPT_DIR / "start.py")], check=True)