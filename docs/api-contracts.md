# API Contracts — MAS-TS-001 v0.1.0

## CLI Scripts

### `mas_fast_screen.py`

Fast-Screen orchestrator (CI gate, L0).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--cards-dir` | `str` | (required) | Directory containing Agent Card JSON files |
| `--policy` | `str` | `None` | Path to mock policy YAML |
| `--block` | flag | `False` | Exit non-zero on failure |
| `--output` | `str` | `None` | Write JSON report to path |
| `--schemas-dir` | `str` | `None` | Custom schemas directory |
| `-v` / `--verbose` | flag | `False` | Debug-level logging |

Exit code: 0 = PASS, 1 = FAIL (requires `--block`).

### `mas_full_run.py`

Full-Run evaluation pipeline (L0-L4).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--engine` | `str` | `v3` | Engine version |
| `--level` | `str` | `all` | Level: `L0`/`L1`/`L2`/`L3`/`L4`/`all` |
| `--card` | `str` | (required) | Path to single Agent Card JSON unless `--multi-vendor` is used |
| `--tasks` | `str` | `None` | Task definitions JSON path |
| `--output` | `str` | `None` | Write JSON report to path |
| `--source-dir` | `str` | `None` | Agent source code directory for deeper analysis |
| `--multi-vendor` | `list[str]` | `None` | Evaluate multiple agent cards and run federation analysis |
| `--block` | flag | `False` | Exit non-zero if verdict is `BLOCKED` |
| `--compliance-format` | `str` | `none` | Federation compliance report format: `markdown`/`html`/`none` |
| `--mode` | `str` | `full` | Execution mode: `full` or conditional `escalate` |
| `--converge` | flag | `False` | Run each non-L0 level in a convergence loop |
| `--max-iterations` | `int` | `5` | Maximum iterations per converged level |
| `--convergence-delta` | `float` | `0.5` | Score delta threshold for convergence |

Exit code: 0 = PASS, 1 = FAIL.

### `compliance_scan.py`

Static Agent Card compliance scanner (D1).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--card` | `str` | `None` | Single Agent Card path |
| `--dir` | `str` | `None` | Directory of Agent Cards |
| `--schema` | `str` | `None` | Custom schema path |
| `--block` | flag | `False` | Exit non-zero on violation |
| `--output` | `str` | `None` | Write JSON report |
| `-v` / `--verbose` | flag | `False` | Debug-level logging |

### `mock_llm.py`

Rule-based LLM simulator (D2, zero-cost).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--task-file` | `str` | (required) | JSON tasks file path |
| `--card` | `str` | `None` | Single Agent Card path |
| `--cards-dir` | `str` | `None` | Directory of Agent Cards |
| `--block` | flag | `False` | Exit non-zero on failure |

### `mock_calibrate.py`

Golden trajectory calibration (QA).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--golden-dir` | `str` | (required) | Golden trajectories directory |
| `--mock-dir` | `str` | (required) | Mock outputs directory |
| `--threshold` | `float` | `0.8` | Similarity threshold |
| `--output` | `str` | `None` | Write JSON report |

### `generate_anchor.py`

Hardware benchmark coefficient generator.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output` | `str` | `reports/anchor.json` | Output path |

---

## Python API (`mas_eval/`)

### `mas_eval.domains`

| Module | Entry Point | Returns |
|--------|-------------|---------|
| `d1_compliance` | `run_d1(card, schemas_dir)` | `{"domain":"D1","score":float,"findings":list,"subscores":dict}` |
| `d1_compliance` | `check_data_cross_border_chain(card)` | `(score, findings)` — D1.11 federation check |
| `d1_compliance` | `check_federation_version_compat(card)` | `(score, findings)` — D1.12 federation check |
| `d2_single_agent` | `run_d2(card, golden_trajectory=None, mock_trajectory=None, core_tools=None)` | Same structure |
| `d3_multi_agent` | `run_d3(card)` | Same structure (auto-skip federation checks for non-federation cards) |
| `d3_multi_agent` | `check_federation_compatibility(card)` | `(score, findings)` — protocol version check |
| `d3_multi_agent` | `check_role_conflicts(card, cards)` | `(score, findings)` — role dedup |
| `d3_multi_agent` | `check_permission_propagation(card)` | `(score, findings)` — scope propagation |
| `d4_governance_security` | `run_d4(card, federation_cards=None)` | Same structure (federated: Governance×0.50 + Security×0.15 + Trust×0.15 + VendorDiv×0.05 + MCPChain×0.10 + GossipTrust×0.05) |
| `d4_governance_security` | `run_d4_federation(cards)` | `{"domain":"D4","component":"federation","score":float,"subscores":dict,"findings":list}` |
| `d4_governance_security` | `check_trust_score(card)` | `(score, findings)` — 5-dimension TrustScorer |
| `d4_governance_security` | `check_vendor_diversity(cards)` | `(score, findings)` — HHI-adapted |
| `d4_governance_security` | `check_mcp_supply_chain(card)` | `(score, findings)` — MCP server security |
| `d4_governance_security` | `TrustScorer` class | 5-dim trust scoring with trust_transfer decay |
| `d5_robustness` | `run_d5(card=None, seed=42, verifier_registry=None)` | Same structure; optional verifier registry blends D5 convergence scoring |

All return shape: `{"domain": str, "score": float(0-100), "findings": list[Finding], "subscores": dict}`.

### Federation: TrustScorer (`d4_governance_security.TrustScorer`)

5-dimension weighted trust computation:

| Dimension | Weight | Source |
|-----------|--------|--------|
| Integrity | 0.25 | Recent score average (last 3 snapshots) |
| Consistency | 0.20 | 1.0 - score variance (max-min) |
| Compliance | 0.25 | Oracle-sourced evaluation ratio |
| Responsiveness | 0.15 | Update frequency decay (3600s half-life) |
| Reputation | 0.15 | Base `trust_score` from card |

Trust transfer decay: `depth=1→1.0, depth=2→0.7, depth=3→0.4, depth≥4→0.1`.

### Federation: Vendor Diversity

Uses adapted Herfindahl-Hirschman Index (HHI):
```
HHI = Σ(vendor_share × 100)²
Diversity = max(0, 100 × (1 - HHI / 10000))
```

### Federation: D4 Score Weights

| Component | Weight |
|-----------|--------|
| Governance | 0.50 |
| Security | 0.15 |
| Trust | 0.15 |
| Vendor Diversity | 0.05 |
| MCP Supply Chain | 0.10 |
| Gossip Trust | 0.05 |

### `mas_eval.harness`

| Module | Entry Point | Returns |
|--------|-------------|---------|
| `l0_fast_screen` | `run_l0_fast_screen(card, tasks=None)` | `HarnessResult`. `tasks` here is the MockLLM task list, **not** a D2 trajectory alias |
| `l1_standard` | `run_l1_standard(card, golden_trajectory=None, mock_trajectory=None)` | `HarnessResult`. Deprecated kwarg `tasks` aliases `golden_trajectory` and emits `DeprecationWarning` |
| `l2_deep` | `run_l2_deep(card, golden_trajectory=None, mock_trajectory=None, federation_cards=None)` | `HarnessResult`. Deprecated kwarg `tasks` aliases `golden_trajectory` and emits `DeprecationWarning` |
| `l3_comprehensive` | `run_l3_comprehensive(card, golden_trajectory=None, mock_trajectory=None, federation_cards=None)` | `HarnessResult`. Deprecated kwarg `tasks` aliases `golden_trajectory` and emits `DeprecationWarning` |
| `l4_evolution` | `run_l4_evolution(card=None, max_epochs=3, convergence_delta=2.0, epoch_state=None, verifier_registry=None)` | `HarnessResult` with epoch metadata |
| `loop_engine` | `ConvergenceLoop(max_iterations=5, convergence_delta=0.5, regression_threshold=-20.0, timeout_seconds=3600, resource_governor=None)` | Iterative harness wrapper returning convergence history |
| `epoch_state` | `EpochState` class | L4 epoch score/findings history with trend and improvement metrics |
| `resource_governor` | `TokenBudget` / `ResourceGovernor` classes | Resource limits and circuit-breaker guard for convergence loops |

`HarnessResult` shape: `{"level": str, "score": float, "grade": str, "verdict": str, "domain_scores": dict, "findings": list}`.

**`tasks` parameter semantics** (Phase 6.4 clarification):
- `run_l0_fast_screen`: `tasks` is a MockLLM task list injected into stage 5
- `run_l1_standard` / `run_l2_deep` / `run_l3_comprehensive`: `tasks` is a **deprecated alias** for `golden_trajectory`; emits `DeprecationWarning` when used and will be removed in a future release. New callers should pass `golden_trajectory`
- `run_d3` and `_score_orchestration` (D3 internal): `tasks` is an orchestration task-plan dict, unrelated to D2 trajectories

Convergence result shape: `{"final_score": float, "iterations": int, "converged": bool, "stop_reason": str, "score_trajectory": list, "history": list, "findings": list}`.

### `mas_eval.scoring`

| Module | Entry Point | Returns |
|--------|-------------|---------|
| `absolute` | `score_to_grade(score)` | `str` ("A+"/"A"/"B"/"C"/"D"/"F") |
| `absolute` | `grade_to_emoji(grade)` | `str` (emoji) |
| `absolute` | `compute_absolute_score(domain_scores)` | `float` |
| `elo` | `EloRating` class | Pairwise rating system |
| `verifier` | `Verifier`, `MockVerifier`, `VerifierRegistry` | Pluggable verifier governance with cross-validation consensus |

### `mas_eval.oracle`

| Module | Entry Point | Returns |
|--------|-------------|---------|
| `oracle_base` | `OracleRegistry` | Global oracle registry |
| `swe_bench` | `SweBenchOracle` | SWE-bench verification |
| `web_arena` | `WebArenaOracle` | WebArena verification |

---

## Finding Schema

```json
{
  "severity": "CRITICAL|HIGH|WARNING|INFO",
  "category": "string",
  "detail": "string"
}
```

## Agent Card Schema v2.0 (Federation)

Extends v1.2 with federation fields in `mas_eval/schemas/agent_card_v2.0.json`.

| Field | Type | Description |
|-------|------|-------------|
| `vendor_id` | `string` | Vendor identifier for HHI diversity scoring |
| `federation.role` | `enum` | `primary`, `secondary`, `observer` |
| `federation.trust_score` | `float [0,1]` | Baseline reputation |
| `federation.trust_history` | `array[TrustSnapshot]` | Timestamped score history for trend analysis |
| `federation.federation_protocols` | `dict` | MCP/A2A protocol version declarations |
| `federation.allowed_mcp_servers` | `array[string]` | MCP server whitelist (supply chain control) |
| `federation.cross_border_policy` | `dict` | Data residency + transfer zone rules |

### `scripts/migrate_agent_card.py`

Migrates v1.2 cards to v2.0 with default federation stubs:

```bash
python scripts/migrate_agent_card.py input.json output.json
python scripts/migrate_agent_card.py --dir cards/  # batch, in-place
```

## Domain Weights

| Domain | Weight |
|--------|--------|
| D1 (Compliance) | 0.10 |
| D2 (Single Agent) | 0.25 |
| D3 (Multi-Agent) | 0.25 |
| D4 (Governance & Security) | 0.20 |
| D5 (Evolution & Robustness) | 0.20 |

---

## Observability — /metrics 端点（R5 OPS）

### 端点定义

| 方法 | 路径 | 认证 | 响应 Content-Type |
|------|------|------|-------------------|
| GET | `/metrics` | 生产环境建议反向代理 Basic Auth | `text/plain; version=0.0.4; charset=utf-8` |

### 暴露的指标（RED 模型 + 业务指标）

| 指标名 | 类型 | 标签 | 说明 |
|--------|------|------|------|
| `mas_eval_http_requests_total` | Counter | method, endpoint, status | HTTP 请求总数（RED.Rate） |
| `mas_eval_http_request_duration_seconds` | Histogram | method, endpoint | HTTP 请求延迟（RED.Duration），buckets 0.005-10.0s |
| `mas_eval_evaluations_total` | Counter | level, verdict | 评估执行总数（业务指标） |
| `mas_eval_hitl_tasks` | Gauge | state | HITL 任务按状态计数（pending/confirmed/cancelled/paused/awaiting） |

### Prometheus 接入示例

```yaml
scrape_configs:
  - job_name: 'mas-eval'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
```

### SLO 指标说明（RED 模型）

- **Rate**: `rate(mas_eval_http_requests_total[5m])` — 每秒请求数
- **Errors**: `rate(mas_eval_http_requests_total{status=~"5.."}[5m])` — 5xx 错误率
- **Duration**: `histogram_quantile(0.99, rate(mas_eval_http_request_duration_seconds_bucket[5m]))` — P99 延迟

---

## SLO / SLI — Execution Level Performance Targets

| Level | Name | Domains | P50 Duration | P99 Duration | Error Rate Target |
|-------|------|---------|-------------|-------------|-------------------|
| L0 | Fast-Screen | D1+D2+D3 subset | ≤ 5 min | ≤ 10 min | ≤ 1% |
| L1 | Standard | D1-D3 | ≤ 30 min | ≤ 45 min | ≤ 0.5% |
| L2 | Deep | D1-D4 | ≤ 2 h | ≤ 3 h | ≤ 0.5% |
| L3 | Comprehensive | D1-D5 | ≤ 8 h | ≤ 12 h | ≤ 0.5% |
| L4 | Evolution | D5 lifecycle | ≤ 72 h | ≤ 96 h | ≤ 1% |

### SLO 补充 — 首 Token 延迟（TTFT）门禁（R4 — Handbook §4.4.2）

| 指标 | 阈值 | Gold | Silver | Bronze | 来源 |
|------|------|------|--------|--------|------|
| 首 Token 延迟（TTFT）P99 | ≤ 500ms | ≤ 200ms | ≤ 350ms | ≤ 500ms | D2 `latency_pressure` 子域 + `gold_thresholds.py` `d2_ttft_p99` |

> **Note**: These are CI-baseline targets for the zero-cost / mock-LLM path. Real LLM inference times will vary by model provider and API latency.

---

## Test Matrix

测试矩阵映射 MAS-TS-001 评估维度到测试文件与覆盖范围。详细用例数以 `pytest --collect-only` 实测为准，下表中的数字为近似估算。

### 单元测试

| 域 | 测试文件 | 用例数（近似） | 覆盖范围 |
|----|---------|--------------|---------|
| D1 Compliance | tests/test_d1_compliance.py | ~60 | 10-check 静态合规（schema/residency/constitution/DAG） |
| D2 Single Agent | tests/test_d2_single_agent.py | ~80 | 模型质量/工具覆盖/任务完成/E2E 场景 |
| D2 Step Efficiency | tests/test_d2_step_efficiency.py | ~30 | 步骤效率子域 |
| D2 Trajectory Quality | tests/test_d2_trajectory_quality.py | ~30 | 轨迹质量子域 |
| D2 Latency Pressure | tests/test_d2_latency_pressure.py | 14 | TTFT P99 分级评分 Gold/Silver/Bronze/Decay/Critical + 字段回退（R4） |
| D3 Multi-Agent | tests/test_d3_multi_agent.py | ~70 | Spawn/Protocol/Orchestration/Isolation/Conflict/Persistence |
| D3 Plan Quality | tests/test_d3_plan_quality.py | ~25 | 计划质量子域 |
| D3 Coordination Efficiency | tests/test_d3_coordination_efficiency.py | ~25 | 协调效率子域 |
| D4 Governance | tests/test_d4_governance.py | ~80 | StateMachine/CircuitBreaker/Oscillation/Audit |
| D4 Security | tests/test_d4_security.py | ~70 | PenTest/RedBlue/TrustChain/SAST/HITL gate |
| D4 Federation | tests/test_d4_federation.py + tests/test_d3_federation.py | ~40 | TrustScorer/Vendor Diversity/MCP supply chain |
| D4 Data Leakage | tests/test_d4_data_leakage.py | ~25 | 隐蔽采集/隐藏通道检测 |
| D5 Robustness | tests/test_d5_robustness.py | ~90 | ChaosEngine/DriftDetector/ReflectiveAgent/ConvergenceVerifier |
| HITL API + Metrics | tests/test_server.py | ~24 | cancel/confirm/pause 端点 + /metrics 端点 + HITL_STATE_GAUGE 刷新（FastAPI TestClient） |
| Schema v2 | tests/test_schema_v2.py | ~50 | Federation + HITL schema 验证 |
| Regression | tests/test_regression.py | 30 | 基线对比 5% 容差（R8 P0） |

### 集成测试

| 文件 | 用例数（近似） | 覆盖范围 |
|------|--------------|---------|
| tests/test_integration.py | 24 | L0-L3 全链路 |
| tests/test_oracle_integration.py | ~15 | WebArena/SWE-bench/Tau-bench Oracle E2E |
| tests/test_harness_aggregation.py | ~20 | 评分聚合 + Gold 报告 |

### Gold Standard 门禁

| 文件 | 用例数（近似） | 覆盖范围 |
|------|--------------|---------|
| tests/test_gold_standard.py | ~20 | L0-L4 阈值矩阵 + 证书生成 |
| tests/test_release_gate_check.py | ~15 | 12 项发布门禁脚本（G0-G3.5） |
| tests/test_federation_threshold.py | ~10 | 联邦阈值政策 |

### 测试运行命令

```bash
# 全量测试
pytest tests/ -v                              # 1739+ tests

# 仅回归测试（R8 P0）
pytest tests/test_regression.py -v -m regression

# 仅 HITL 相关
pytest tests/test_server.py tests/test_d4_security.py::TestHitlGate tests/test_schema_v2.py::TestSchemaV2Hitl -v

# 发布门禁全量（含 G3.4 UAT + G3.5 regression）
python3 scripts/release_gate_check.py --manual-ok

# 单域快速验证
pytest tests/test_d4_security.py -v -k "HitlGate"
```
