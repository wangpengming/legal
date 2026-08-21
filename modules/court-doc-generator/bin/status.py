#!/usr/bin/env python3
"""出庭手续生成器 — 全栈状态查询脚本（后端 + 前端）。"""
import socket
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RUN_DIR = PROJECT_ROOT / ".run"

BACKEND_PID  = RUN_DIR / "backend.pid"
FRONTEND_PID = RUN_DIR / "vite.pid"
BACKEND_LOG  = RUN_DIR / "backend.log"
FRONTEND_LOG = RUN_DIR / "vite.log"

BACKEND_PORT  = 8001
FRONTEND_PORT = 18502

BACKEND_HEALTH = f"http://localhost:{BACKEND_PORT}/health"


def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False


def read_pid(path: Path) -> int | None:
    if path.exists():
        try:
            return int(path.read_text().strip())
        except Exception:
            pass
    return None


def check_backend_health() -> tuple[bool, str]:
    try:
        import urllib.request
        r = urllib.request.urlopen(BACKEND_HEALTH, timeout=3)
        return True, r.read().decode()
    except Exception as e:
        return False, str(e)


def check_frontend() -> tuple[bool, str]:
    """前端 Vite：必须 HTTP 响应才算健康。"""
    try:
        import urllib.request
        urllib.request.urlopen(f"http://localhost:{FRONTEND_PORT}/", timeout=3)
        return True, "HTML OK"
    except Exception as e:
        return False, str(e)


def log_tail(path: Path, lines: int = 5) -> str:
    if not path.exists():
        return "(无日志)"
    try:
        content = path.read_text()
        all_lines = content.strip().splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail) if tail else "(空)"
    except Exception:
        return "(读取失败)"


def main() -> None:
    print("=" * 60)
    print("📊 出庭手续生成器 · 服务状态")
    print("=" * 60)

    all_ok = True

    # ── 后端 ────────────────────────────────────────────────
    be_listening = is_port_listening(BACKEND_PORT)
    be_pid = read_pid(BACKEND_PID)
    be_health, be_msg = check_backend_health()

    print()
    print(f"【后端】FastAPI  ·  端口 {BACKEND_PORT}")
    print(f"  🔌 端口监听: {'✅ 已监听' if be_listening else '❌ 未监听'}")
    print(f"  📄 PID 文件: {be_pid or '无'}")
    print(f"  💚 健康检查: {'✅ ' + be_msg[:60] if be_health else '❌ ' + be_msg[:60]}")
    if BACKEND_LOG.exists():
        sz = BACKEND_LOG.stat().st_size / 1024
        print(f"  📋 日志: {BACKEND_LOG} ({sz:.0f} KB)")
        for line in log_tail(BACKEND_LOG, 3).splitlines():
            print(f"     {line}")
    if not (be_listening and be_health):
        all_ok = False

    # ── 前端 ────────────────────────────────────────────────
    fe_listening = is_port_listening(FRONTEND_PORT)
    fe_pid = read_pid(FRONTEND_PID)
    fe_ok, fe_msg = check_frontend()

    print()
    print(f"【前端】Vite/React  ·  端口 {FRONTEND_PORT}")
    print(f"  🔌 端口监听: {'✅ 已监听' if fe_listening else '❌ 未监听'}")
    print(f"  📄 PID 文件: {fe_pid or '无'}")
    print(f"  💚 健康检查: {'✅ ' + fe_msg[:60] if fe_ok else '❌ ' + fe_msg[:60]}")
    if FRONTEND_LOG.exists():
        sz = FRONTEND_LOG.stat().st_size / 1024
        print(f"  📋 日志: {FRONTEND_LOG} ({sz:.0f} KB)")
        for line in log_tail(FRONTEND_LOG, 3).splitlines():
            print(f"     {line}")
    if not (fe_listening and fe_ok):
        all_ok = False

    print()
    print("=" * 60)
    if all_ok:
        print("🎉 全栈服务运行正常")
        print(f"   前端 UI: http://localhost:{FRONTEND_PORT}/")
        print(f"   后端 API: http://localhost:{BACKEND_PORT}/")
        print(f"   API 文档: http://localhost:{BACKEND_PORT}/docs")
    else:
        missing = []
        if not be_listening: missing.append(f"后端({BACKEND_PORT})")
        if not be_health: missing.append("后端健康")
        if not fe_listening: missing.append(f"前端({FRONTEND_PORT})")
        if not fe_ok: missing.append("前端健康")
        print(f"⚠️  未就绪: {', '.join(missing)}")
        print("请运行 python bin/start.py 启动服务")
    print("=" * 60)


if __name__ == "__main__":
    main()
