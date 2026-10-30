#!/usr/bin/env python3
# =============================================
# 启动 case-intelligence 飞书 Bot 常驻服务（长连接默认）
# 后台启动：写 PID + 日志到 .run/，等待心跳新鲜后返回
# 无入站端口（WS 主动外连）；webhook 模式需外部 HTTP server，见 --mode webhook
#
# 凭证：LARK_APP_ID / LARK_APP_SECRET（仅 .env，禁入库，AGENTS §6.2）
# 状态：PID/日志 .run/case-intelligence.bot.{pid,log}；心跳/去重/材料 .run/bot/
# =============================================
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
PID_FILE = RUN_DIR / "case-intelligence.bot.pid"
LOG_FILE = RUN_DIR / "case-intelligence.bot.log"
HEARTBEAT = RUN_DIR / "bot" / "heartbeat"

HEARTBEAT_TIMEOUT = 20  # 秒


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


def _heartbeat_fresh(max_age: float = 90.0) -> bool:
    try:
        return (time.time() - float(HEARTBEAT.read_text().strip())) <= max_age
    except Exception:
        return False


def start() -> bool:
    RUN_DIR.mkdir(exist_ok=True)

    pid = _read_pid()
    if _pid_alive(pid):
        print(f"ℹ️  Bot 已在运行（PID {pid}）")
        return True

    app_id = os.environ.get("LARK_APP_ID") or ""
    app_secret = os.environ.get("LARK_APP_SECRET") or ""
    if not app_id or not app_secret:
        print("❌ 缺少 LARK_APP_ID / LARK_APP_SECRET（写入 .env 后重试；禁入库）")
        return False

    print("=" * 60)
    print("case-intelligence · 飞书 Bot")
    print("=" * 60)
    print(f"通道:     {os.environ.get('LARK_CONNECTION_MODE') or 'websocket'}")
    print(f"引擎:     {os.environ.get('LARK_BOT_ENGINE') or 'minimax'}")
    print(f"PID 文件: {PID_FILE}")
    print(f"日志文件: {LOG_FILE}")
    print("\n启动中...")

    cmd = [_find_python(), str(PROJECT_ROOT / "bin" / "bot_run.py")]
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

    deadline = time.time() + HEARTBEAT_TIMEOUT
    while time.time() < deadline:
        if _heartbeat_fresh(max_age=HEARTBEAT_TIMEOUT):
            print("\n✅ 启动成功（心跳已就绪）")
            print("   停止: python3 bin/bot_stop.py")
            return True
        if proc.poll() is not None:
            print(f"\n❌ 启动失败（进程已退出），请查看日志: {LOG_FILE}")
            if PID_FILE.exists():
                PID_FILE.unlink()
            return False
        time.sleep(0.5)

    print(f"\n❌ 启动超时（{HEARTBEAT_TIMEOUT}s 内无心跳），请查看日志: {LOG_FILE}")
    return False


def main() -> int:
    return 0 if start() else 1


if __name__ == "__main__":
    sys.exit(main())