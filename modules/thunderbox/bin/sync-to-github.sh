#!/bin/bash
# =============================================================================
# Thunderbox Console — 同步到 legal-thunderbox/
# =============================================================================
# 用途：将本地开发版（modules/thunderbox/）同步到部署源目录
#       /Users/pengming/code/work/me/legal-thunderbox/，然后 push GitHub
#
# 用法：bash bin/sync-to-github.sh [--dry-run] [--force]
#
# ⚠️  注意：
#   - 此脚本会覆盖目标目录中的文件，请确认 git 工作区干净
#   - 目标目录应为 GitHub 仓库，push 前会验证远程配置
#   - 禁止 push 未确认的更改（AGENTS.md §10.3 Push 红线）
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"   # modules/thunderbox/
TARGET_DIR="${LEGAL_THUNDERBOX_TARGET:-/Users/pengming/code/work/me/legal-thunderbox}"

DRY_RUN=""
FORCE=""

# 解析参数
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    --help|-h)
      echo "用法: $0 [--dry-run] [--force]"
      echo "  --dry-run  预览同步内容（不实际复制）"
      echo "  --force    跳过确认直接执行"
      exit 0
      ;;
  esac
done

echo "=============================================="
echo " Thunderbox Console — 同步到 GitHub 部署源"
echo "=============================================="
echo ""

# 1. 检查源目录
if [[ ! -d "$MODULE_DIR" ]]; then
  echo "❌ 源目录不存在: $MODULE_DIR"
  exit 1
fi
echo "📂 源目录: $MODULE_DIR"

# 2. 检查目标目录
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "❌ 目标目录不存在: $TARGET_DIR"
  echo "   请先 clone GitHub 仓库："
  echo "   git clone https://github.com/<owner>/legal-thunderbox.git \"$TARGET_DIR\""
  exit 1
fi
echo "📂 目标目录: $TARGET_DIR"

# 3. 确认 git 工作区干净
cd "$TARGET_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  echo ""
  echo "⚠️  目标目录有未提交的更改："
  git status --short
  echo ""
  if [[ -z "$FORCE" ]]; then
    read -p "继续将覆盖这些文件，是否继续？ [y/N] " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "已取消。"
      exit 0
    fi
  fi
fi

# 4. 检查 git remote
GIT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [[ -z "$GIT_REMOTE" ]]; then
  echo "❌ 目标目录没有配置 git remote（origin）"
  exit 1
fi
echo "🌐 Git remote: $GIT_REMOTE"

# 5. rsync 排除列表（与 .gitignore 保持一致）
RSYNC_OPTS=(
  --archive           # 保留权限、时间戳
  --delete           # 删除目标中不存在于源的文件
)

# 排除项（与 .gitignore 对齐）
EXCLUDES=(
  --exclude='.venv/'
  --exclude='venv/'
  --exclude='__pycache__/'
  --exclude='.pytest_cache/'
  --exclude='.run/'
  --exclude='data/'
  --exclude='data/*'
  --exclude='outputs/'
  --exclude='outputs/*'
  --exclude='.env'
  --exclude='.env.local'
  --exclude='*.db'
  --exclude='*.log'
  --exclude='.DS_Store'
  --exclude='node_modules/'
  --exclude='dist/'
  --exclude='build/'
  --exclude='*.pyc'
  --exclude='*.pyo'
  --exclude='.git/'
)

if [[ -n "$DRY_RUN" ]]; then
  echo ""
  echo "🔍 [DRY-RUN] 预览同步内容（不会实际复制）："
  rsync --dry-run -v "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "$MODULE_DIR/" "$TARGET_DIR/" 2>&1 | head -50
  FILE_COUNT=$(rsync --dry-run -n "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "$MODULE_DIR/" "$TARGET_DIR/" 2>/dev/null | wc -l | tr -d ' ')
  echo ""
  echo "✅ 预览完成，共 ${FILE_COUNT} 个文件/目录将同步"
  exit 0
fi

# 6. 执行同步
echo ""
echo "📦 开始同步（rsync）…"
rsync "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "$MODULE_DIR/" "$TARGET_DIR/"

# 7. 验证同步
SYNCED_FILES=$(rsync --dry-run "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "$MODULE_DIR/" "$TARGET_DIR/" 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "✅ 同步完成"

# 8. 显示变更
cd "$TARGET_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  echo ""
  echo "📋 变更摘要："
  git status --short | head -30
  echo ""

  # 9. Push 提示（⚠️ push 需要用户明确授权）
  echo "=============================================="
  echo " 下一步操作（请逐条确认执行）："
  echo "=============================================="
  echo ""
  echo "  1. cd $TARGET_DIR"
  echo "  2. git add -A"
  echo "  3. git commit -m '[feat] thunderbox-console: sync from legal monorepo'"
  echo "  4. git push origin main"
  echo ""
  echo "  🔴 注意：push 必须用户逐次明确授权，AI 不得擅自 push"
  echo ""
  echo "  建议 commit message："
  echo "  ------------------------------------------------"
  echo "  [feat] thunderbox-console: 完整 MVP 交付 (SPEC-2026-001)"
  echo ""
  echo "  - 后端测试体系 (31 tests) + bin 4件套 + Dockerfile"
  echo "  - HTML 前端 (Dashboard/App List/Wizard/Detail)"
  echo "  - Config Tab + Database Tab + Audit Log"
  echo "  - 审计中间件 (aiosqlite + FastAPI)"
  echo "  ------------------------------------------------"
else
  echo ""
  echo "ℹ️  没有检测到变更（目标目录与源目录完全同步）"
fi

echo ""
echo "✅ sync-to-github.sh 完成"
