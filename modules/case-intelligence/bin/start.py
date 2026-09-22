#!/usr/bin/env python3
# =============================================
# 跨平台启动脚本（case-intelligence CLI 模块）
# =============================================
# 注意：本模块为 CLI 工具（非 Web 服务），4 件套提供：
#   start   → 初始化 DB + 显示帮助
#   status  → 显示统计摘要
#   stop    → 空操作（CLI 无需后台进程）
#   restart → 空操作
# =============================================
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACT_CLI = PROJECT_ROOT / "bin" / "extract.py"


def main() -> None:
    print("=" * 60)
    print("case-intelligence · 案例智能分析模块")
    print("=" * 60)
    print()
    print("模块类型: CLI 工具（无持久化服务）")
    print("数据库:   data/case_registry.db")
    print()
    print("可用命令:")
    print("  python bin/extract.py register  --name '案件名' --case-number '案号'")
    print("  python bin/extract.py list")
    print("  python bin/extract.py extract  --case-id <id> --type <type> --title '标题'")
    print("  python bin/extract.py promote  --artifact-id <id> --template-name '模板名'")
    print("  python bin/extract.py complete --case-id <id>")
    print("  python bin/extract.py check    --case-number '案号'")
    print("  python bin/extract.py search   --query '关键词'")
    print("  python bin/extract.py report")
    print()
    print("查看详细帮助:")
    print("  python bin/extract.py --help")
    print()
    # 初始化 DB（触发建表）
    print("初始化数据库...")
    result = subprocess.run(
        [sys.executable, str(EXTRACT_CLI), "report"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0 and "case_registry.db" not in result.stderr:
        print(result.stderr, file=sys.stderr)
    print("✅ 就绪")


if __name__ == "__main__":
    main()
