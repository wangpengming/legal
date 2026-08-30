#!/bin/bash
# Thunderbox Console 启动脚本 wrapper
exec python3 "$(dirname "$0")/start.py" "$@"
