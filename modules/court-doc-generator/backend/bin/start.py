#!/usr/bin/env python3
"""后端启动脚本（FastAPI + Uvicorn）。

跨平台兼容：使用 subprocess.Popen 替代 os.fork()。
端口冲突时强制清理占用进程，不换端口。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# 找到 backend 目录
SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
RUN_DIR = ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)

PID_FILE = RUN_DIR / "backend.pid"
LOG_FILE = RUN_DIR / "backend.log"
PORT = 8001

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


def find_python():
    """查找虚拟环境 Python，fallback 到当前 Python。"""
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    # 如果通过 bin/start.py 调用，sys.executable 已是虚拟环境 Python
    return sys.executable


if __name__ == "__main__":
    # 停止旧进程
    pid = read_pid()
    if pid and is_running(pid):
        print(f"🛑 停止旧进程 {pid}")
        try:
            os.kill(pid, 9)
        except OSError:
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

    python = find_python()

    rollover_log(LOG_FILE)

    # 后台启动（subprocess.Popen，跨平台兼容）
    log_f = open(LOG_FILE, "w")
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=str(ROOT),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    PID_FILE.write_text(str(proc.pid))

    dist_dir = ROOT.parent / "frontend" / "dist"
    if (dist_dir / "index.html").exists():
        print(f"🌐 生产模式：前端由后端统一托管，浏览器访问 http://localhost:{PORT}")
    print(f"🚀 启动 backend (PID {proc.pid}) 端口 {PORT}")
    print(f"   日志: {LOG_FILE}")
    print(f"   健康: http://localhost:{PORT}/health")

    # 等待端口就绪（最多 8 秒）
    for i in range(16):
        time.sleep(0.5)
        if port_in_use(PORT):
            print(f"✅ 后端就绪 http://localhost:{PORT}/docs")
            break
    else:
        print(f"⚠️  后端启动超时，请检查日志: {LOG_FILE}")

    log_f.close()
