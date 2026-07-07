# MAS-TS-001 Release Gate Checklist

**版本**: v0.3 | 可执行 12 项发布门禁 (Phase 7.1)

> 对应 `产品级发布全量验收标准与评审流程手册.md` 的五 Gate 模型，精炼为 MAS-TS CLI 项目可执行的 12 项检查。每项检查映射到具体命令或文档化的人工审批。v0.3 追加 G3.4 (UAT signoff, R7 P0) 与 G3.5 (regression baseline, R8 P0)。

---

## 可执行清单

运行 `python3 scripts/release_gate_check.py` 自动检查 G1-G3 自动项；G0/G3.4 项需人工审批。

```
G0.1  manual  Requirements documented              — docs/plans/* 已明确验收标准
G0.2  manual  Architecture/design review           — 设计变更已评审并写入 docs/plans/
G1.1  auto    ruff: 0 errors                       — `python3 -m ruff check mas_eval/ tests/`
G1.2  auto    mypy strict: 0 errors                — `python3 -m mypy mas_eval/ --strict`
G1.3  auto    pytest coverage ≥ 85%                — `python3 -m pytest tests/ --cov=mas_eval --cov-report=term-missing`
G2.1  auto    pytest: 100% passed                  — `python3 -m pytest tests/ -q`
G2.2  auto    Integration tests pass               — `python3 -m pytest tests/test_integration.py -q`
G3.1  auto    bandit SAST: 0 issues                — `python3 -m bandit -r mas_eval -c pyproject.toml -q`
G3.2  auto    pip-audit: 0 Critical/High CVE       — `python3 -m pip_audit --requirement requirements.txt --strict`
G3.3  auto    Secret scan: 0 hardcoded credentials — 内置 regex (AKIA/ghp_/sk-)
G3.4  manual  UAT signoff recorded                 — docs/uat/MAS-TS-001_UAT_Signoff_v0.6.0.md (R7 P0)
G3.5  auto    Regression baseline pass             — `python3 -m pytest tests/test_regression.py -q` (R8 P0)
```

## 使用方式

```bash
# 列出 10 项检查 (不执行)
python3 scripts/release_gate_check.py --list

# 运行所有自动检查并报告 (人工项返回 MANUAL 状态)
python3 scripts/release_gate_check.py

# 人工项已额外审批，仅要求自动项 PASS
python3 scripts/release_gate_check.py --manual-ok

# 检查 12 项中已勾选的数量 (legacy checkbox mode)
grep -c '\[x\]' docs/release-gate.md
# 输出应为 12
```

退出码: `0` = 全部满足；`1` = 有 FAIL 或未审批的 MANUAL 项。

## Gate 分组

### Gate 0 — 需求冻结 (manual)

- [ ] **G0.1** 功能验收标准已明确文档化 — `docs/plans/*` 包含明确定义
- [ ] **G0.2** 架构/设计变更已评审 — 设计记录于 `docs/plans/` 并经维护者评审

### Gate 1 — 代码质量 (auto)

- [ ] **G1.1** ruff: 0 error (CI: `ruff check mas_eval/`)
- [ ] **G1.2** mypy: 0 error (CI: `mypy mas_eval/ --strict --ignore-missing-imports`)
- [ ] **G1.3** 单元测试覆盖率 ≥ 85%

### Gate 2 — 测试通过 (auto)

- [ ] **G2.1** pytest: 100% passed
- [ ] **G2.2** 集成测试：核心链路验证通过

### Gate 3 — 预发验收 (auto + manual)

- [ ] **G3.1** bandit SAST: 0 issues (configured skips: B101/B105/B110/B311/B404/B603/B607)
- [ ] **G3.2** pip-audit: 0 Critical/High CVE
- [ ] **G3.3** 密钥扫描: 0 硬编码凭证 (regex: AKIA / ghp_ / sk-)
- [ ] **G3.4** UAT 签署记录: `docs/uat/MAS-TS-001_UAT_Signoff_v0.6.0.md` 存在且为 Go/Conditional Go (R7 P0)
- [ ] **G3.5** 回归基线对比: `tests/test_regression.py` 全部通过 (R8 P0)

### Gate 4 — 生产发布 (manual + CI)

- [ ] CI 全流程通过 (8 个 workflow: test / type-check / security-scan / check-exfiltration / check-agent-config / check-api-version / check-fail-mode / check-mcp-envelope)
- [ ] 运维文档就绪 (`docs/operations-readiness.md` / Runbook / 升级路径)

> Gate 4 在脚本中未实现为自动检查，因其需要 CI runner 完整运行；在 release 准备阶段由发布管理员单独审批。

## CI 集成

`.github/workflows/test.yml` 已包含：
1. ruff check (G1.1)
2. mypy strict (G1.2)
3. pytest --cov 报告与 85% 阈值检查 (G1.3, G2.1)
4. federation scan (Phase 7.2 阈值政策)

`.github/workflows/security-scan.yml` 已包含：
1. TruffleHog (G3.3 等价)
2. bandit SAST (G3.1)
3. pip-audit (G3.2)
