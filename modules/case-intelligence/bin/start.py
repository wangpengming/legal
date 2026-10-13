#!/usr/bin/env python3
# =============================================
# 启动脚本（case-intelligence · Streamlit Web UI）
# 委托 bin/start_ui.py：后台启动 + 写 PID/日志 + 端口就绪等待
# 纯 CLI 操作请用 bin/extract.py（register / scan / search ...）
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from start_ui import main as _start_main  # noqa: E402


if __name__ == "__main__":
    sys.exit(_start_main())