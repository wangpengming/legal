#!/usr/bin/env python3
"""一键部署脚本：环境检查 + 虚拟环境 + 依赖安装 + 端口验证。

用法：
    python3 bin/setup.py           # 完整部署（创建 .venv + pip + npm）
    python3 bin/setup.py --check   # 仅检查环境，不安装
    python3 bin/setup.py --start   # 部署完成后自动启动服务
"""

import os
import shutil
import subprocess
import sys
import socket
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent
VENV_DIR = MODULE_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
VENV_PIP = VENV_DIR / "bin" / "pip"
FRONTEND_DIR = MODULE_ROOT / "frontend"
REQ_SHARED = MODULE_ROOT / "requirements.txt"
REQ_BACKEND = MODULE_ROOT / "backend" / "requirements.txt"

BACKEND_PORT = 8001
FRONTEND_PORT = 18502
PYTHON_MIN = (3, 10)
NODE_MIN = 18

CHECK_ONLY = "--check" in sys.argv
DO_START = "--start" in sys.argv

# ── 工具函数 ──────────────────────────────────────────

def step(msg: str):
    print(f"\n{'📦' if '安装' in msg else '🔍' if '检查' in msg else '⚙️ '} {msg}")

def ok(msg: str = ""):
    print(f"   ✅ {msg}" if msg else "   ✅ 通过")

def warn(msg: str):
    print(f"   ⚠️  {msg}")

def fail(msg: str):
    print(f"   ❌ {msg}")

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def run(cmd: list, cwd=None, show_output=True) -> bool:
    """运行命令，返回是否成功。"""
    try:
        if show_output:
            result = subprocess.run(cmd, cwd=cwd, check=False)
        else:
            result = subprocess.run(
                cmd, cwd=cwd, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        return result.returncode == 0
    except FileNotFoundError:
        return False

def run_pip(cmd: list) -> bool:
    """在虚拟环境中运行 pip。"""
    return run([str(VENV_PIP)] + cmd, cwd=str(MODULE_ROOT))

# ── 检查步骤 ──────────────────────────────────────────

def check_python():
    step("检查 Python 版本")
    ver = sys.version_info[:2]
    if ver >= PYTHON_MIN:
        ok(f"Python {ver[0]}.{ver[1]}")
        return True
    fail(f"需要 Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]}+，当前 {ver[0]}.{ver[1]}")
    return False

def check_node():
    step("检查 Node.js / npm")
    if shutil.which("node") and shutil.which("npm"):
        try:
            node_ver = subprocess.check_output(["node", "-v"], text=True).strip().lstrip("v")
            npm_ver = subprocess.check_output(["npm", "-v"], text=True).strip()
            major = int(node_ver.split(".")[0])
            if major >= NODE_MIN:
                ok(f"Node {node_ver} / npm {npm_ver}")
                return True
            warn(f"Node {node_ver}（建议 ≥{NODE_MIN}），尝试继续")
            return True
        except Exception:
            pass
    fail("未找到 Node.js 或 npm")
    print("   安装: https://nodejs.org/ （推荐 LTS）")
    print("   或 macOS: brew install node")
    return False

def check_tesseract():
    step("检查 Tesseract OCR（可选）")
    if shutil.which("tesseract"):
        ok("已安装")
        return True
    warn("未安装（拍照扫描功能不可用，其他功能正常）")
    print("   macOS: brew install tesseract tesseract-lang")
    print("   Ubuntu: apt install tesseract-ocr tesseract-ocr-chi-sim")
    return True  # 不影响整体部署

# ── 安装步骤 ──────────────────────────────────────────

def setup_venv():
    step("创建虚拟环境")
    if VENV_DIR.exists():
        if VENV_PYTHON.exists():
            ok(f"已存在: {VENV_DIR}")
            return True
        warn("虚拟环境目录存在但 Python 不完整，重新创建")
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    if not run([sys.executable, "-m", "venv", str(VENV_DIR)]):
        fail("创建虚拟环境失败")
        return False
    ok(f"已创建: {VENV_DIR}")
    return True

def install_python_deps():
    step("安装 Python 依赖")
    if not VENV_PIP.exists():
        fail("虚拟环境不完整，请重新运行")
        return False

    # 升级 pip
    run_pip(["install", "--upgrade", "pip"])

    # 共享依赖
    if REQ_SHARED.exists():
        if not run_pip(["install", "-r", str(REQ_SHARED)]):
            fail("共享依赖安装失败")
            return False
        ok("共享依赖 (requirements.txt)")
    else:
        warn(f"文件不存在: {REQ_SHARED}")

    # 后端依赖
    if REQ_BACKEND.exists():
        if not run_pip(["install", "-r", str(REQ_BACKEND)]):
            fail("后端依赖安装失败")
            return False
        ok("后端依赖 (backend/requirements.txt)")
    else:
        warn(f"文件不存在: {REQ_BACKEND}")

    return True

def install_frontend_deps():
    step("安装前端依赖 (npm install)")
    if not (FRONTEND_DIR / "package.json").exists():
        warn("未找到 frontend/package.json，跳过")
        return True

    if (FRONTEND_DIR / "node_modules").exists():
        ok("node_modules 已存在，跳过 npm install")
        return True

    if not run(["npm", "install"], cwd=str(FRONTEND_DIR)):
        fail("npm install 失败")
        print("   请检查网络连接，或手动执行: cd frontend && npm install")
        return False
    ok("前端依赖安装完成")
    return True

def check_env_file():
    step("检查环境变量配置")
    env_example = MODULE_ROOT / "backend" / ".env.example"
    env_file = MODULE_ROOT / "backend" / ".env"
    if env_file.exists():
        ok(".env 已配置（默认值即可运行，生产环境按需修改）")
        return True
    # .env 已在仓库中，此分支仅用于意外删除后的恢复
    if env_example.exists():
        shutil.copy(env_example, env_file)
        ok(f"已从 .env.example 恢复 .env")
        return True
    warn("未找到 .env.example，跳过")
    return True

def check_ports():
    step("检查端口可用性")
    all_ok = True
    for port, name in [(BACKEND_PORT, "后端"), (FRONTEND_PORT, "前端")]:
        if port_in_use(port):
            warn(f"端口 {port} ({name}) 已被占用")
            all_ok = False
        else:
            ok(f"端口 {port} ({name}) 可用")
    if not all_ok:
        print("   提示: 先运行 python3 bin/stop.py 释放端口")
    return all_ok

# ── 主流程 ────────────────────────────────────────────

def main():
    print("⚖️  出庭手续生成器 · 一键部署")
    print("=" * 50)

    # 阶段 1：环境检查
    checks = [
        check_python(),
        check_node(),
        check_tesseract(),
    ]
    if not all(checks[:2]):  # Python 和 Node 是必须的
        print("\n❌ 必要环境不满足，请先安装后再运行本脚本。")
        sys.exit(1)

    if CHECK_ONLY:
        check_ports()
        print("\n✅ 环境检查完成（--check 模式，未执行安装）。")
        return

    # 阶段 2：安装
    if not all([
        setup_venv(),
        install_python_deps(),
        install_frontend_deps(),
        check_env_file(),
    ]):
        print("\n❌ 部署过程中有失败项，请查看上方错误信息。")
        sys.exit(1)

    check_ports()

    print("\n" + "=" * 50)
    print("✅ 部署完成！")
    print()
    print("   启动服务:")
    print(f"     python3 bin/start.py")
    print(f"   或双击: 启动.command (macOS)")
    print()
    print(f"   前端: http://localhost:{FRONTEND_PORT}")
    print(f"   后端: http://localhost:{BACKEND_PORT}/docs")

    if DO_START:
        print("\n🚀 自动启动服务...")
        subprocess.run([sys.executable, str(MODULE_ROOT / "bin" / "start.py")])

if __name__ == "__main__":
    main()