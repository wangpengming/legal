#!/usr/bin/env bash
# =============================================
# macOS 双击启动入口（双击 .command 文件触发）
# =============================================
# 关键陷阱：双击 .command 文件时，脚本执行完后 Terminal 窗口会立即关闭
# 解决方案：用 `read` 让脚本最后阻塞，等待用户按 Enter 才退出
# =============================================
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python || echo "")

if [ -z "$PY" ]; then
    osascript -e 'display alert "Python 未找到" message "请先安装 Python 3.10+ (https://www.python.org/downloads/)" as critical' 2>/dev/null || true
    echo "❌ 未找到 Python。请先安装 Python 3.10+"
    echo
    echo "按任意键关闭此窗口..."
    read -n 1
    exit 1
fi

"$PY" bin/start.py

echo
echo "✅ 服务已启动。"
echo "浏览器应已跳转到 http://localhost:18501"
echo
echo "关闭服务请运行：bash bin/stop.sh"
echo
echo "按任意键关闭此窗口..."
read -n 1