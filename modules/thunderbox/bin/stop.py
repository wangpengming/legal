#!/usr/bin/env python3
"""
Thunderbox Console 停止脚本

三重定位停止：
1. PID 文件 → kill
2. 端口 lsof → kill
3. 进程名 pgrep → kill

用法：
    python3 bin/stop.py
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent.resolve()
PID_FILE = MODULE_ROOT / ".run" / "thunderbox.pid"
PORT = int(os.environ.get("PORT", "18502"))


def stop_by_pid() -> bool:
    """方式1：PID 文件"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            print(f"✅ 已停止（PID 文件）: {pid}")
            return True
        except (ProcessLookupError, ValueError, OSError):
            PID_FILE.unlink()
    return False


def stop_by_port() -> bool:
    """方式2：端口 lsof"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{PORT}"],
            capture_output=True, text=True,
        )
        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"✅ 已停止（端口 {PORT}）: {pid}")
            except ProcessLookupError:
                pass
        return bool(pids)
    except FileNotFoundError:
        # lsof 不可用，尝试 netstat
        try:
            result = subprocess.run(
                ["sh", "-c", f"netstat -tlnp 2>/dev/null | grep ':{PORT}' | awk '{{print $7}}' | cut -d'/' -f1"],
                capture_output=True, text=True,
            )
            pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"✅ 已停止（端口 {PORT}）: {pid}")
                except ProcessLookupError:
                    pass
            return bool(pids)
        except Exception:
            pass
    return False


def stop_by_name() -> bool:
    """方式3：进程名"""
    keywords = ["uvicorn", "thunderbox", "backend.main"]
    stopped = False
    for kw in keywords:
        try:
            result = subprocess.run(
                ["pgrep", "-f", kw],
                capture_output=True, text=True,
            )
            pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"✅ 已停止（进程名 {kw}）: {pid}")
                    stopped = True
                except ProcessLookupError:
                    pass
        except FileNotFoundError:
            pass
    return stopped


def stop() -> int:
    if stop_by_pid():
        return 0
    if stop_by_port():
        return 0
    if stop_by_name():
        return 0
    print("⚠️  未找到运行中的 Thunderbox Console 进程")
    return 1


if __name__ == "__main__":
    sys.exit(stop())
