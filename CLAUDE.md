# MAS-TS — Agent 自治理规范

> **上位法**: 本文件受 [Athena 系统宪法 v1.4](athena/constitution/v1.4) 约束。冲突时以宪法为准。
> **同步方向**: A → B 单向。本仓库是 Track B 发布源，由上游开发仓库经叙事转化后同步。

## 安全红线（优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将专有文件提交到此仓库
4. 禁止 `gh` CLI 推送到非授权远程

## 宪法优先声明
本配置文件与 Athena 系统宪法冲突时，以宪法为准。
