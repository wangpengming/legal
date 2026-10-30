#!/usr/bin/env python3
# =============================================
# 停止脚本（case-intelligence · Streamlit Web UI）
# 委托 bin/stop_ui.py：三重定位（PID / 端口 / 兜底）停止
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stop_ui import main as _stop_main  # noqa: E402


if __name__ == "__main__":
    sys.exit(_stop_main())