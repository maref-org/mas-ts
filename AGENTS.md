# AGENTS.md — AI Agent Context for MAS-TS-001 (v0.10.0)

> **上位法**: 本文件受 [Athena 系统宪法 v1.5](../CONSTITUTION.md) 和 [MAS-TS 治理框架](GOVERNANCE.md) 共同约束。冲突时以宪法优先，其次以治理框架为准。
> **同步方向**: A → B 单向（Athena 开发源 → GitHub 发布源）。所有变更必须在 Athena 开发源完成后再同步。
> **泄密预防**: 本仓库不得包含 T3/T2 级内容（路径/Key/IP/时间戳/依赖图）。发布前必须经过叙事转化引擎（宪法第九条）处理。反向检查：禁止将内部开发信息（路径/时间戳/组织名）写入公共文档。

## Project Overview

MAS-TS-001 Evaluation Harness evaluates multi-agent systems across 5 domains
(D1-D5) at 5 execution levels (L0-L4). Used for CI gating, compliance auditing,
and capability benchmarking.

## Architecture

```
              mas_fast_screen.py / mas_full_run.py
                         │
            ┌────────────┴────────────┐
            │      mas_eval/          │
            │  ┌──────────────────┐   │
            │  │ domains/ (D1-D5) │   │ ← scoring logic
            │  ├──────────────────┤   │
            │  │ harness/ (L0-L4) │   │ ← execution orchestration
            │  ├──────────────────┤   │
            │  │ scoring/         │   │ ← Elo + absolute grading
            │  └──────────────────┘   │
            └─────────────────────────┘
```

## Key Conventions

- **Domain evaluators** return `{"domain", "score" (0-100), "findings", "subscores"}`
- **Harness runners** return `{"level", "score", "grade", "verdict", "domain_scores", "findings"}`
- **Findings** have `{"severity" (CRITICAL/HIGH/WARNING/INFO), "category", "detail"}`
- **All scores** are floats 0.0-100.0
- **Domain weights**: D1×0.10, D2×0.25, D3×0.25, D4×0.20, D5×0.20

## Agent Card Schema v1.2

Extends v1.1 with optional fields:
- `constitution.envelope` — governance envelope (version, jurisdiction)
- `constitution.health_state` — 4-state health indicator
- `constitution.heartbeat_interval_seconds` — freshness requirement
- `message_format` — protocol + transport specification
- `governance` — state machine + circuit breaker configuration

## File Map

| File | Purpose |
|------|---------|
| `mas_eval/domains/d1_compliance.py` | 10-check static compliance (schema, residency, constitution, DAG) |
| `mas_eval/domains/d2_single_agent.py` | Model quality, tool coverage, task completion, E2E scenarios |
| `mas_eval/domains/d2_step_efficiency.py` | D2 step efficiency sub-domain scoring |
| `mas_eval/domains/d2_trajectory_quality.py` | D2 trajectory quality sub-domain scoring |
| `mas_eval/domains/d2_latency_pressure.py` | D2 latency pressure sub-domain (R4 TTFT P99≤500ms) |
| `mas_eval/domains/d3_multi_agent.py` | Spawn, protocol, orchestration, isolation, conflict, persistence |
| `mas_eval/domains/d3_coordination_efficiency.py` | D3 coordination efficiency sub-domain scoring |
| `mas_eval/domains/d3_plan_quality.py` | D3 plan quality sub-domain scoring |
| `mas_eval/domains/d3_security_interaction.py` | D3 Agent-to-Agent security interaction (cross-agent injection, delegation spoof, tool-scope exploit, coordination attack) |
| `mas_eval/domains/d4_governance_security.py` | StateMachine, CircuitBreaker, Oscillation, Audit, Security scoring, TrustScorer, vendor diversity, MCP supply chain, HITL gate |
| `mas_eval/domains/d4_data_leakage.py` | D4 data leakage detection (covert collection, hidden channels) |
| `mas_eval/domains/d4_injection_detection.py` | D4 prompt-injection detection (direct/indirect vectors, jailbreak resistance, defense-declaration audit) |
| `mas_eval/domains/d4_runtime_consistency.py` | D4 runtime consistency check (undeclared network, cross-border violation, steganography) |
| `mas_eval/domains/d5_robustness.py` | ChaosEngine, DriftDetector, ReflectiveAgent, ConvergenceVerifier, FederationCascade |
| `mas_eval/schemas/agent_card_v1.1.json` | Agent card schema v1.1 (baseline) |
| `mas_eval/schemas/agent_card_v1.2.json` | Agent card schema v1.2 (constitution envelope, health_state) |
| `mas_eval/schemas/agent_card_v2.0.json` | Federation-extended agent card schema (v2.0, with HITL field) |
| `scripts/migrate_agent_card.py` | v1.2→v2.0 card migration tool |
| `mas_eval/harness/l0_fast_screen.py` | 5-stage CI gate runner with Gold Standard threshold checks |
| `mas_eval/harness/l1_standard.py` | D1-D3 aggregation |
| `mas_eval/harness/l2_deep.py` | D1-D4 aggregation with Gold Standard report and certificate |
| `mas_eval/harness/l3_comprehensive.py` | D1-D5 aggregation with Gold Standard report and certificate |
| `mas_eval/harness/l4_evolution.py` | D5 lifecycle runner with MetaEvaluator integration |
| `mas_eval/harness/aggregation.py` | Score aggregation + Gold Standard report computation |
| `mas_eval/harness/sidecar_bridge.py` | Sidecar runtime security bridge — flattens HMAC audit chain, fuses runtime consistency + injection into D4 (Phase 2 v0.8.2) |
| `mas_eval/harness/emergence_harness.py` | Emergence property harness |
| `mas_eval/harness/stress_harness.py` | Stress test harness |
| `mas_eval/harness/trajectory_builder.py` | Trajectory builder for golden vs actual comparison |
| `mas_eval/harness/loop_engine.py` | Convergence loop engine with regression detection |
| `mas_eval/harness/resource_governor.py` | Resource governor for evaluation runs |
| `mas_eval/harness/epoch_state.py` | Epoch state management for L4 lifecycle |
| `mas_eval/scoring/elo.py` | Pairwise Elo rating system |
| `mas_eval/scoring/absolute.py` | Absolute scoring, grading, verdict |
| `mas_eval/scoring/gold_thresholds.py` | Gold Standard L0-L4 threshold matrix (with HITL metrics) |
| `mas_eval/scoring/gold_certificate.py` | Gold Standard certificate generator |
| `mas_eval/scoring/meta_evaluator.py` | Meta-Evaluator: auto_red_team (4 probes incl. adversarial_prompt_mutation) + score_reproducibility_variance |
| `mas_eval/scoring/multi_model.py` | Multi-model evaluation runner |
| `mas_eval/scoring/verifier.py` | Verifier for evaluation results |
| `mas_eval/scoring/attribution.py` | Attribution scoring |
| `mas_eval/scoring/compliance_report.py` | Compliance report generator |
| `mas_eval/scoring/compliance_formatter.py` | Compliance report formatter |
| `mas_eval/scoring/findings.py` | Findings data structure (v1 + v2 attribution) |
| `mas_eval/scoring/regression.py` | Regression baseline comparison tool (5% tolerance) |
| `mas_eval/scoring/standards_mapping.py` | External standards mapping engine (OWASP Agentic / MITRE ATLAS / NIST RMF) |
| `mas_eval/reporting/full_report.py` | Full evaluation report generator |
| `mas_eval/reporting/html_report.py` | HTML report generator |
| `mas_eval/reporting/coverage_report.py` | Coverage report generator |
| `mas_eval/reporting/gold_report.py` | Gold Standard report generator |
| `mas_eval/reporting/dashboard.py` | Dashboard report generator |
| `mas_eval/cross_cutting/cost_efficiency.py` | Cost efficiency cross-cutting metric (CPT, token waste, hitl review cost) |
| `mas_eval/security/hmac_manager.py` | HMAC-SHA256 signing + key rotation + derive_key |
| `mas_eval/oracle/oracle_base.py` | Oracle ABC + OracleRegistry + run_d2_with_oracle |
| `mas_eval/oracle/web_arena.py` | WebArena Oracle with Playwright real browser verification |
| `mas_eval/oracle/swe_bench.py` | SWE-bench Oracle for code task E2E |
| `mas_eval/oracle/tau_bench.py` | Tau-bench Oracle for tool-use E2E |
| `mas_eval/oracle/env.py` | Oracle environment utilities |
| `mas_eval/utils.py` | safe_get / safe_get_in / safe_get_list utilities |
| `mas_eval/data/sample_cards/` | Sample Agent Cards (v1.2 + v2.0) |
| `mas_eval/data/multi_vendor_test/` | 5 real vendor cards + federation scan results |
| `mas_eval/data/golden_trajectories/` | 10 golden trajectory JSON files |
| `mas_eval/data/baselines/v0.6.0_baseline.json` | v0.6.0 regression baseline snapshot |
| `tests/` | 82 test files, 2042 tests (with regression + HITL + latency + agentic-security + runtime-bridge + standards-mapping + API-hardening suites) |
| `.github/workflows/test.yml` | pytest + ruff + coverage gate 85% + Gold L0 gate + federation scan |
| `.github/workflows/security-scan.yml` | TruffleHog + bandit SAST + pip-audit + SBOM CycloneDX (daily cron) |
| `.github/workflows/type-check.yml` | mypy strict type checking |
| `.github/workflows/check-exfiltration.yml` | T3/T2 anti-leak scan (paths/orgs/phones/API keys/timestamps) |
| `.github/workflows/check-mcp-envelope.yml` | MCP envelope fields check (Article 15-A) |
| `.github/workflows/check-api-version.yml` | MCP tool api_version check (Article 15) |
| `.github/workflows/check-fail-mode.yml` | MCP cross-boundary FAIL_MODE check (Article 7) |
| `.github/workflows/check-agent-config.yml` | Agent config constitution reference check (Article 31) |
| `.github/workflows/check-remote.yml` | Remote origin verification pre-push |
| `.github/workflows/codeql.yml` | CodeQL static analysis (weekly) |
| `.github/workflows/semgrep.yml` | Semgrep SAST rule scan (weekly) |
| `scripts/release_gate_check.py` | 15-item release gate runner (G0-G3, with G3.4 UAT + G3.5 regression + G3.6 SLO + G3.7 security-headers + G3.8 tracing) |
| `scripts/gold_standard_gate.py` | Gold Standard L0 threshold gate |
| `scripts/federation_threshold.py` | Multi-vendor federation scan threshold policy |
| `scripts/emergency-rollback.sh` | Emergency rollback script (git revert + verify) |
| `scripts/sanitize-for-push.sh` | Track B pre-push content safety check |
| `scripts/full_audit.sh` | Full audit script |
| `scripts/audit_deep_eval.py` | Deep evaluation audit script |
| `api/server.py` | FastAPI service with /health + /evaluate + /hitl + /metrics + /slo-status endpoints |
| `api/error_codes.py` | 8 standardized error codes + build_error_response factory |
| `api/ratelimit.py` | Token bucket rate limiter middleware (RATE_LIMIT_RATE/RATE_LIMIT_BURST) |
| `api/security_headers.py` | 5 security response headers (CSP/XFO/XCTO/Permissions/Referrer) |
| `api/tracing.py` | X-Trace-ID request/response tracing middleware |
| `mas_eval/scoring/context_window.py` | 3 truncation strategies + context utilization check |
| `mas_eval/scoring/degradation.py` | 5-level degradation state machine (normal→blocked) |
| `mas_eval/scoring/slo.py` | Prometheus SLO error budget + /slo-status endpoint |
| `docs/api-contracts.md` | CLI + Python API contract documentation (with Test Matrix) |
| `docs/release-gate.md` | Release gate checklist (15 items) |
| `docs/operations-readiness.md` | Runbook and ops procedures (8 scenarios) |
| `docs/rtm.yaml` | Requirements Traceability Matrix (RTM) |
| `docs/uat/` | UAT case docs and signoff records |

## Testing

```bash
# Run all tests
pytest tests/ -v           # 2042 tests (82 files)

# Run specific domain
pytest tests/test_d5_robustness.py -v

# Run integration pipeline
pytest tests/test_integration.py -v
```

## D4 Gray-code State Machine

States: INIT(0) → OBSERVE(1) → ANALYZE(3) → PLAN(2) → ACT(6) →
MONITOR(7) → ADAPT(5) → STABILIZE(4) → VERIFY(12) → HALT(13)

- Primary path requires single-bit-flip transitions
- HALT is absorbing
- Entropy follows 0→1→2→3→4→3→2→1→1→0 hump

## D4 Circuit Breaker

- 3 consecutive failures → OPEN
- 30s cooldown → HALF_OPEN
- 2/2 probe success → CLOSED
- Recursion depth >3 → OPEN

## D5 Chaos Engineering

5 infra faults: network_partition, cpu_pressure, memory_pressure, disk_failure, process_kill
5 LLM faults: timeout, hallucination, token_corruption, model_degradation, rate_limiting

## D5 Convergence Cycles

C1: Response consistency (cosine sim ≥0.7)
C2: Self-consistency (≥3/5 agreement)
C3: Task completion (≥80% pass rate)
Score: C1×0.35 + C2×0.35 + C3×0.30

## 治理合规检查清单

每次提交前应确认：

- [x] 无 T3/T2 级内容（路径/Key/IP/时间戳）— rg 扫描零命中
- [x] `git remote -v` 为授权远程 — 无远程（仅本地）
- [x] pre-push hook 已就位
- [x] CI: pytest 通过 — 2042 passed, 0 failed
- [ ] MCP 工具含 `api_version`（第十五条）— 不适用
- [ ] 跨边界 MCP 消息含 `trace_id`/`timestamp`/`source_agent`（第十五-A条）— 不适用
- [ ] 跨边界 MCP 调用有 `FAIL_MODE` 降级（第七条）— 不适用
- [ ] MCP 服务器代码位于正确归属目录（第八条）— 不适用
- [ ] 进入 Track B 前经过叙事转化（第九条）— 不适用
- [x] 不含 T3 级内容（第十一条）— 已扫描确认
- [ ] Agent 已注册、心跳健康（第二十六~二十八条）— 不适用
- [x] 宪法引用路径正确（第三十二条）— AGENTS.md 引用路径正确
