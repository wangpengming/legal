#!/usr/bin/env python3
# =============================================
# 状态查询脚本（case-intelligence · Streamlit Web UI）
# 委托 bin/status_ui.py：端口 + PID + /_stcore/health + 日志尾部
# 退出码：0 运行中 / 1 未运行
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from status_ui import status as _status  # noqa: E402


if __name__ == "__main__":
    sys.exit(_status())