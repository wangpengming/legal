#!/usr/bin/env python3
# =============================================
# 重启 case-intelligence 飞书 Bot（先停后启）
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot_start import start  # noqa: E402
from bot_stop import stop  # noqa: E402


def restart() -> bool:
    print("🔄 case-intelligence Bot 重启")
    print("=" * 60)
    print("\n[1/2] 停止...")
    stop()
    print("\n[2/2] 启动...")
    return start()


def main() -> int:
    return 0 if restart() else 1


if __name__ == "__main__":
    sys.exit(main())