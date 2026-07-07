#!/usr/bin/env bash
# Track B 红线校验：git remote 白名单 + CD pipeline 禁用
# 依据：审计报告 R1 P0 + 宪法第 4-A 条第 1 项（remote 仅显示授权 remote）+ 红线第 5 条（CD 禁用）
# 用法：pre-push hook（pre-commit install --hook-type pre-push）或 CI step 调用
# 无 remote 时（本地仓库）判 pass 不误报
set -euo pipefail

ALLOWED_REMOTES=("maref-org/mas-ts")
violations=0

# 校验 1：origin remote 必须匹配白名单
remote_output=$(git remote -v 2>/dev/null || true)
if [ -n "$remote_output" ]; then
  while IFS= read -r line; do
    # 行格式：<name> <url> (fetch|push)
    name=$(echo "$line" | awk '{print $1}')
    url=$(echo "$line" | awk '{print $2}')
    [ "$name" = "origin" ] || continue
    ok=0
    for allowed in "${ALLOWED_REMOTES[@]}"; do
      case "$url" in
        *"$allowed"*) ok=1; break ;;
      esac
    done
    if [ "$ok" -ne 1 ]; then
      echo "FAIL: origin remote '$url' not in whitelist (${ALLOWED_REMOTES[*]})" >&2
      violations=$((violations + 1))
    fi
  done <<< "$remote_output"
fi

# 校验 2：cd.yml 必须不存在（Track B 红线第 5 条 CD 禁用）
if [ -f ".github/workflows/cd.yml" ]; then
  echo "FAIL: .github/workflows/cd.yml must be absent (Track B 红线第 5 条 CD 禁用)" >&2
  violations=$((violations + 1))
fi

if [ "$violations" -gt 0 ]; then
  echo "Remote whitelist check failed: $violations violation(s)" >&2
  exit 1
fi

echo "Remote whitelist check passed (origin matches ${ALLOWED_REMOTES[*]}, cd.yml absent)"
exit 0
