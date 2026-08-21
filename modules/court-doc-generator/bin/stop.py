#!/usr/bin/env python3
"""
出庭手续生成器 — 全栈停止脚本。

健壮性：
  - 三重定位：PID 文件 → 端口 → 残留进程
  - SIGTERM → 等待1秒 → SIGKILL
  - 支持单独停止：--backend / --frontend
  - 退出码：0=全部停止 / 1=部分停止
"""
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR    = Path(__file__).parent
PROJECT_ROOT  = SCRIPT_DIR.parent
RUN_DIR       = PROJECT_ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)

BACKEND_PID   = RUN_DIR / "backend.pid"
FRONTEND_PID  = RUN_DIR / "vite.pid"
BACKEND_PORT  = 8001
FRONTEND_PORT = 18502


def pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        ).stdout
        return [int(p) for p in out.strip().split() if p.strip()]
    except Exception:
        return []


def read_pid(path: Path) -> int | None:
    if path.exists():
        try:
            val = int(path.read_text().strip())
            return val if val > 0 else None
        except Exception:
            pass
    return None


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_service(name: str, pid_path: Path, port: int) -> bool:
    """三重定位停止。返回 True=已停止，False=未运行。"""
    pids = set()

    # 1. PID 文件
    p = read_pid(pid_path)
    if p:
        pids.add(p)
        print(f"  📄 [{name}] PID 文件 → {p}")

    # 2. 端口上所有进程
    for p in pids_on_port(port):
        pids.add(p)
    if pids_on_port(port):
        print(f"  🔌 [{name}] 端口 {port} → {pids_on_port(port)}")

    if not pids:
        print(f"  ℹ️  [{name}] 未运行")
        pid_path.unlink(missing_ok=True)
        return True

    # 3. SIGTERM
    print(f"  🛑 [{name}] 停止中: {sorted(pids)}")
    for pid in list(pids):
        os.kill(pid, 15)  # SIGTERM

    # 4. 等待确认
    time.sleep(1.5)
    survivors = [p for p in pids if is_running(p)]
    if survivors:
        print(f"     → 仍存活: {survivors}，SIGKILL")
        for pid in survivors:
            os.kill(pid, 9)  # SIGKILL
        time.sleep(0.5)

    # 5. 清理 PID 文件
    pid_path.unlink(missing_ok=True)

    # 6. 验证端口释放
    if pids_on_port(port):
        print(f"  ⚠️  [{name}] 端口 {port} 仍未释放")
        return False
    print(f"  ✅ [{name}] 已停止")
    return True


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="全栈停止脚本")
    parser.add_argument("--backend",  action="store_true", help="仅停止后端")
    parser.add_argument("--frontend", action="store_true", help="仅停止前端")
    args = parser.parse_args()

    # 默认全停
    do_backend  = not args.frontend  # 既没有 --frontend，也没有 --backend → 全停
    do_frontend = not args.backend
    if args.backend and args.frontend:
        do_backend = do_frontend = False

    print("=" * 50)
    print("🛑 出庭手续生成器 · 全栈停止")
    print("=" * 50)
    print()

    results: list[bool] = []
    if do_backend:
        results.append(stop_service("后端 (FastAPI)", BACKEND_PID, BACKEND_PORT))
        print()
    if do_frontend:
        results.append(stop_service("前端 (Vite)", FRONTEND_PID, FRONTEND_PORT))
        print()

    print("=" * 50)
    if all(results) and len(results) == 2:
        print("✅ 全部服务已停止")
    elif all(results):
        print("✅ 指定服务已停止")
    else:
        print("⚠️  部分服务未停止或端口未释放")
    print("=" * 50)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
