#!/usr/bin/env python3
"""前端停止脚本。"""
import os
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PID_FILE = ROOT / ".run" / "frontend.pid"


def read_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            return None
    return None


pid = read_pid()
if pid:
    try:
        os.kill(pid, 9)
        print(f"🛑 停止前端进程 {pid}")
    except OSError:
        print(f"⚠️  进程 {pid} 不存在")
    time.sleep(1)
else:
    # fallback: 杀掉端口 18502 上的进程
    import subprocess
    result = subprocess.run(["lsof", "-ti", ":18502"], capture_output=True, text=True)
    if result.stdout.strip():
        for p in result.stdout.strip().split("\n"):
            os.kill(int(p), 9)
            print(f"🛑 停止端口占用进程 {p}")

if PID_FILE.exists():
    PID_FILE.unlink()
print("✅ 前端已停止")