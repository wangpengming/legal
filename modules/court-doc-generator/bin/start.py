#!/usr/bin/env python3
# =============================================
# 跨平台启动脚本（macOS/Linux/Windows 通用）
# =============================================
# 设计原则：
# - 不依赖 bash 3.2 / zsh / PowerShell 差异
# - 自动定位 Python 解释器（python3 → python）
# - 端口占用检测与避让（默认 18501，避让 19000）
# - 自动开浏览器（首次启动）
# - 健康检查（启动后 8 秒内探测）
#
# 使用：
#     python bin/start.py
# 或：
#     bash bin/start.sh     # 包裹脚本
#     bin\\start.bat          # Windows
# =============================================
import os
import sys
import time
import socket
import shutil
import subprocess
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 18501
FALLBACK_PORT = 19000  # 18501 占用时的备选
HEALTH_URL = "http://localhost:{port}/_stcore/health"
OPEN_BROWSER_DELAY = 6  # 启动后几秒打开浏览器
PID_DIR = PROJECT_ROOT / ".run"
PID_FILE = PID_DIR / "streamlit.pid"
LOG_FILE = PID_DIR / "streamlit.log"


def find_python() -> str:
    """定位 Python 解释器（兼容 Windows Store 陷阱）。

    顺序：
    1. sys.executable（脚本解释器，最可靠）
    2. python3
    3. python（⚠️ Windows 上 py 命令会触发 Store，所以优先 python.exe 而非 py.exe）
    """
    candidates = [sys.executable, "python3", "python"]
    for cand in candidates:
        if not cand:
            continue
        # sys.executable 永远存在
        if cand == sys.executable:
            return cand
        # 命令查找
        if shutil.which(cand):
            return cand
    print("❌ 未找到 Python 解释器。请先安装 Python 3.10+", file=sys.stderr)
    sys.exit(1)


def is_port_listening(port: int) -> bool:
    """检测端口是否被占用（TCP connect 测试）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """等待端口就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_listening(port):
            return True
        time.sleep(0.3)
    return False


def check_health(port: int, timeout: float = 8.0) -> bool:
    """健康检查 GET /_stcore/health。"""
    try:
        import urllib.request
        req = urllib.request.urlopen(HEALTH_URL.format(port=port), timeout=2)
        return req.status == 200
    except Exception:
        return False


def is_already_running() -> int | None:
    """检查是否已有进程在运行（PID 文件 + 端口检测）。"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # 进程是否存在
            if sys.platform == "win32":
                subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, check=False,
                )
            else:
                os.kill(pid, 0)  # 信号 0 仅探测
            # 同时检查端口
            if is_port_listening(DEFAULT_PORT):
                return pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
    return None


def open_browser(port: int) -> None:
    """打开默认浏览器。"""
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        print(f"🌐 已打开浏览器：{url}")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ 自动打开浏览器失败，请手动访问：{url}（{e}）")


def main() -> None:
    PID_DIR.mkdir(exist_ok=True)

    # 1. 已运行检查
    existing_pid = is_already_running()
    if existing_pid:
        print(f"⚠️ 服务已在运行（PID {existing_pid}），无需重复启动")
        print(f"   访问 http://localhost:{DEFAULT_PORT}")
        return

    # 2. 端口选择（避让）
    port = DEFAULT_PORT
    if is_port_listening(port):
        print(f"⚠️ 端口 {port} 已被占用，切换到 {FALLBACK_PORT}")
        port = FALLBACK_PORT
        if is_port_listening(port):
            print(f"❌ 备选端口 {FALLBACK_PORT} 也被占用。请手动释放端口", file=sys.stderr)
            sys.exit(1)

    # 3. 启动
    python = find_python()
    cmd = [
        python, "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false",
    ]
    print(f"🚀 启动中：{' '.join(cmd)}")
    print(f"   cwd: {PROJECT_ROOT}")
    print(f"   log: {LOG_FILE}")

    log_fp = open(LOG_FILE, "ab")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        # Windows 上不弹 cmd 窗口
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"✅ PID={proc.pid} 端口={port}")

    # 4. 等待就绪
    if wait_for_port(port, timeout=15):
        print(f"✅ 端口 {port} 已就绪")
        # 健康检查
        time.sleep(2)  # 等待 Streamlit 完成初始化
        if check_health(port):
            print(f"✅ 健康检查通过：{HEALTH_URL.format(port=port)}")
        else:
            print(f"⚠️ 健康检查未通过（Streamlit 可能仍在初始化）")
        # 5. 开浏览器
        # v1.1.3 修复：原 `sleep(OPEN_BROWSER_DELAY - 8)` 在 OPEN_BROWSER_DELAY=6 时
        # 为负值，触发 ValueError 崩溃导致浏览器永不打开。
        # wait_for_port 已等端口就绪 + 上方 sleep(2)，这里直接开浏览器即可。
        open_browser(port)
    else:
        print(f"⚠️ 端口 {port} 启动超时。请查看日志：{LOG_FILE}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")