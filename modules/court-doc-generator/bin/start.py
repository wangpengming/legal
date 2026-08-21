#!/usr/bin/env python3
"""一键启动出庭手续生成器（后端 + 前端）。

用法：
    python3 bin/start.py          # 启动全部
    python3 bin/start.py backend  # 仅启动后端
    python3 bin/start.py frontend # 仅启动前端
"""
import subprocess
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent
BACKEND_BIN = MODULE_ROOT / "backend" / "bin"
FRONTEND_BIN = MODULE_ROOT / "frontend" / "bin"
VENV_PYTHON = MODULE_ROOT / ".venv" / "bin" / "python"

target = sys.argv[1] if len(sys.argv) > 1 else "all"


def find_python():
    """查找可用 Python。"""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


python = find_python()

print("⚖️  出庭手续生成器 v2.0.0")
print("=" * 50)

# 检查虚拟环境
if not VENV_PYTHON.exists():
    print("⚠️  未找到 .venv 虚拟环境")
    print("   创建: python3 -m venv .venv")
    print("   安装: .venv/bin/pip install -r requirements.txt -r backend/requirements.txt")
    sys.exit(1)

# 检查 npm
npm_check = subprocess.run(["which", "npm"], capture_output=True)
if npm_check.returncode != 0:
    print("❌ 未找到 npm，请安装 Node.js")
    sys.exit(1)

errors = []

if target in ("all", "backend"):
    print("\n📡 启动后端 (端口 8001)...")
    r = subprocess.run([python, str(BACKEND_BIN / "start.py")])
    if r.returncode != 0:
        errors.append("backend")

if target in ("all", "frontend"):
    print("\n🎨 启动前端 (端口 18502)...")
    r = subprocess.run([python, str(FRONTEND_BIN / "start.py")])
    if r.returncode != 0:
        errors.append("frontend")

if target == "all":
    print("\n" + "=" * 50)
    time.sleep(2)

    print("\n📊 服务状态:")
    for svc, port, name in [("backend", 8001, "后端 API"), ("frontend", 18502, "前端界面")]:
        subprocess.run([python, str(MODULE_ROOT / svc / "bin" / "status.py")])

    if not errors:
        print("\n✅ 全部启动成功！")
        print(f"   前端: http://localhost:18502")
        print(f"   后端: http://localhost:8001/docs")
        print(f"\n   停止: python3 bin/stop.py")
    else:
        print(f"\n⚠️  部分服务启动失败: {', '.join(errors)}")