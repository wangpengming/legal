#!/usr/bin/env bash
# macOS / Linux 启动包裹（bash 3.2 兼容，不用数组 +=）
set -e
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python || echo "")
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python。请安装 Python 3.10+"
  exit 1
fi
exec "$PY" bin/start.py