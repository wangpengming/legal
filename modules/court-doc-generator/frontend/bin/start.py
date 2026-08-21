#!/usr/bin/env python3
"""前端启动脚本（Vite dev server）。"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUN_DIR = ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)
PID_FILE = RUN_DIR / "frontend.pid"
PORT = 18502


def port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


# 检查 node_modules
if not (ROOT / "node_modules").exists():
    print("📦 首次运行，安装前端依赖...")
    subprocess.run(["npm", "install"], cwd=str(ROOT), check=True)

# 停止旧进程
if PID_FILE.exists():
    try:
        old_pid = int(PID_FILE.read_text().strip())
        os.kill(old_pid, 9)
        print(f"🛑 停止旧前端进程 {old_pid}")
    except Exception:
        pass
    time.sleep(1)

if port_in_use(PORT):
    print(f"❌ 端口 {PORT} 已被占用，请先释放")
    sys.exit(1)

# 后台启动
pid = os.fork()
if pid == 0:
    os.chdir(str(ROOT))
    os.execvp("npx", ["npx", "vite", "--port", str(PORT), "--host"])

PID_FILE.write_text(str(pid))
print(f"🚀 启动前端 (PID {pid}) 端口 {PORT}")
print(f"   访问 http://localhost:{PORT}")

# 等待端口就绪
for i in range(20):
    if port_in_use(PORT):
        print(f"✅ 前端就绪 http://localhost:{PORT}")
        break
    time.sleep(1)
else:
    print(f"⚠️  前端启动超时，请检查日志")