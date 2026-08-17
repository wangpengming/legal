#!/usr/bin/env bash
# macOS / Linux 停止包裹脚本
set -e
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python || echo "")
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python"
  exit 1
fi
exec "$PY" bin/stop.py