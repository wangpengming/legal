#!/usr/bin/env python3
"""
Thunderbox Console 启动脚本

用法：
    python3 bin/start.py          # 启动后端（uvicorn + FastAPI）
    python3 bin/start.py --check   # 仅检测端口冲突，不启动

端口：18502（可在 module.yaml 中修改）
PID：modules/thunderbox/.run/thunderbox.pid
日志：modules/thunderbox/.run/thunderbox.log
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent.resolve()
RUN_DIR = MODULE_ROOT / ".run"
PID_FILE = RUN_DIR / "thunderbox.pid"
LOG_FILE = RUN_DIR / "thunderbox.log"
PORT = int(os.environ.get("PORT", "18504"))
VENV_DIR     = MODULE_ROOT / "backend" / ".venv"
VENV_PYTHON  = VENV_DIR / "bin" / "python"
VENV_PYTHON_STR = str(VENV_PYTHON)
BACKEND_MAIN = MODULE_ROOT / "backend" / "main.py"
VERSION = "1.0.0"


def find_python() -> str:
    """查找可用 Python：优先虚拟环境，fallback 到当前 Python"""
    if VENV_PYTHON.exists():
        return VENV_PYTHON_STR
    return sys.executable


def is_port_in_use(port: int) -> bool:
    """检测端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_run_dir():
    """确保 .run 目录存在"""
    RUN_DIR.mkdir(exist_ok=True)


def write_pid(pid: int):
    """写入 PID 文件"""
    ensure_run_dir()
    PID_FILE.write_text(str(pid))


def remove_pid():
    """删除 PID 文件"""
    if PID_FILE.exists():
        PID_FILE.unlink()


def start_server(check_only: bool = False) -> int:
    """启动 uvicorn 服务器"""
    ensure_run_dir()

    # 端口检测
    if is_port_in_use(PORT):
        fallback = int(os.environ.get("PORT_FALLBACK", "19000"))
        if is_port_in_use(fallback):
            print(f"❌ 端口 {PORT} 和 {fallback} 均被占用")
            print("   请手动释放端口或设置 PORT 环境变量")
            return 1
        print(f"⚠️  端口 {PORT} 被占用，自动切换到 {fallback}")
        port = fallback
    else:
        port = PORT

    if check_only:
        print(f"✅ 端口 {port} 可用")
        return 0

    python = find_python()

    # 启动 uvicorn
    cmd = [
        python, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "info",
    ]

    log_fd = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        cmd,
        cwd=str(MODULE_ROOT),
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PORT": str(port)},
    )

    write_pid(proc.pid)
    print(f"✅ Thunderbox Console v{VERSION} 已启动")
    print(f"   端口: {port}")
    print(f"   PID: {proc.pid}")
    print(f"   日志: {LOG_FILE}")

    # 等待健康检查
    import urllib.request
    health_url = f"http://127.0.0.1:{port}/health"
    for i in range(16):  # 8 秒（每 0.5 秒）
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(health_url, timeout=2) as r:
                if r.status == 200:
                    print(f"   健康检查: ✅ 通过")
                    print(f"   访问 http://localhost:{port}")
                    return 0
        except Exception:
            pass

    print(f"⚠️  健康检查未通过，请检查日志: {LOG_FILE}")
    return 1


if __name__ == "__main__":
    check_only = "--check" in sys.argv
    sys.exit(start_server(check_only=check_only))
