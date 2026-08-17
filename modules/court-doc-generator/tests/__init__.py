# ============================================================
# 出庭手续生成器 · 单元测试
# ============================================================
# 运行：pytest tests/ -v
# 覆盖率：pytest tests/ --cov=. --cov-report=term-missing
# ============================================================
import os
import sys
from pathlib import Path

# 让 pytest 能直接 import 顶层模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))