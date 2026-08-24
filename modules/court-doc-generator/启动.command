#!/usr/bin/env bash
# =============================================
# macOS 双击启动入口
# 逻辑：检查服务状态 → 缺失则启动 → 弹出浏览器
# 适用：macOS 双击运行，Terminal 窗口自动打开
#
# 注意：若双击后被编辑器打开（非终端），请右键本文件
#       → 打开方式 → 终端 → 勾选"始终以此方式打开"
# =============================================
set -e
cd "$(dirname "$0")"

BACKEND_PORT=8001
FRONTEND_PORT=18502
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

# 定位 Python
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif [ -x ".venv/bin/python3" ]; then
    PY=".venv/bin/python3"
else
    PY=$(command -v python3 || command -v python || echo "")
fi

if [ -z "$PY" ]; then
    echo "❌ 未找到 Python。请先安装 Python 3.10+"
    echo
    echo "按任意键关闭此窗口..."
    read -r -n 1
    exit 1
fi

# 首次部署：检查虚拟环境，缺失则引导 setup
if [ ! -x ".venv/bin/python" ]; then
    echo "⚠️  未找到虚拟环境 .venv，需要先部署环境"
    echo
    if [ -x "$PY" ]; then
        echo "🔧 正在一键部署..."
        "$PY" bin/setup.py
        echo
    else
        echo "❌ 未找到可用 Python，请安装 Python 3.10+"
        echo "按任意键关闭此窗口..."
        read -r -n 1
        exit 1
    fi
fi

# 检查端口是否监听（返回 0=在监听）
is_port_listening() {
    nc -z localhost "$1" 2>/dev/null
}

echo "🔍 检查服务状态..."
echo

backend_ok=false
frontend_ok=false

if is_port_listening "$BACKEND_PORT"; then
    echo "✅ 后端 FastAPI (${BACKEND_PORT}) 已运行"
    backend_ok=true
else
    echo "⏳ 后端 FastAPI (${BACKEND_PORT}) 未运行"
fi

if is_port_listening "$FRONTEND_PORT"; then
    echo "✅ 前端 Vite (${FRONTEND_PORT}) 已运行"
    frontend_ok=true
else
    echo "⏳ 前端 Vite (${FRONTEND_PORT}) 未运行"
fi

echo

if $backend_ok && $frontend_ok; then
    # 前后端都在 — 直接开浏览器
    echo "🎉 所有服务就绪，正在打开浏览器..."
    open "$FRONTEND_URL"
    echo "   已打开: $FRONTEND_URL"
elif $backend_ok; then
    # 仅后端在 — 只启动前端
    echo "⚙️  后端已运行，仅启动前端..."
    "$PY" bin/start.py frontend
    echo
    echo "🌐 正在打开浏览器..."
    open "$FRONTEND_URL"
elif $frontend_ok; then
    # 仅前端在 — 只启动后端
    echo "⚙️  前端已运行，仅启动后端..."
    "$PY" bin/start.py backend
    echo
    echo "🌐 正在打开浏览器..."
    open "$FRONTEND_URL"
else
    # 全部未运行 — 全量启动
    echo "🚀 启动全栈服务..."
    "$PY" bin/start.py
    echo
    echo "🌐 正在打开浏览器..."
    open "$FRONTEND_URL"
fi

echo
echo "按任意键关闭此窗口..."
read -r -n 1