#!/usr/bin/env python3
"""前端重启。"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
python = sys.executable

subprocess.run([python, str(SCRIPT_DIR / "stop.py")], check=False)
subprocess.run([python, str(SCRIPT_DIR / "start.py")], check=True)