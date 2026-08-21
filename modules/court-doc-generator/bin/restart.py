#!/usr/bin/env python3
"""一键重启（后端 + 前端）。"""
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent
python = sys.executable

subprocess.run([python, str(MODULE_ROOT / "bin" / "stop.py")], check=False)
subprocess.run([python, str(MODULE_ROOT / "bin" / "start.py")], check=True)