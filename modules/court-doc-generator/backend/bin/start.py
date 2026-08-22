#!/usr/bin/env python3
"""后端启动脚本（FastAPI）。"""
import os, sys, time
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

# 检查端口是否已被占用
def port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

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

if __name__ == "__main__":
    # 停止旧进程
    pid = read_pid()
    if pid and is_running(pid):
        print(f"🛑 停止旧进程 {pid}")
        os.kill(pid, 9)
        time.sleep(1)

    if port_in_use(PORT):
        print(f"⚠️  端口 {PORT} 已被占用，尝试 fallback {PORT+1}")
        PORT_NEW = PORT + 1
        if port_in_use(PORT_NEW):
            print(f"❌ 端口 {PORT_NEW} 也被占用，退出")
            sys.exit(1)
    else:
        PORT_NEW = PORT

    venv_python = os.environ.get("VIRTUAL_ENV")
    if venv_python:
        python = str(Path(venv_python) / "bin" / "python")
    else:
        python = sys.executable

    venv_site = ROOT / ".venv"
    env = os.environ.copy()
    if venv_site.exists():
        env["VIRTUAL_ENV"] = str(venv_site)

    rollover_log(LOG_FILE)  # 覆盖写前先轮转归档

    pid = os.fork()
    if pid == 0:
        # 子进程
        with open(LOG_FILE, "w") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        os.chdir(str(ROOT))
        os.execvp(python, [python, "-m", "uvicorn",
            "app.main:app", "--host", "0.0.0.0", "--port", str(PORT_NEW)])

    # 父进程
    dist_dir = ROOT.parent / "frontend" / "dist"
    if (dist_dir / "index.html").exists():
        print(f"🌐 生产模式：前端由后端统一托管，浏览器访问 http://localhost:{PORT_NEW}")
    PID_FILE.write_text(str(pid))
    print(f"🚀 启动 backend (PID {pid}) 端口 {PORT_NEW}")
    print(f"   日志: {LOG_FILE}")
    print(f"   健康: http://localhost:{PORT_NEW}/health")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Started PID {pid} port {PORT_NEW}\n")
