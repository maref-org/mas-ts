#!/bin/bash
# =============================================================================
# emergency-rollback.sh — 应急回滚脚本 (R6)
#
# 用法: bash scripts/emergency-rollback.sh [--commit <sha>] [--dry-run]
#   --commit <sha>: 指定回滚的 commit (默认 HEAD)
#   --dry-run:      只显示计划，不执行
#
# 步骤:
#   1. 预检 (git 状态 + remote 验证 + 当前分支)
#   2. 备份 (打 tag backup/pre-rollback-<timestamp>)
#   3. Revert (git revert --no-edit)
#   4. 验证 (ruff + pytest 冒烟)
#   5. 摘要 (回滚前后 commit + 验证结果)
#
# 依据: AUDIT_REPORT_v0.1 R6 — ga-promotion-plan Task 3 落地
# 格式参考: scripts/sanitize-for-push.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DRY_RUN=false
TARGET_COMMIT="HEAD"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit)
            TARGET_COMMIT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "用法: bash scripts/emergency-rollback.sh [--commit <sha>] [--dry-run]"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: bash scripts/emergency-rollback.sh [--commit <sha>] [--dry-run]"
            exit 1
            ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo -e "${BLUE}🔧 MAS-TS 应急回滚脚本${NC}"
echo "   仓库: $(basename "$REPO_ROOT")"
echo "   目标 commit: $TARGET_COMMIT"
echo "   模式: $([ "$DRY_RUN" = true ] && echo 'DRY-RUN (仅计划)' || echo 'EXECUTE (执行)')"
echo ""

# ── Step 1: 预检 ──────────────────────────────────────────────────
echo -e "${BLUE}─── 步骤 1: 预检 ───${NC}"

# 1.1 Git 状态检查
GIT_STATUS=$(git status --porcelain 2>/dev/null || true)
if [ -n "$GIT_STATUS" ]; then
    echo -e "${YELLOW}⚠️  工作区有未提交的更改:${NC}"
    echo "$GIT_STATUS" | head -10
    echo -e "${YELLOW}   建议先 stash 或 commit 后再回滚${NC}"
    read -p "继续回滚? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && { echo "已取消"; exit 0; }
else
    echo -e "${GREEN}✅ 工作区干净${NC}"
fi

# 1.2 Remote 验证 (宪法第 4-A 条第 1 项)
REMOTE_CHECK=$(git remote -v 2>/dev/null || true)
if [ -n "$REMOTE_CHECK" ]; then
    echo -e "${YELLOW}⚠️  存在 remote (宪法第 4-A 条要求仅显示授权 remote):${NC}"
    echo "$REMOTE_CHECK"
    echo -e "${YELLOW}   回滚前请确认 remote 为授权 remote${NC}"
else
    echo -e "${GREEN}✅ 无 remote (本地仓库)${NC}"
fi

# 1.3 当前分支与 commit
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo -e "${GREEN}✅ 当前分支: $CURRENT_BRANCH${NC}"
echo -e "${GREEN}✅ 当前 commit: $CURRENT_COMMIT${NC}"

# 1.4 验证目标 commit 存在
if ! git cat-file -e "$TARGET_COMMIT" 2>/dev/null; then
    echo -e "${RED}❌ 目标 commit 不存在: $TARGET_COMMIT${NC}"
    exit 1
fi
TARGET_SHORT=$(git rev-parse --short "$TARGET_COMMIT")
echo -e "${GREEN}✅ 目标 commit 有效: $TARGET_SHORT${NC}"

# Dry-run 模式：仅显示计划
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${BLUE}─── DRY-RUN 模式: 仅显示计划，不执行 ───${NC}"
    echo "   1. 备份 tag: backup/pre-rollback-$(date +%Y%m%d-%H%M%S)"
    echo "   2. 执行:    git revert $TARGET_COMMIT --no-edit"
    echo "   3. 验证:    ruff check + pytest 冒烟 (test_d1 + test_d4)"
    echo "   4. 恢复:    git reset --hard $CURRENT_COMMIT"
    exit 0
fi

# ── Step 2: 备份 ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─── 步骤 2: 备份 ───${NC}"
BACKUP_TAG="backup/pre-rollback-$(date +%Y%m%d-%H%M%S)"
git tag "$BACKUP_TAG"
echo -e "${GREEN}✅ 已创建备份 tag: $BACKUP_TAG${NC}"

# ── Step 3: Revert ────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─── 步骤 3: Revert ───${NC}"
echo "执行: git revert $TARGET_COMMIT --no-edit"
if git revert "$TARGET_COMMIT" --no-edit; then
    NEW_COMMIT=$(git rev-parse --short HEAD)
    echo -e "${GREEN}✅ Revert 完成，新 commit: $NEW_COMMIT${NC}"
else
    echo -e "${RED}❌ Revert 失败 (可能存在冲突)${NC}"
    echo -e "${YELLOW}   解决冲突后 git revert --continue，或放弃: git revert --abort${NC}"
    echo -e "${YELLOW}   备份 tag 仍存在: $BACKUP_TAG${NC}"
    exit 1
fi

# ── Step 4: 验证 (冒烟测试) ───────────────────────────────────────
echo ""
echo -e "${BLUE}─── 步骤 4: 验证 (冒烟测试) ───${NC}"
VERIFY_FAILED=0

# 4.1 Ruff 静态检查
echo "  [1/2] 运行 ruff..."
if python3 -m ruff check mas_eval/ tests/ -q 2>/dev/null; then
    echo -e "${GREEN}  ✅ ruff 通过${NC}"
else
    echo -e "${RED}  ❌ ruff 失败${NC}"
    VERIFY_FAILED=1
fi

# 4.2 Pytest 冒烟 (D1 合规 + D4 安全 子集，快速验证)
echo "  [2/2] 运行 pytest 冒烟 (test_d1_compliance + test_d4_security)..."
if python3 -m pytest tests/test_d1_compliance.py tests/test_d4_security.py -q --timeout=60 2>/dev/null; then
    echo -e "${GREEN}  ✅ pytest 冒烟通过${NC}"
else
    echo -e "${RED}  ❌ pytest 冒烟失败${NC}"
    VERIFY_FAILED=1
fi

# ── Step 5: 摘要 ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─── 步骤 5: 摘要 ───${NC}"
echo "  回滚前 commit:  $CURRENT_COMMIT"
echo "  回滚后 commit:  $NEW_COMMIT"
echo "  备份 tag:       $BACKUP_TAG"
echo "  验证结果:       $([ $VERIFY_FAILED -eq 0 ] && echo '✅ 通过' || echo '❌ 失败')"
echo ""

if [ $VERIFY_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 回滚成功且验证通过${NC}"
    echo "   如需恢复回滚前状态: git reset --hard $BACKUP_TAG"
    echo "   如需查看回滚内容:   git show $NEW_COMMIT"
else
    echo -e "${RED}❌ 回滚完成但验证失败${NC}"
    echo -e "${YELLOW}   建议: 检查验证错误，必要时恢复: git reset --hard $BACKUP_TAG${NC}"
    exit 1
fi
