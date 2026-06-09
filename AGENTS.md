# AGENTS.md — AI Agent Context for MAS-TS-001

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
| `mas_eval/domains/d3_multi_agent.py` | Spawn, protocol, orchestration, isolation, conflict, persistence |
| `mas_eval/domains/d4_governance_security.py` | StateMachine, CircuitBreaker, Oscillation, Audit, Security scoring |
| `mas_eval/domains/d5_robustness.py` | ChaosEngine, DriftDetector, ReflectiveAgent, ConvergenceVerifier |
| `mas_eval/harness/l0_fast_screen.py` | 5-stage CI gate runner |
| `mas_eval/harness/l1_standard.py` | D1-D3 aggregation |
| `mas_eval/harness/l2_deep.py` | D1-D4 aggregation |
| `mas_eval/harness/l3_comprehensive.py` | D1-D5 aggregation |
| `mas_eval/harness/l4_evolution.py` | D5 lifecycle runner |
| `mas_eval/scoring/elo.py` | Pairwise Elo rating system |
| `mas_eval/scoring/absolute.py` | Absolute scoring, grading, verdict |
| `tests/` | 24 test files, 646+ tests |

## Testing

```bash
# Run all tests
pytest tests/ -v

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

- [ ] 无 T3/T2 级内容（路径/Key/IP/时间戳）
- [ ] `git remote -v` 为授权远程
- [ ] pre-push hook 已就位
- [ ] CI: pytest 通过
- [ ] MCP 工具含 `api_version`（第十五条）
- [ ] 跨边界 MCP 消息含 `trace_id`/`timestamp`/`source_agent`（第十五-A条）
- [ ] 跨边界 MCP 调用有 `FAIL_MODE` 降级（第七条）
- [ ] MCP 服务器代码位于正确归属目录（第八条）
- [ ] 进入 Track B 前经过叙事转化（第九条）
- [ ] 不含 T3 级内容（第十一条）
- [ ] Agent 已注册、心跳健康（第二十六~二十八条）
- [ ] 宪法引用路径正确（第三十二条）
