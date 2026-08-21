#!/usr/bin/env python3
"""
出庭手续生成器 — 重启脚本。

用法：
  python bin/restart.py          # 重启全部
  python bin/restart.py --backend   # 仅重启后端
  python bin/restart.py --frontend  # 仅重启前端
"""
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).parent


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="全栈重启")
    parser.add_argument("--backend",  action="store_true", help="仅重启后端")
    parser.add_argument("--frontend", action="store_true", help="仅重启前端")
    args = parser.parse_args()

    be_flag = ("--backend" if args.backend else None)
    fe_flag = ("--frontend" if args.frontend else None)

    # 1. 停止
    stop_args = [sys.executable, str(BIN / "stop.py")]
    if be_flag: stop_args.append(be_flag)
    if fe_flag: stop_args.append(fe_flag)
    print("🔄 停止服务...")
    subprocess.run(stop_args, check=False)

    # 2. 等端口释放
    import time; time.sleep(2)

    # 3. 启动
    print("🔄 启动服务...")
    start_args = [sys.executable, str(BIN / "start.py")]
    if be_flag: start_args.append(be_flag)
    if fe_flag: start_args.append(fe_flag)
    result = subprocess.run(start_args, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
