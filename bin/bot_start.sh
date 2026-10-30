#!/usr/bin/env bash
# macOS / Linux bot start 包裹（bash 3.2 兼容）
set -e
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python || echo "")
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python"
  exit 1
fi
exec "$PY" bin/bot_start.py
