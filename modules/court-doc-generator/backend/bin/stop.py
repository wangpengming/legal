#!/usr/bin/env python3
"""后端停止脚本。"""
import os, time, signal
from pathlib import Path

ROOT = Path(__file__).parent.parent
PID_FILE = ROOT / ".run" / "backend.pid"

def read_pid():
    if PID_FILE.exists():
        try: return int(PID_FILE.read_text().strip())
        except: pass
    return None

def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

pid = read_pid()
if pid and is_running(pid):
    print(f"🛑 停止进程 {pid}")
    os.kill(pid, signal.SIGTERM)
    time.sleep(1)
    if is_running(pid):
        os.kill(pid, 9)
else:
    print("⚠️  未找到运行中的 backend 进程")

if PID_FILE.exists():
    PID_FILE.unlink()
print("✅ 已停止")
