#!/usr/bin/env bash
# macOS / Linux 状态查询包裹脚本
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python || echo "")
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python"
  exit 1
fi
exec "$PY" bin/status.py