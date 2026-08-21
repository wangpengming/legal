#!/usr/bin/env python3
"""
出庭手续生成器 — 全栈启动脚本（FastAPI 后端 + Vite 前端）

健壮性设计原则：
  1. 原子性：PID 先写再 fork，fork 后验证进程真实存在
  2. 等 HTTP 不等端口：端口通 ≠ 服务就绪，必须等 HTTP 响应
  3. 完全脱离终端：start_new_session=True 避免 macOS SIGSTOP
  4. 可独立重启：--backend / --frontend 单独控制
  5. 防螺旋：同一服务连续失败 3 次则停止并报错
  6. 退出码：0=全部就绪 / 1=部分就绪 / 2=启动失败
"""
import os
import sys
import time
import socket
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 路径配置 ──────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
PROJECT_ROOT  = SCRIPT_DIR.parent
BACKEND_ROOT  = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
RUN_DIR       = PROJECT_ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)

BACKEND_PORT   = 8001
FRONTEND_PORT  = 18502

BACKEND_HEALTH   = f"http://localhost:{BACKEND_PORT}/health"
FRONTEND_HEALTH  = f"http://localhost:{FRONTEND_PORT}/"

BACKEND_LOG    = RUN_DIR / "backend.log"
FRONTEND_LOG   = RUN_DIR / "vite.log"
BACKEND_PID    = RUN_DIR / "backend.pid"
FRONTEND_PID   = RUN_DIR / "vite.pid"


# ── 通用工具 ───────────────────────────────────────────────────────────────

def is_port_listening(port: int, timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_http(port: int, path: str = "/", timeout: float = 15) -> bool:
    """等待 HTTP 服务真正响应（不只是端口通）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _http_ping(port, path):
            return True
        time.sleep(0.3)
    return False


def _http_ping(port: int, path: str = "/", timeout: float = 2) -> bool:
    try:
        import urllib.request
        r = urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=timeout)
        return r.status == 200
    except Exception:
        return False


def wait_port_free(port: int, timeout: float = 10) -> bool:
    """等待端口被释放（进程退出后）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_port_listening(port):
            return True
        time.sleep(0.3)
    return False


def find_python() -> str:
    for p in [
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "bin" / "python3",
    ]:
        if p.exists():
            return str(p)
    venv = os.environ.get("VIRTUAL_ENV")
    if venv and (Path(venv) / "bin" / "python").exists():
        return str(Path(venv) / "bin" / "python")
    return str(sys.executable)


def pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.run(["lsof", "-ti", f":{port}"],
                             capture_output=True, text=True).stdout
        return [int(p) for p in out.strip().split() if p.strip()]
    except Exception:
        return []


def kill(pid: int, force: bool = False) -> None:
    try:
        os.kill(pid, 9 if force else 15)
    except OSError:
        pass


def stop_process(pid_path: Path, port: int, name: str) -> None:
    """三重定位停止进程：PID 文件 → 端口 → 残留。"""
    killed = set()

    # 1. PID 文件
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            if pid > 0:
                kill(pid, force=False)
                killed.add(pid)
        except Exception:
            pass

    # 2. 端口上所有进程
    for pid in pids_on_port(port):
        if pid not in killed:
            kill(pid, force=False)
            killed.add(pid)

    # 3. 等待退出
    time.sleep(1)
    # 如果还在，用 SIGKILL
    for pid in list({int(pid_path.read_text().strip())} if pid_path.exists() else set()) + pids_on_port(port):
        if pid > 0:
            kill(pid, force=True)
    pid_path.unlink(missing_ok=True)
    wait_port_free(port, timeout=5)


# ── 服务描述 ────────────────────────────────────────────────────────────────

@dataclass
class Service:
    name: str
    port: int
    pid_path: Path
    log_path: Path
    health_url: str          # 用于 check()
    start_cmd: list[str]     # 子类填充
    cwd: Path = field(default_factory=Path)

    def is_healthy(self) -> bool:
        return _http_ping(self.port, path=self.health_url.split(f":{self.port}")[1])

    def is_port_open(self) -> bool:
        return is_port_listening(self.port)

    def start(self) -> "Service":
        """原子启动：先清旧进程 → 再 fork → 再写 PID（进程已存在则 PID 真实）。"""
        # 1. 停止旧进程（如果存在）
        if self.pid_path.exists():
            try:
                old_pid = int(self.pid_path.read_text().strip())
                if old_pid > 0:
                    kill(old_pid, force=False)
            except Exception:
                pass

        # 2. 等待端口释放
        if self.is_port_open():
            for pid in pids_on_port(self.port):
                kill(pid, force=True)
            wait_port_free(self.port)

        # 3. fork 并启动
        log = open(self.log_path, "wb")
        proc = subprocess.Popen(
            self.start_cmd,
            cwd=str(self.cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 完全脱离终端，避免 macOS SIGSTOP
        )
        log.close()

        # 4. 验证进程真实存在后再写 PID（原子性保证）
        time.sleep(0.3)
        if proc.poll() is not None:
            raise RuntimeError(f"{self.name} 启动后立即退出，请检查日志: {self.log_path}")
        self.pid_path.write_text(str(proc.pid))
        return self

    def wait_ready(self, timeout: float = 15) -> bool:
        """等待服务 HTTP 就绪，返回是否成功。"""
        return wait_http(self.port, path=self.health_url.split(f":{self.port}")[1], timeout=timeout)

    def stop(self) -> None:
        stop_process(self.pid_path, self.port, self.name)


class BackendService(Service):
    def __init__(self):
        python = find_python()
        super().__init__(
            name="FastAPI 后端",
            port=BACKEND_PORT,
            pid_path=BACKEND_PID,
            log_path=BACKEND_LOG,
            health_url=BACKEND_HEALTH,
            cwd=BACKEND_ROOT,
            start_cmd=[
                python, "-m", "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", str(BACKEND_PORT),
            ],
        )


class FrontendService(Service):
    def __init__(self):
        vite_bin = FRONTEND_ROOT / "node_modules" / ".bin" / "vite"
        if not vite_bin.exists():
            raise FileNotFoundError(f"Vite 未找到: {vite_bin}，请先 npm install")
        super().__init__(
            name="Vite 前端",
            port=FRONTEND_PORT,
            pid_path=FRONTEND_PID,
            log_path=FRONTEND_LOG,
            health_url=FRONTEND_HEALTH,
            cwd=FRONTEND_ROOT,
            # health_url path = "/"（首页本身）
            start_cmd=[
                str(vite_bin),
                "--port", str(FRONTEND_PORT),
                "--host", "0.0.0.0",
            ],
        )


# ── 启动协调器 ────────────────────────────────────────────────────────────

def launch_service(svc: Service, retry: int = 3) -> tuple[bool, str]:
    """启动单个服务，失败最多重试 retry 次。返回 (成功, 状态描述)。"""
    for attempt in range(1, retry + 1):
        try:
            svc.start()
        except Exception as e:
            print(f"  ❌ {svc.name} 启动失败: {e}")
            if attempt < retry:
                print(f"     重试 {attempt}/{retry - 1}...")
                time.sleep(2)
            return False, f"启动异常: {e}"

        if svc.wait_ready(timeout=15):
            print(f"  ✅ {svc.name} 就绪 (PID {svc.pid_path.read_text().strip()})")
            return True, "ok"

        print(f"  ⚠️  {svc.name} 端口已开但 HTTP 无响应，尝试重启...")
        svc.stop()
        if attempt < retry:
            print(f"     重试 {attempt}/{retry - 1}...")
            time.sleep(1)

    print(f"  ❌ {svc.name} 连续 {retry} 次启动失败，请检查日志: {svc.log_path}")
    return False, "超时"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="全栈启动脚本")
    parser.add_argument("--backend",  action="store_true", help="仅启动后端")
    parser.add_argument("--frontend", action="store_true", help="仅启动前端")
    parser.add_argument("--restart",  metavar="SVC", choices=["backend", "frontend", "all"],
                        default="all", help="重启目标 (default: all)")
    args = parser.parse_args()

    # 确定需要操作的服务
    do_backend  = args.backend  or args.restart in ("backend", "all")
    do_frontend = args.frontend or args.restart in ("frontend", "all")

    print("=" * 50)
    print("⚖️  出庭手续生成器 · 全栈启动")
    print("=" * 50)
    print()

    # ── 初始化服务对象 ──────────────────────────────────────────────────
    backend  = BackendService()
    frontend = FrontendService()

    results: dict[str, bool] = {}

    # ── 后端 ────────────────────────────────────────────────────────────
    if do_backend:
        if backend.is_healthy():
            print(f"✅ 后端 FastAPI 已健康运行 (PID {backend.pid_path.read_text().strip()})")
            results["backend"] = True
        else:
            print("🚀 启动后端 FastAPI...")
            ok, _ = launch_service(backend)
            results["backend"] = ok
    else:
        print("⏭ 跳过后端")
        results["backend"] = backend.is_healthy()

    # ── 前端 ────────────────────────────────────────────────────────────
    if do_frontend:
        if frontend.is_healthy():
            print(f"✅ 前端 Vite 已健康运行 (PID {frontend.pid_path.read_text().strip()})")
            results["frontend"] = True
        else:
            print("🚀 启动前端 Vite...")
            ok, _ = launch_service(frontend)
            results["frontend"] = ok
    else:
        print("⏭ 跳过前端")
        results["frontend"] = frontend.is_healthy()

    # ── 最终状态 ────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    all_ok = all(results.values())
    if all_ok:
        print("🎉 全栈服务已就绪！")
        print(f"   前端 UI:  http://localhost:{FRONTEND_PORT}/")
        print(f"   后端 API: http://localhost:{BACKEND_PORT}/")
        print(f"   API 文档: http://localhost:{BACKEND_PORT}/docs")
        print()
        print("关闭: python bin/stop.py")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"⚠️  以下服务未就绪: {', '.join(failed)}")
        for name in failed:
            svc = backend if name == "backend" else frontend
            print(f"   → 检查日志: {svc.log_path}")
    print("=" * 50)

    return 0 if all_ok else (1 if any(results.values()) else 2)


if __name__ == "__main__":
    sys.exit(main())
