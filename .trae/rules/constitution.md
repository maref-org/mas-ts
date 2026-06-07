# Trae AI — Athena 系统宪法约束

**上位法**: 本文件受 [Athena 系统宪法 v1.4-p1](CLAUDE.md#上位法) 约束。冲突时以宪法为准。

## 安全红线（宪法第四-A条 — 优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止添加非授权 remote（pre-commit hook 自动移除）
3. 禁止 `git push` 到非授权远程
4. 禁止 `gh` CLI 推送到非授权 remote
5. 禁止绕过 pre-push hook（`--no-verify`）

## 宪法优先声明
本配置文件与 Athena 系统宪法冲突时，以宪法为准。
