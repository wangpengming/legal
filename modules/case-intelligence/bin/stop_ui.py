#!/usr/bin/env python3
# =============================================
# 停止 case-intelligence Web UI
# 三重定位：PID 文件 → 端口（lsof / netstat）→ 兜底
# 跨平台：Windows 用 taskkill，POSIX 用 SIGTERM
# =============================================
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
PID_FILE = RUN_DIR / "case-intelligence-ui.pid"

PORTS = (18503, 18504)


def _read_pid():
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def _pids_on_port(port: int):
    """按端口查进程号，跨平台尽力而为（lsof / netstat）。"""
    pids = set()
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True,
            ).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
                    pids.add(int(parts[4]))
        except Exception:
            pass
    else:
        for cmd in (["lsof", "-ti", f"tcp:{port}"], ["lsof", "-i", f":{port}", "-t"]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True).stdout
                for tok in out.split():
                    pids.add(int(tok))
                if pids:
                    break
            except Exception:
                continue
    return pids


def _kill(pid: int):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
    return True


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def stop() -> bool:
    pids = set()
    pid = _read_pid()
    if pid:
        pids.add(pid)
    for port in PORTS:
        pids |= _pids_on_port(port)

    if not pids:
        print("ℹ️  未找到运行中的 UI 进程")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True

    for pid in sorted(pids):
        if _kill(pid):
            print(f"✅ 已停止 PID {pid}")
        else:
            print(f"⚠️  PID {pid} 不存在（可能已退出）")

    if PID_FILE.exists():
        PID_FILE.unlink()

    print("✅ 停止完成")
    return True


def main() -> int:
    return 0 if stop() else 1


if __name__ == "__main__":
    sys.exit(main())