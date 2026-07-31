# MAS-TS-001 Release Gate Checklist

**版本**: v0.4 | 可执行 15 项发布门禁 (Phase 7.1)

> 对应 `产品级发布全量验收标准与评审流程手册.md` 的五 Gate 模型，精炼为 MAS-TS CLI 项目可执行的 15 项检查。每项检查映射到具体命令或文档化的人工审批。v0.4 追加 G3.6 (SLO error budget, 新增), G3.7 (安全头检测), G3.8 (追踪中间件检测)。

---

## 可执行清单

运行 `python3 scripts/release_gate_check.py` 自动检查 G1-G3 自动项；G0/G3.4 项需人工审批。

```
G0.1  manual  Requirements documented              — docs/plans/* 已明确验收标准
G0.2  manual  Architecture/design review           — 设计变更已评审并写入 docs/plans/
G1.1  auto    ruff: 0 errors                       — `python3 -m ruff check mas_eval/ tests/ api/`
G1.2  auto    mypy strict: 0 errors                — `python3 -m mypy mas_eval/ --strict`
G1.3  auto    pytest coverage ≥ 85%                — `python3 -m pytest tests/ --cov=mas_eval --cov-report=term-missing`
G2.1  auto    pytest: 100% passed                  — `python3 -m pytest tests/ -q`
G2.2  auto    Integration tests pass               — `python3 -m pytest tests/test_integration.py -q`
G3.1  auto    bandit SAST: 0 issues                — `python3 -m bandit -r mas_eval -c pyproject.toml -q`
G3.2  auto    pip-audit: 0 Critical/High CVE       — `python3 -m pip_audit --requirement requirements.txt --strict`
G3.3  auto    Secret scan: 0 hardcoded credentials — 内置 regex (AKIA/ghp_/sk-), TruffleHog CI
G3.4  manual  UAT signoff recorded                 — docs/uat/MAS-TS-001_UAT_Signoff_v0.8.0.md (R7 P0)
G3.5  auto    Regression baseline pass             — `python3 -m pytest tests/test_regression.py -q` (R8 P0)
G3.6  auto    SLO error budget check               — `python3 -c "from mas_eval.scoring.slo import check_slo, reset_slo_state; reset_slo_state(); r=check_slo({'d1_compliance':100}); assert r['overall_pass']"`
G3.7  auto    Security headers present            — `python3 -c "from api.security_headers import SECURITY_HEADERS; assert len(SECURITY_HEADERS) >= 5"`
G3.8  auto    Trace middleware present             — `python3 -c "from api.tracing import TracingMiddleware; assert TracingMiddleware"`
```

## 使用方式

```bash
# 列出 15 项检查 (不执行)
python3 scripts/release_gate_check.py --list

# 运行所有自动检查并报告 (人工项返回 MANUAL 状态)
python3 scripts/release_gate_check.py

# 人工项已额外审批，仅要求自动项 PASS
python3 scripts/release_gate_check.py --manual-ok

# 检查 15 项中已勾选的数量 (legacy checkbox mode, 仅脚本项)
python3 -c "import re, pathlib; t=pathlib.Path('docs/release-gate.md').read_text(); items=re.findall(r'^-\s*\[([ x])\]\s*\*\*(G\d+\.\d+)\*\*', t, re.M); print(f'{sum(1 for s,_ in items if s==\"x\")}/{len(items)} 已勾选')"
# 输出应显示 15/15
```

退出码: `0` = 全部满足；`1` = 有 FAIL 或未审批的 MANUAL 项。

## Gate 分组

### Gate 0 — 需求冻结 (manual)

- [x] **G0.1** 功能验收标准已明确文档化 — `docs/plans/*` 包含明确定义 (确认人: 发布经理，2026-07-31)
- [x] **G0.2** 架构/设计变更已评审 — 设计记录于 `docs/plans/` 并经维护者评审 (确认人: 发布经理，2026-07-31)

### Gate 1 — 代码质量 (auto)

- [ ] **G1.1** ruff: 0 error (CI: `ruff check mas_eval/ tests/ api/`)
- [ ] **G1.2** mypy: 0 error (CI: `mypy mas_eval/ --strict --ignore-missing-imports`)
- [ ] **G1.3** 单元测试覆盖率 ≥ 85%

### Gate 2 — 测试通过 (auto)

- [ ] **G2.1** pytest: 100% passed
- [ ] **G2.2** 集成测试：核心链路验证通过

### Gate 3 — 预发验收 (auto + manual)

- [ ] **G3.1** bandit SAST: 0 issues (configured skips: B101/B105/B110/B311/B404/B603/B607)
- [ ] **G3.2** pip-audit: 0 Critical/High CVE
- [ ] **G3.3** 密钥扫描: 0 硬编码凭证 (regex: AKIA / ghp_ / sk-)
- [x] **G3.4** UAT 签署记录: `docs/uat/MAS-TS-001_UAT_Signoff_v0.8.0.md` 存在且为 Go (R7 P0)，v0.9.0 新增模块已验证通过 (确认人: 发布经理，2026-07-31)
- [ ] **G3.5** 回归基线对比: `tests/test_regression.py` 全部通过 (R8 P0)
- [ ] **G3.6** SLO 错误预算检查: `check_slo` 全部 level 通过
- [ ] **G3.7** 安全头: `api/security_headers.py` ≥ 5 项安全头
- [ ] **G3.8** 追踪中间件: `api/tracing.py` TracingMiddleware 可导入

### Gate 4 — 生产发布 (manual + CI)

- [ ] CI 全流程通过 (11 个 workflow: test / type-check / security-scan / check-exfiltration / check-agent-config / check-api-version / check-fail-mode / check-mcp-envelope / check-remote / codeql / semgrep)
- [ ] 运维文档就绪 (`docs/operations-readiness.md` / Runbook / 升级路径)

> Gate 4 在脚本中未实现为自动检查，因其需要 CI runner 完整运行；在 release 准备阶段由发布管理员单独审批。

## CI 集成

`.github/workflows/test.yml` 已包含：
1. ruff check (G1.1)
2. mypy strict (G1.2)
3. pytest --cov 报告与 85% 阈值检查 (G1.3, G2.1)
4. federation scan (Phase 7.2 阈值政策)
5. 集成测试覆盖率独立测量 (G2.2)

`.github/workflows/security-scan.yml` 已包含：
1. TruffleHog (G3.3 等价)
2. bandit SAST (G3.1)
3. pip-audit (G3.2)
4. CycloneDX SBOM (容器扫描)

## 新增运维能力 (v0.8.3 清债)

| 能力 | 位置 | 说明 |
|------|------|------|
| SLO 可执行化 | `mas_eval/scoring/slo.py` | Prometheus 错误预算 + `/slo-status` 端点 |
| Trace 贯通 | `api/tracing.py` | X-Trace-ID 头 + 日志关联 |
| 运行时限流 | `api/ratelimit.py` | Token bucket rate limiter, 429 响应 |
| 安全头加固 | `api/security_headers.py` | CSP/XFO/XCTO/Permissions/Referrer 5 项 |
| CORS 环境变量化 | `api/server.py` | CORS_ORIGINS env var, 默认空 |
| 错误码映射 | `api/error_codes.py` | 8 种标准化错误码 + HITL 状态机 |
| 上下文窗口管理 | `mas_eval/scoring/context_window.py` | 3 种截断策略 + 利用率检查 |
| 降级框架 | `mas_eval/scoring/degradation.py` | 5 级降级状态机 (normal→blocked) |

## 新增运维能力 (v0.9.0 追加)

| 能力 | 位置 | 门禁项 |
|------|------|--------|
| SLO 门禁可执行化 | `scripts/release_gate_check.py` | G3.6 |
| 安全头门禁可执行化 | `scripts/release_gate_check.py` | G3.7 |
| 追踪门禁可执行化 | `scripts/release_gate_check.py` | G3.8 |
