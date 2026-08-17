#!/usr/bin/env python3
# =============================================
# 重启脚本（stop + start）
# =============================================
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"


def main() -> None:
    print("🔄 重启流程：停止 → 启动")
    print()
    # 1. stop
    subprocess.run([sys.executable, str(BIN_DIR / "stop.py")], check=False)
    print()
    # 2. 等 2 秒（让端口释放）
    import time
    time.sleep(2)
    # 3. start
    subprocess.run([sys.executable, str(BIN_DIR / "start.py")], check=False)


if __name__ == "__main__":
    main()