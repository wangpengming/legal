#!/usr/bin/env python3
# =============================================
# case-intelligence 飞书 Bot 状态检查（SPEC §4.3：进程存活 ∧ 心跳新鲜）
#
# 退出码：0 = 运行中 / 1 = 未运行 / 2 = 异常（进程在但心跳陈旧）
# =============================================
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
LOG_FILE = RUN_DIR / "case-intelligence.bot.log"
PID_FILE = RUN_DIR / "case-intelligence.bot.pid"
HEARTBEAT = RUN_DIR / "bot" / "heartbeat"
STATE_DIR = RUN_DIR / "bot"

HEARTBEAT_MAX_AGE = 90.0  # 秒（worker 每 30s 一跳，容忍 3 跳）


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _heartbeat_age():
    try:
        import time
        return time.time() - float(HEARTBEAT.read_text().strip())
    except Exception:
        return None


def status() -> int:
    print("""
📊 case-intelligence · Bot 服务状态
==================================================""")

    mode = os.environ.get("LARK_CONNECTION_MODE") or "websocket"
    print(f"📡 通道模式: {mode}" + ("（主动外连，无入站端口）" if mode == "websocket" else ""))

    pid = None
    if PID_FILE.exists():
        raw = PID_FILE.read_text().strip()
        pid = int(raw) if raw.isdigit() else None
        print(f"📄 PID 文件: {raw}")
    else:
        print("📄 PID 文件: 无")

    alive = _pid_alive(pid)
    print(f"🧩 进程存活: {'✅ 运行中' if alive else '❌ 未运行'}")

    age = _heartbeat_age()
    if age is None:
        print("💚 心跳: ❌ 无心跳文件")
    else:
        fresh = age <= HEARTBEAT_MAX_AGE
        print(f"💚 心跳: {'✅ 新鲜' if fresh else '⚠️ 陈旧'}（{age:.0f}s 前，阈值 {HEARTBEAT_MAX_AGE:.0f}s）")

    print(f"🗂 状态目录: {STATE_DIR}")

    if LOG_FILE.exists():
        size = LOG_FILE.stat().st_size
        print(f"📋 日志文件: {LOG_FILE} ({size/1024:.1f} KB)")
        lines = LOG_FILE.read_text(errors="ignore").strip().split("\n")
        if lines:
            print("\n--- 最近日志 ---")
            for line in lines[-5:]:
                print(line)
    else:
        print("📋 日志文件: 无")

    print("\n==================================================")

    fresh = age is not None and age <= HEARTBEAT_MAX_AGE
    if alive and fresh:
        print("✅ Bot 正常运行")
        return 0
    if alive:
        print("⚠️  Bot 进程在，但心跳陈旧（可能卡死或断连）")
        print("   建议: python3 bin/bot_restart.py")
        return 2
    print("❌ Bot 未运行")
    print("   启动: python3 bin/bot_start.py")
    return 1


if __name__ == "__main__":
    sys.exit(status())