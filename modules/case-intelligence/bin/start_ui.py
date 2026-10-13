#!/usr/bin/env python3
# =============================================
# 启动 case-intelligence Web UI（Streamlit，端口 18503）
# 后台启动：写 PID + 日志到 .run/，等待端口就绪后返回
# 跨平台：Windows 用 CREATE_NEW_PROCESS_GROUP，POSIX 用 start_new_session
# =============================================
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
PID_FILE = RUN_DIR / "case-intelligence-ui.pid"
LOG_FILE = RUN_DIR / "case-intelligence-ui.log"

DEFAULT_PORT = 18503
FALLBACK_PORT = 18504
HEALTH_TIMEOUT = 20  # 秒


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _find_python() -> str:
    """优先模块自带 .venv，其次当前解释器（不依赖其它模块的 venv）。"""
    for rel in (".venv/bin/python3", ".venv/bin/python", ".venv/Scripts/python.exe"):
        p = PROJECT_ROOT / rel
        if p.exists():
            return str(p)
    return sys.executable


def _read_pid():
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _free_port():
    for port in (DEFAULT_PORT, FALLBACK_PORT):
        if not _port_in_use(port):
            return port
    return None


def start() -> bool:
    RUN_DIR.mkdir(exist_ok=True)

    pid = _read_pid()
    if _pid_alive(pid):
        print(f"ℹ️  UI 已在运行（PID {pid}）")
        print(f"   访问 http://localhost:{DEFAULT_PORT}")
        return True

    port = _free_port()
    if not port:
        print(f"❌ 端口 {DEFAULT_PORT} / {FALLBACK_PORT} 均被占用")
        print("   请先释放端口：python3 bin/stop.py")
        return False

    print("=" * 60)
    print("case-intelligence · Web UI")
    print("=" * 60)
    print(f"端口:     {port}")
    print(f"PID 文件: {PID_FILE}")
    print(f"日志文件: {LOG_FILE}")
    print("\n启动中...")

    cmd = [
        _find_python(), "-m", "streamlit", "run", str(PROJECT_ROOT / "app.py"),
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env.setdefault("DATA_DIR", str(PROJECT_ROOT / "data"))

    popen_kwargs = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    with open(LOG_FILE, "w") as f:
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), env=env,
            stdout=f, stderr=subprocess.STDOUT, **popen_kwargs,
        )
    PID_FILE.write_text(str(proc.pid))

    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        if _port_in_use(port):
            print("\n✅ 启动成功!")
            print(f"   访问 http://localhost:{port}")
            print("   停止: python3 bin/stop.py")
            return True
        if proc.poll() is not None:
            print(f"\n❌ 启动失败（进程已退出），请查看日志: {LOG_FILE}")
            if PID_FILE.exists():
                PID_FILE.unlink()
            return False
        time.sleep(0.5)

    print(f"\n❌ 启动超时（{HEALTH_TIMEOUT}s 内端口未就绪），请查看日志: {LOG_FILE}")
    return False


def main() -> int:
    return 0 if start() else 1


if __name__ == "__main__":
    sys.exit(main())