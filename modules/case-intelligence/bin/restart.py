#!/usr/bin/env python3
# =============================================
# 重启脚本（CLI 模块，等效于 start）
# =============================================
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main() -> None:
    print("🔄 case-intelligence 重启（CLI 工具，等效于 start）")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "bin" / "start.py")])

if __name__ == "__main__":
    main()
