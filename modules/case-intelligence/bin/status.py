#!/usr/bin/env python3
# =============================================
# 状态查询脚本
# =============================================
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main() -> None:
    print("📊 case-intelligence · 服务状态")
    print("=" * 50)
    print("类型: CLI 工具（无持久化服务）")
    print()
    # 调用 report 子命令获取统计
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "bin" / "extract.py"), "report"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("⚠️  无法获取统计:", result.stderr[:200])
    print()
    print("🎉 模块就绪")
    print("   运行 python bin/extract.py --help 查看所有命令")

if __name__ == "__main__":
    main()
