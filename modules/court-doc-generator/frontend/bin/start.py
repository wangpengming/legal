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
LOG_FILE = RUN_DIR / "frontend.log"
PORT = 18502

MAX_LOG_SIZE = 5 * 1024 * 1024   # 超过 5MB 触发轮转
KEEP_LOGS = 5                    # 保留 N 份归档（.1 最新 → .N 最旧）


def rollover_log(log_file: Path):
    """启动前日志轮转：超限旧日志归档为 .1/.2/...，防止单文件激增。"""
    if not log_file.exists() or log_file.stat().st_size < MAX_LOG_SIZE:
        return
    oldest = Path(str(log_file) + f".{KEEP_LOGS}")
    oldest.unlink(missing_ok=True)
    for i in range(KEEP_LOGS - 1, 0, -1):
        src = Path(str(log_file) + f".{i}")
        if src.exists():
            src.rename(Path(str(log_file) + f".{i + 1}"))
    log_file.rename(Path(str(log_file) + ".1"))
    print(f"🔄 日志轮转：{log_file.name} 已归档为 {log_file.name}.1（保留 {KEEP_LOGS} 份）")


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

# 后台启动（stdout/stderr 重定向到日志文件；stdin 置 /dev/null，
# 避免父进程 pty 关闭后 vite readline 读 stdin 抛 EIO 崩溃）
rollover_log(LOG_FILE)  # 覆盖写前先轮转归档

pid = os.fork()
if pid == 0:
    with open(LOG_FILE, "w") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, sys.stdin.fileno())
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