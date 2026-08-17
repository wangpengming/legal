#!/usr/bin/env python3
# =============================================
# 跨平台停止脚本
# =============================================
# 三重进程定位策略：
# 1. PID 文件
# 2. 端口 (lsof / netstat)
# 3. 进程名匹配 (streamlit run app.py)
# 全部失败时给出手动排查指引
# =============================================
import os
import sys
import signal
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 18501
PID_FILE = PROJECT_ROOT / ".run" / "streamlit.pid"


def find_pid_by_port(port: int) -> int | None:
    """通过端口找 PID（macOS/Linux 用 lsof，Windows 用 netstat）。"""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    return int(parts[-1])
        else:
            out = subprocess.check_output(
                ["lsof", "-ti", f":{port}"], text=True, stderr=subprocess.DEVNULL
            )
            pids = [int(p) for p in out.split() if p.strip()]
            if pids:
                return pids[0]
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    return None


def find_pid_by_name() -> list[int]:
    """通过进程名匹配 streamlit run app.py。"""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["wmic", "process", "where",
                 "CommandLine like '%streamlit run app.py%'",
                 "get", "ProcessId"],
                text=True, stderr=subprocess.DEVNULL,
            )
        else:
            out = subprocess.check_output(
                ["pgrep", "-f", "streamlit run app.py"],
                text=True, stderr=subprocess.DEVNULL,
            )
        return [int(p) for p in out.split() if p.strip().isdigit()]
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return []


def kill_pid(pid: int, force: bool = False) -> bool:
    """杀进程。macOS/Linux 用 SIGTERM（默认）/ SIGKILL（force），Windows 用 taskkill。"""
    try:
        if sys.platform == "win32":
            args = ["taskkill", "/PID", str(pid), "/T"]
            if force:
                args.append("/F")
            subprocess.run(args, check=False, capture_output=True)
        else:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def main() -> None:
    pids_found: set[int] = set()

    # 1. PID 文件
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            pids_found.add(pid)
            print(f"📄 从 PID 文件找到 PID {pid}")
        except ValueError:
            pass

    # 2. 端口
    pid_port = find_pid_by_port(DEFAULT_PORT)
    if pid_port:
        pids_found.add(pid_port)
        print(f"🔌 从端口 {DEFAULT_PORT} 找到 PID {pid_port}")

    # 3. 进程名
    pid_name = find_pid_by_name()
    for p in pid_name:
        pids_found.add(p)
    if pid_name:
        print(f"🔍 从进程名找到 PID {pid_name}")

    if not pids_found:
        print(f"ℹ️ 未发现运行中的 streamlit 服务")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return

    # 杀进程（先 SIGTERM，2 秒后还活着就 SIGKILL）
    print(f"🛑 准备停止 {len(pids_found)} 个进程：{sorted(pids_found)}")
    for pid in pids_found:
        if kill_pid(pid, force=False):
            print(f"   ✅ SIGTERM → PID {pid}")

    time.sleep(2)

    # 二次确认
    survivors = set()
    if PID_FILE.exists():
        try:
            survivors.add(int(PID_FILE.read_text().strip()))
        except ValueError:
            pass
    survivors |= set(find_pid_by_name())
    if find_pid_by_port(DEFAULT_PORT):
        survivors.add(find_pid_by_port(DEFAULT_PORT) or 0)

    survivors &= pids_found  # 只看我们要杀的
    for pid in survivors:
        if kill_pid(pid, force=True):
            print(f"   💥 SIGKILL → PID {pid}")

    # 清理 PID 文件
    if PID_FILE.exists():
        PID_FILE.unlink()
    print("✅ 已停止")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")