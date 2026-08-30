#!/usr/bin/env python3
"""
Thunderbox Console 状态检查脚本

检查：端口监听 / PID 文件 / 健康检查 / 日志尾部

用法：
    python3 bin/status.py
退出码：0=运行中 / 1=未运行 / 2=异常
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent.resolve()
PID_FILE = MODULE_ROOT / ".run" / "thunderbox.pid"
LOG_FILE = MODULE_ROOT / ".run" / "thunderbox.log"
PORT = int(os.environ.get("PORT", "18502"))
VERSION = "1.0.0"


def is_port_listening(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_health(port: int) -> tuple[bool, str]:
    """检查健康检查端点"""
    try:
        import urllib.request
        url = f"http://127.0.0.1:{port}/health"
        with urllib.request.urlopen(url, timeout=3) as r:
            body = r.read().decode()
            return (r.status == 200, body)
    except Exception as e:
        return False, str(e)


def get_log_tail(path: Path, lines: int = 10) -> str:
    """获取日志尾部"""
    if not path.exists():
        return "(日志文件不存在)"
    content = path.read_text()
    log_lines = content.strip().split("\n")
    tail = log_lines[-lines:] if len(log_lines) > lines else log_lines
    return "\n".join(tail)


def get_pid_from_file() -> int | None:
    """从 PID 文件读取 PID"""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def status() -> int:
    print(f"📊 Thunderbox Console v{VERSION} · 服务状态")
    print("=" * 48)

    # 端口状态
    listening = is_port_listening(PORT)
    port_status = "✅ 已监听" if listening else "❌ 未监听"
    print(f"🔌 端口 {PORT}: {port_status}")

    # PID 文件
    pid = get_pid_from_file()
    if pid:
        try:
            os.kill(pid, 0)  # 检测进程是否存在
            print(f"📄 PID 文件: {pid} (进程存在)")
            pid_ok = True
        except ProcessLookupError:
            print(f"📄 PID 文件: {pid} (进程已消失)")
            pid_ok = False
    else:
        print(f"📄 PID 文件: 不存在")
        pid_ok = False

    # 健康检查
    if listening:
        ok, body = check_health(PORT)
        if ok:
            print(f"💚 健康检查: ✅ 通过 ({body.strip()})")
            health_ok = True
        else:
            print(f"💚 健康检查: ❌ 失败 ({body})")
            health_ok = False
    else:
        print(f"💚 健康检查: ⏭️ 跳过（端口未监听）")
        health_ok = False

    # 日志
    log_size = f"{LOG_FILE.stat().st_size / 1024:.1f} KB" if LOG_FILE.exists() else "0 KB"
    print(f"📋 日志文件: {LOG_FILE} ({log_size})")
    tail = get_log_tail(LOG_FILE, 5)
    if tail and tail != "(日志文件不存在)":
        print("   --- 日志尾部 ---")
        for line in tail.split("\n")[-5:]:
            print(f"   {line}")

    print()

    # 综合判断
    if listening and health_ok:
        print(f"✅ 服务正常运行")
        print(f"   访问 http://localhost:{PORT}")
        return 0
    elif listening or pid_ok:
        print(f"⚠️  服务异常")
        return 2
    else:
        print(f"❌ 服务未运行")
        return 1


if __name__ == "__main__":
    sys.exit(status())
