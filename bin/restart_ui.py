#!/usr/bin/env python3
# =============================================
# 重启 case-intelligence Web UI（先停后启）
# =============================================
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from start_ui import start  # noqa: E402
from stop_ui import stop, PORTS, _port_in_use  # noqa: E402


def restart() -> bool:
    print("🔄 case-intelligence UI 重启")
    print("=" * 60)
    print("\n[1/2] 停止...")
    stop()

    # 等待端口释放（最多 10s）
    for _ in range(20):
        if not any(_port_in_use(p) for p in PORTS):
            break
        time.sleep(0.5)

    print("\n[2/2] 启动...")
    return start()


def main() -> int:
    return 0 if restart() else 1


if __name__ == "__main__":
    sys.exit(main())