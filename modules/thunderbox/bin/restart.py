#!/usr/bin/env python3
"""
Thunderbox Console 重启脚本

用法：
    python3 bin/restart.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 导入同目录下的 stop 和 start
import importlib.util

def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

stop_mod = load_module("stop")
start_mod = load_module("start")


def restart() -> int:
    print("🔄 停止服务...")
    stop_mod.stop()
    print()
    print("🔄 启动服务...")
    return start_mod.start_server()


if __name__ == "__main__":
    sys.exit(restart())
