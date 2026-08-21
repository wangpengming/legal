#!/usr/bin/env python3
"""前端状态查询。"""
import os
import socket
from pathlib import Path

ROOT = Path(__file__).parent.parent
PID_FILE = ROOT / ".run" / "frontend.pid"
PORT = 18502


def read_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            return None
    return None


def port_listening(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


print("📊 出庭手续生成器 · 前端服务状态")
print("=" * 50)

listening = port_listening(PORT)
print(f"🔌 端口 {PORT}: {'✅ 已监听' if listening else '❌ 未监听'}")

pid = read_pid()
if pid:
    try:
        os.kill(pid, 0)
        print(f"📄 PID 文件: {pid} ✅ 运行中")
    except OSError:
        print(f"📄 PID 文件: {pid} ❌ 已失效")
else:
    print("📄 PID 文件: ❌ 不存在")

print()
if listening:
    print("✅ 前端正常运行")
    print(f"   访问 http://localhost:{PORT}")
    exit(0)
else:
    print("❌ 前端未运行")
    exit(1)