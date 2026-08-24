#!/usr/bin/env python3
"""前端启动脚本（Vite dev server）。

跨平台兼容：使用 subprocess.Popen 替代 os.fork()。
自动检测 node_modules 缺失并 npm install。
"""
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


def kill_port_owner(port: int):
    """强制释放端口：找占用进程 PID → SIGKILL。"""
    import subprocess as sp
    try:
        # macOS / Linux: lsof -ti :PORT
        result = sp.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            for pid_str in result.stdout.strip().split("\n"):
                pid = int(pid_str)
                os.kill(pid, 9)
                print(f"🛑 已终止占用端口 {port} 的进程 {pid}")
            time.sleep(1)
            return True
    except Exception:
        pass
    # Windows fallback: netstat
    try:
        result = sp.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                pid = int(line.strip().split()[-1])
                sp.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                print(f"🛑 已终止占用端口 {port} 的进程 {pid}")
                time.sleep(1)
                return True
    except Exception:
        pass
    return False


# 检查 node_modules 完整性（比较锁文件时间戳，避免目录存在但过期）
node_modules = ROOT / "node_modules"
lock_file = ROOT / "package-lock.json"
node_lock = node_modules / ".package-lock.json"
need_install = True
if node_modules.exists() and node_lock.exists() and lock_file.exists():
    if lock_file.stat().st_mtime <= node_lock.stat().st_mtime:
        need_install = False

if need_install:
    if not node_modules.exists():
        print("📦 首次运行，安装前端依赖...")
    else:
        print("📦 node_modules 已过期，更新前端依赖...")
    result = subprocess.run(["npm", "install"], cwd=str(ROOT), check=False)
    if result.returncode != 0:
        print("❌ npm install 失败，请检查网络或手动执行: cd frontend && npm install")
        sys.exit(1)

# 停止旧进程
if PID_FILE.exists():
    try:
        old_pid = int(PID_FILE.read_text().strip())
        os.kill(old_pid, 9)
        print(f"🛑 停止旧前端进程 {old_pid}")
    except Exception:
        pass
    time.sleep(1)

# 端口冲突处理：强制释放，不换端口
if port_in_use(PORT):
    print(f"⚠️  端口 {PORT} 已被占用，正在清理...")
    if kill_port_owner(PORT):
        if port_in_use(PORT):
            print(f"❌ 端口 {PORT} 清理失败，请手动处理")
            print(f"   运行: python3 bin/stop.py")
            sys.exit(1)
    else:
        print(f"❌ 无法自动清理端口 {PORT}，请手动处理")
        print(f"   运行: python3 bin/stop.py")
        sys.exit(1)

# 后台启动（subprocess.Popen，跨平台兼容）
rollover_log(LOG_FILE)

log_f = open(LOG_FILE, "w")
proc = subprocess.Popen(
    ["npx", "vite", "--port", str(PORT), "--host"],
    cwd=str(ROOT),
    stdout=log_f,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
)

PID_FILE.write_text(str(proc.pid))
print(f"🚀 启动前端 (PID {proc.pid}) 端口 {PORT}")
print(f"   访问 http://localhost:{PORT}")

# 等待端口就绪
for i in range(20):
    if port_in_use(PORT):
        print(f"✅ 前端就绪 http://localhost:{PORT}")
        break
    time.sleep(1)
else:
    print(f"⚠️  前端启动超时，请检查日志: {LOG_FILE}")

log_f.close()