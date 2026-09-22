#!/usr/bin/env python3
# =============================================
# 停止脚本（CLI 模块，无需后台进程）
# =============================================
import sys

def main() -> None:
    print("ℹ️  case-intelligence 为 CLI 工具，无后台进程")
    print("   如需清理数据，请手动操作:")
    print("   - 删除 data/case_registry.db 重置数据库")
    print("   - 删除 data/artifacts/ 清理提取物文件")

if __name__ == "__main__":
    main()
