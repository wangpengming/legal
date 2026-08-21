#!/usr/bin/env python3
"""后端状态查询（端口 + PID + 健康检查 + 日志尾部）。"""
import os
import socket
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUN_DIR = ROOT / ".run"
PID_FILE = RUN_DIR / "backend.pid"
LOG_FILE = RUN_DIR / "backend.log"
PORT = 8001


def read_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            return None
    return None


def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def port_listening(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def health_check(port):
    try:
        u = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
        return u.status == 200, u.read().decode()
    except Exception:
        return False, ""


print("📊 出庭手续生成器 · 后端服务状态")
print("=" * 50)

# 端口
listening = port_listening(PORT)
print(f"🔌 端口 {PORT}: {'✅ 已监听' if listening else '❌ 未监听'}")

# PID
pid = read_pid()
if pid:
    alive = is_running(pid)
    print(f"📄 PID 文件: {pid} {'✅ 运行中' if alive else '❌ 已失效'}")
else:
    print("📄 PID 文件: ❌ 不存在")

# 健康检查
if listening:
    ok, body = health_check(PORT)
    print(f"💚 健康检查 (http://localhost:{PORT}/health): {'✅ 通过' if ok else '❌ 失败'}")
    if ok:
        print(f"   响应: {body.strip()}")

# 日志
log_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
print(f"📋 日志文件: {LOG_FILE.relative_to(ROOT)} ({log_size / 1024:.1f} KB)")

print()
if listening and pid and is_running(pid):
    print("✅ 服务正常运行")
    print(f"   访问 http://localhost:{PORT}/docs")
    exit(0)
elif listening:
    print("⚠️  端口在监听但 PID 文件状态异常")
    exit(2)
else:
    print("❌ 服务未运行")
    exit(1)