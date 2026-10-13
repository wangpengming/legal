#!/usr/bin/env python3
# =============================================
# 重启脚本（case-intelligence · Streamlit Web UI）
# 委托 bin/restart_ui.py：先停后启
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from restart_ui import main as _restart_main  # noqa: E402


if __name__ == "__main__":
    sys.exit(_restart_main())