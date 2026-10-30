#!/usr/bin/env python3
# =============================================
# 停止 case-intelligence 飞书 Bot 常驻服务
# 三重定位：PID 文件 → 进程名（bot_run.py，pgrep/wmic）→ 兜底
# 跨平台：Windows 用 taskkill，POSIX 用 SIGTERM
# =============================================
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
PID_FILE = RUN_DIR / "case-intelligence.bot.pid"

# 进程名兜底匹配（唯一标识：本模块的 bot_run.py 绝对路径）
PROCESS_MARKER = str(PROJECT_ROOT / "bin" / "bot_run.py")


def _read_pid():
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def _pids_by_marker():
    """按进程名/命令行定位（POSIX: pgrep -f；Windows: wmic）。"""
    pids = set()
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
                capture_output=True, text=True,
            ).stdout
            for line in out.splitlines():
                if "bot_run.py" in line:
                    tok = line.split()
                    if tok and tok[-1].isdigit():
                        pids.add(int(tok[-1]))
        except Exception:
            pass
    else:
        try:
            out = subprocess.run(
                ["pgrep", "-f", PROCESS_MARKER], capture_output=True, text=True
            ).stdout
            for tok in out.split():
                pids.add(int(tok))
        except Exception:
            pass
    return pids


def _kill(pid: int) -> bool:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
    return True


def stop() -> bool:
    pids = set()
    pid = _read_pid()
    if pid:
        pids.add(pid)
    pids |= _pids_by_marker()

    if not pids:
        print("ℹ️  未找到运行中的 Bot 进程")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True

    for pid in sorted(pids):
        if _kill(pid):
            print(f"✅ 已停止 PID {pid}")
        else:
            print(f"⚠️  PID {pid} 不存在（可能已退出）")

    # 等待优雅退出（SIGTERM → transport.stop）
    for _ in range(20):
        if not any(_pid_alive(p) for p in pids):
            break
        time.sleep(0.25)

    if PID_FILE.exists():
        PID_FILE.unlink()

    print("✅ 停止完成")
    return True


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main() -> int:
    return 0 if stop() else 1


if __name__ == "__main__":
    sys.exit(main())