#!/usr/bin/env bash
# =============================================
# macOS 双击启动入口
# 逻辑：前后端已运行 → 弹出浏览器；未运行 → 启动服务
# =============================================
cd "$(dirname "$0")"

FRONTEND_URL="http://localhost:18502"

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
    read -n 1
    exit 1
fi

# 检查端口是否监听（返回 0=在监听）
is_port_listening() {
    nc -z localhost "$1" 2>/dev/null
}

echo "🔍 检查服务状态..."
echo

backend_ok=false
frontend_ok=false

if is_port_listening 8001; then
    echo "✅ 后端 FastAPI (8001) 已运行"
    backend_ok=true
else
    echo "⏳ 后端 FastAPI (8001) 未运行"
fi

if is_port_listening 18502; then
    echo "✅ 前端 Vite (18502) 已运行"
    frontend_ok=true
else
    echo "⏳ 前端 Vite (18502) 未运行"
fi

echo

if $backend_ok && $frontend_ok; then
    # 前后端都在，直接开浏览器
    echo "🎉 所有服务就绪，正在打开浏览器..."
    open "$FRONTEND_URL"
    echo "   已打开: $FRONTEND_URL"
elif $frontend_ok || $backend_ok; then
    # 部分服务运行中，先等另一侧启动再开浏览器
    echo "⚙️  部分服务未运行，启动中..."
    "$PY" bin/start.py
    echo
    echo "🌐 正在打开浏览器..."
    open "$FRONTEND_URL"
else
    # 全部未运行
    echo "🚀 启动全栈服务..."
    "$PY" bin/start.py
    echo
    echo "🌐 正在打开浏览器..."
    open "$FRONTEND_URL"
fi

echo
echo "按任意键关闭此窗口..."
read -n 1
