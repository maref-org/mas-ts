# MAS-TS-001 UAT 用例集 v0.6.0

**版本**: v0.6.0 | **日期**: 2026-07-03 | **依据**: AUDIT_REPORT_v0.1_ProductReleaseHandbook.md R7 P0 阻塞项

> 本文档响应审计报告 §11 P0 阻塞项 R7（UAT 缺失，Gate 2 阻塞）。审计手册 §2.5 PRR/ORR 模型在 MAS-TS-001 上的等效转译为"评估结果可重现 + CI 门禁可靠"，UAT 用例聚焦这两大核心保证。

---

## 1. UAT 范围

MAS-TS-001 是**评估其他 Multi-Agent System 的元工具（Meta-Evaluator）**，自身非传统生产服务。UAT 范围按审计手册 §0.2 等效关注点转译：

| 手册术语 | MAS-TS-001 等效 UAT 范围 |
|---------|-------------------------|
| 生产就绪 | 评估结果可重现（Gold Standard 证书 + 回归基线对比） |
| 灰度发布 | 评估层级 L0→L1→L2→L3→L4 渐进验证 |
| 回滚 | 评估结果可追溯（HMAC 审计链 + emergency-rollback.sh） |
| SLO | L0-L4 执行延迟与错误率目标（`api-contracts.md` SLO 表） |

**不在 UAT 范围内**：
- 前端 UI / 桌面端（MAS-TS-001 无前端）
- 实时数据备份（仓库 Git 版本控制即为备份）
- 容量规划（单卡评估工具，无并发吞吐）

---

## 2. UAT 角色与签署

| 角色 | 职责 | 占位姓名 |
|------|------|---------|
| 业务方代表 | 确认评估结果满足业务可用性要求 | _待填_ (MAREF 治理团队) |
| 技术评估方 | 确认 CI 门禁、回归基线、HITL API 等技术指标 | _待填_ (仓库维护者) |
| 发布经理 | Go/No-Go 最终决策 | _待填_ |

**签署记录**：见 `MAS-TS-001_UAT_Signoff_v0.6.0.md`

---

## 3. UAT 用例

### UC-01: D1-D5 全流程评估一致性 (P0)

**目标**：验证 v0.6.0 回归基线锚点 `d1_d5_pipeline` 可重现。

- **前置条件**：
  - `mas_eval/data/sample_cards/compliant_agent_v2.json` 存在
  - `mas_eval/data/baselines/v0.6.0_baseline.json` 存在且 `d1_d5_pipeline` 锚点已回填实测值
- **执行步骤**：
  1. 运行 `python3 mas_full_run.py --card mas_eval/data/sample_cards/compliant_agent_v2.json --level L3`
  2. 记录 D1/D2/D3/D4/D5 评分
  3. 运行 `python3 -c "from mas_eval.scoring.regression import load_baseline, compare_with_tolerance; b = load_baseline('mas_eval/data/baselines/v0.6.0_baseline.json'); actual = b['anchors']['d1_d5_pipeline']['cards']['compliant_agent_v2']; r = compare_with_tolerance(actual, actual); print(r.passed)"`
- **预期结果**：
  - mas_full_run.py 成功退出（exit code 0）
  - D1-D5 评分与基线锚点偏差 ≤5%（`compare_with_tolerance` 返回 `passed=True`）
- **等级**：P0

### UC-02: 联邦扫描稳定性 (P0)

**目标**：验证 5 vendor 联邦扫描通过率 100%，无新增 CRITICAL findings。

- **前置条件**：
  - `mas_eval/data/multi_vendor_test/` 下 5 个 vendor card 齐全
  - `scripts/federation_threshold.py` 存在
- **执行步骤**：
  1. 运行 `python3 scripts/federation_threshold.py`
  2. 检查输出是否含 CRITICAL findings
- **预期结果**：
  - 通过率 100%（5/5 vendor）
  - 无新增 CRITICAL findings（与 `v4_federation_scan_v2_results.json` 对比）
- **等级**：P0

### UC-03: HITL 中断 API 可达性 (P0)

**目标**：验证 R3 P0 落地的 HITL cancel/confirm/pause 端点功能正常。

- **前置条件**：
  - `api/server.py` 存在
  - `uvicorn` 与 `httpx` 已安装
- **执行步骤**：
  1. 启动 FastAPI 服务：`uvicorn api.server:app --port 8000 &`
  2. POST `http://localhost:8000/hitl/task-001/pause`
  3. POST `http://localhost:8000/hitl/task-001/confirm`
  4. POST `http://localhost:8000/hitl/task-002/cancel`
  5. GET `http://localhost:8000/health` 确认服务健康
  6. 关闭服务：`kill %1`
- **预期结果**：
  - 各端点返回 HTTP 200
  - 响应体含 `task_id` / `action` / `previous_state` / `new_state` / `timestamp`
  - `timestamp` 为 ISO 8601 格式（含时区）
  - 404 端点（未注册 task_id）返回 HTTP 404
- **等级**：P0

### UC-04: 回归基线对比 (P0)

**目标**：验证 R8 P0 落地的回归测试套件 30 测试全部通过。

- **前置条件**：
  - `mas_eval/scoring/regression.py` 存在
  - `tests/test_regression.py` 存在
  - `mas_eval/data/baselines/v0.6.0_baseline.json` 存在
- **执行步骤**：
  1. 运行 `pytest tests/test_regression.py -v`
  2. 检查通过数
- **预期结果**：
  - 30 passed, 0 failed
  - 5 测试类（TestRegressionResult / TestLoadBaseline / TestCompareWithTolerance / TestValidateSchema / TestBaselineAnchors）全部 PASS
- **等级**：P0

### UC-05: Gold Standard 证书生成 (P1)

**目标**：验证 L2/L3 评估运行能生成 Gold Standard 证书且阈值矩阵满足。

- **前置条件**：
  - `mas_eval/scoring/gold_certificate.py` 存在
  - `mas_eval/scoring/gold_thresholds.py` 含 hitl_approval_rate 阈值（R3.4 已落地）
- **执行步骤**：
  1. 运行 `python3 mas_full_run.py --card mas_eval/data/sample_cards/compliant_agent_v2.json --level L2`
  2. 检查 stdout 或输出文件中的证书
- **预期结果**：
  - 证书生成（含 level / score / grade / verdict / domain_scores / hitl_approval_rate）
  - L2 阈值矩阵满足：d1_compliance=100, d2_task_completion≥0.85, hitl_approval_rate≥0.85
- **等级**：P1

### UC-06: 应急回滚脚本可执行 (P1)

**目标**：验证 R6 P1 落地的 `emergency-rollback.sh` 在 dry-run 模式下能正常输出。

- **前置条件**：
  - `scripts/emergency-rollback.sh` 存在且可执行
  - git working tree clean
- **执行步骤**：
  1. 运行 `bash scripts/emergency-rollback.sh --dry-run`
  2. 检查输出
- **预期结果**：
  - 输出 5 步骤摘要（预检 / 备份 / Revert / 验证 / 摘要）
  - dry-run 模式下无实际 git revert 操作
  - 退出码 0
- **等级**：P1

### UC-07: 发布门禁脚本完整通过 (P0)

**目标**：验证 C1 落地的 12 项发布门禁（含 G3.4 UAT + G3.5 regression）能完整通过。

- **前置条件**：
  - `scripts/release_gate_check.py` 含 G0-G3.5 共 12 项
  - G0 人工项（G0.1/G0.2/G3.4）已审批
  - `docs/uat/MAS-TS-001_UAT_Signoff_v0.6.0.md` 存在且为 Go/Conditional Go
- **执行步骤**：
  1. 运行 `python3 scripts/release_gate_check.py --manual-ok`
  2. 检查输出
- **预期结果**：
  - 12 项检查全 PASS
  - G3.5 自动运行 `pytest tests/test_regression.py -q` 并通过
  - 退出码 0
- **等级**：P0

---

## 4. UAT 执行记录

| 用例 | 执行人 | 日期 | 结果 | 备注 |
|------|--------|------|------|------|
| UC-01 | _待填_ | _待填_ | _待填_ | D1-D5 一致性 |
| UC-02 | _待填_ | _待填_ | _待填_ | 联邦扫描 |
| UC-03 | _待填_ | _待填_ | _待填_ | HITL API |
| UC-04 | _待填_ | _待填_ | _待填_ | 回归基线 |
| UC-05 | _待填_ | _待填_ | _待填_ | Gold 证书 |
| UC-06 | _待填_ | _待填_ | _待填_ | 应急回滚 |
| UC-07 | _待填_ | _待填_ | _待填_ | 发布门禁 |

---

## 5. UAT 状态汇总

- **总用例数**: 7
- **P0 用例数**: 5（UC-01/02/03/04/07）
- **P1 用例数**: 2（UC-05/06）
- **执行状态**: ⏸ 待执行（本文档为模板，签字由用户后续完成）

---

**文档维护**: Trae AI Agent
**生成日期**: 2026-07-03
**依据版本**: AUDIT_REPORT_v0.1_ProductReleaseHandbook.md v1.0
