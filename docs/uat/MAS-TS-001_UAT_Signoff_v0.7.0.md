# MAS-TS-001 UAT 签署记录 v0.7.0

**版本**: v0.7.0 | **签署日期**: _待填_ | **依据**: AUDIT_REPORT_v0.1_ProductReleaseHandbook.md R7 P0

> 本文档是 MAS-TS-001 v0.7.0 UAT 的正式签署记录。响应审计报告 §11 P0 阻塞项 R7（UAT 缺失，Gate 2 阻塞）。完成签署后，本文件作为 `scripts/release_gate_check.py` G3.4 项的人工审批证据。

---

## 1. UAT 摘要

| 项 | 值 |
|----|----|
| 执行用例数 | 9 |
| 通过数 | 4（技术验证） |
| 失败数 | 0 |
| 阻塞数 | 0 |
| P0 用例通过率 | 4 / 7（UC-01/04/08/09 已通过；UC-02/03/07 待人工执行） |
| P1 用例通过率 | 0 / 2（UC-05/06 待人工执行） |
| UAT 执行周期 | 2026-07-06 ~ _待填_ |

**详细用例**：见 `MAS-TS-001_UAT_v0.7.0.md`

---

## 2. Go/No-Go 决策

请勾选一项：

- [ ] **Go** — 全部 P0 用例通过，可进入 Gate 3 预发验收
- [x] **Conditional Go** — P0 技术验证部分通过（4/7），剩余 3 项 P0 + 2 项 P1 待人工执行，附条件清单（见 §4）
- [ ] **No-Go** — 存在 P0 失败，阻塞发布（见 §5 失败追踪）

**决策理由**：

技术验证 4 项 P0 用例（UC-01/04/08/09）已由 Trae AI 于 2026-07-06 执行通过，覆盖 v0.7.0 新增的 T7（/metrics）和 T8（TTFT 延迟门禁）核心功能。剩余 3 项 P0（UC-02 联邦扫描 / UC-03 HITL API / UC-07 发布门禁）和 2 项 P1（UC-05 Gold 证书 / UC-06 应急回滚）需人工在目标环境执行并签署。

**决策日期**：2026-07-06（技术验证完成日期）

**决策人**：_待填_（发布经理最终签署）

---

## 3. 签署方

| 角色 | 姓名 | 签字 | 日期 |
|------|------|------|------|
| 业务方代表 | _待填_ | _待填_ | _待填_ |
| 技术评估方 | _待填_ | _待填_ | _待填_ |
| 发布经理 | _待填_ | _待填_ | _待填_ |

> 三方签字齐备后本 UAT 记录生效。任一方拒签则视为 No-Go。

---

## 4. 附条件清单（Conditional Go 适用）

仅当 §2 勾选 "Conditional Go" 时填写本节。

| 条件 | 负责人 | 到期日 | 状态 |
|------|--------|--------|------|
| UC-02 联邦扫描稳定性人工执行 | _待填_ | _待填_ | ⏸ 待执行 |
| UC-03 HITL 中断 API 人工执行 | _待填_ | _待填_ | ⏸ 待执行 |
| UC-05 Gold Standard 证书生成人工执行 | _待填_ | _待填_ | ⏸ 待执行 |
| UC-06 应急回滚脚本人工执行 | _待填_ | _待填_ | ⏸ 待执行 |
| UC-07 发布门禁脚本完整通过人工执行 | _待填_ | _待填_ | ⏸ 待执行 |

**条件清除路径**：上述 5 项条件需在 v0.7.0 正式发布前完成。未清除的条件将阻塞 Gate 3 验收。

---

## 5. 失败用例追踪（No-Go 适用）

仅当 §2 勾选 "No-Go" 时填写本节。

| 用例 ID | 失败原因 | 修复方案 | 负责人 | 状态 |
|---------|---------|---------|--------|------|
| _无_ | _不适用_ | _不适用_ | _不适用_ | _不适用_ |

**重新执行计划**：v0.7.0 技术验证无失败用例，无需重新执行。

---

## 6. UAT 环境信息

| 项 | 值 |
|----|----|
| 操作系统 | macOS 26.5.2 (Darwin) |
| Python 版本 | 3.10.20 (homebrew) |
| MAS-TS-001 版本 | v0.7.0 |
| git commit SHA | _待填_ |
| 测试运行命令 | `pytest tests/ -v` |
| 总测试数 | 1798 passed, 1 skipped (playwright), 0 failed |
| 回归测试 | `pytest tests/test_regression.py -v` → 30 passed |
| L3 评估验证 | `mas_full_run.py --level L3` × 3 sample cards 全部成功 |
| L0-L4 全层级验证 | L0/L1/L2/L3/L4 全部可执行（claude_code_v2 sample） |

---

## 7. 附录：UAT 用例 ID 速查

| UC ID | 名称 | 等级 | 关联风险 | 技术验证 |
|-------|------|------|---------|---------|
| UC-01 | D1-D5 全流程评估一致性 | P0 | R8 回归基线 | ✅ 2026-07-06 |
| UC-02 | 联邦扫描稳定性 | P0 | 联邦合规门禁 | ⏸ 待人工执行 |
| UC-03 | HITL 中断 API 可达性 | P0 | R3 HITL | ⏸ 待人工执行 |
| UC-04 | 回归基线对比 | P0 | R8 回归测试套件 | ✅ 2026-07-06 |
| UC-05 | Gold Standard 证书生成 | P1 | R3.4 Gold 阈值 | ⏸ 待人工执行 |
| UC-06 | 应急回滚脚本可执行 | P1 | R6 回滚脚本 | ⏸ 待人工执行 |
| UC-07 | 发布门禁脚本完整通过 | P0 | C1 12 项门禁 | ⏸ 待人工执行 |
| UC-08 | Prometheus /metrics 端点暴露 | P0 | T7 R5 可观测性 | ✅ 2026-07-06 |
| UC-09 | P99 TTFT 延迟门禁 | P0 | T8 R4 性能门禁 | ✅ 2026-07-06 |

---

## 8. v0.7.0 技术验证详情（2026-07-06）

### UC-01: D1-D5 全流程评估一致性
- 执行：`python3 mas_full_run.py --card mas_eval/data/sample_cards/compliant_agent_v2.json --level L3`
- 结果：D1=95.0, D2=22.6, D3=26.0, D4=65.3, D5=74.3, overall=49.6
- 基线对比：与 `v0.7.0_baseline.json` 实测值一致（`compare_with_tolerance` passed=True）

### UC-04: 回归基线对比
- 执行：`pytest tests/test_regression.py -v`
- 结果：30 passed in 0.04s

### UC-08: Prometheus /metrics 端点暴露
- 执行：`pytest tests/test_server.py -v`（含 /metrics 测试）
- 结果：全部通过；`api/metrics.py` 标签基数已修复（T7 代码审查问题 #52）

### UC-09: P99 TTFT 延迟门禁
- 执行：`pytest tests/test_d2_latency_pressure.py -v`
- 结果：全部通过；P99 nearest-rank 计算正确（n=100, index=98）

---

**文档维护**: Trae AI Agent
**生成日期**: 2026-07-06
**依据版本**: AUDIT_REPORT_v0.1_ProductReleaseHandbook.md v1.0
**关联文档**: `MAS-TS-001_UAT_v0.7.0.md`（用例详情）
**前序版本**: `MAS-TS-001_UAT_Signoff_v0.6.0.md`
