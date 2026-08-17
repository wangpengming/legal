#!/usr/bin/env python3
# =============================================
# 服务状态查询脚本
# =============================================
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 18501
PID_FILE = PROJECT_ROOT / ".run" / "streamlit.pid"
LOG_FILE = PROJECT_ROOT / ".run" / "streamlit.log"
HEALTH_URL = f"http://localhost:{DEFAULT_PORT}/_stcore/health"


def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def check_health(port: int) -> tuple[bool, str]:
    """健康检查。返回 (ok, body_or_error)。"""
    try:
        import urllib.request
        req = urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=2)
        return req.status == 200, req.read().decode()
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def main() -> None:
    print("📊 出庭手续生成器 · 服务状态")
    print("=" * 50)

    # 端口
    port_listening = is_port_listening(DEFAULT_PORT)
    print(f"🔌 端口 {DEFAULT_PORT}: {'✅ 已监听' if port_listening else '❌ 未监听'}")

    # PID 文件
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        print(f"📄 PID 文件: {pid}")
    else:
        print(f"📄 PID 文件: 无")

    # 健康检查
    ok, body = check_health(DEFAULT_PORT)
    print(f"💚 健康检查 ({HEALTH_URL}): {'✅ 通过' if ok else '❌ 失败'}")
    if not ok and body:
        print(f"   错误：{body[:100]}")

    # 日志尾部
    if LOG_FILE.exists():
        size_kb = LOG_FILE.stat().st_size / 1024
        print(f"📋 日志文件: {LOG_FILE}（{size_kb:.1f} KB）")

    print()
    if port_listening and ok:
        print("🎉 服务正常运行")
        print(f"   访问 http://localhost:{DEFAULT_PORT}")
        sys.exit(0)
    elif port_listening:
        print("⚠️ 端口监听中，但健康检查失败（可能 Streamlit 还在初始化）")
        sys.exit(2)
    else:
        print("💤 服务未运行")
        sys.exit(1)


if __name__ == "__main__":
    main()