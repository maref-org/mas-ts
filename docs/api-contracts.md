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
| `--card` | `str` | (required) | Path to single Agent Card JSON |
| `--cards-dir` | `str` | `None` | Directory of Agent Cards (batch) |
| `--level` | `str` | `all` | Level: `L0`/`L1`/`L2`/`L3`/`L4`/`all` |
| `--mode` | `str` | `full` | Execution mode: `full` or conditional `escalate` |
| `--converge` | flag | `False` | Run each non-L0 level in a convergence loop |
| `--max-iterations` | `int` | `5` | Maximum iterations per converged level |
| `--convergence-delta` | `float` | `0.5` | Score delta threshold for convergence |
| `--output` | `str` | `None` | Write JSON report to path |
| `--verbose` | flag | `False` | Debug-level logging |

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
| `d2_single_agent` | `run_d2(card, tasks_path)` | Same structure |
| `d3_multi_agent` | `run_d3(card)` | Same structure (auto-skip federation checks for non-federation cards) |
| `d3_multi_agent` | `check_federation_compatibility(card)` | `(score, findings)` — protocol version check |
| `d3_multi_agent` | `check_role_conflicts(card, cards)` | `(score, findings)` — role dedup |
| `d3_multi_agent` | `check_permission_propagation(card)` | `(score, findings)` — scope propagation |
| `d4_governance_security` | `run_d4(card, federation_cards=None)` | Same structure (federated: Governance×0.50 + Security×0.15 + Trust×0.20 + VendorDiv×0.05 + MCPChain×0.10) |
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
| Trust | 0.20 |
| Vendor Diversity | 0.05 |
| MCP Supply Chain | 0.10 |

### `mas_eval.harness`

| Module | Entry Point | Returns |
|--------|-------------|---------|
| `l0_fast_screen` | `run_l0_fast_screen(card)` | `HarnessResult` |
| `l1_standard` | `run_l1_standard(card)` | `HarnessResult` |
| `l2_deep` | `run_l2_deep(card)` | `HarnessResult` |
| `l3_comprehensive` | `run_l3_comprehensive(card)` | `HarnessResult` |
| `l4_evolution` | `run_l4_evolution(card=None, max_epochs=3, convergence_delta=2.0, epoch_state=None, verifier_registry=None)` | `HarnessResult` with epoch metadata |
| `loop_engine` | `ConvergenceLoop(max_iterations=5, convergence_delta=0.5, regression_threshold=-20.0, timeout_seconds=3600, resource_governor=None)` | Iterative harness wrapper returning convergence history |
| `epoch_state` | `EpochState` class | L4 epoch score/findings history with trend and improvement metrics |
| `resource_governor` | `TokenBudget` / `ResourceGovernor` classes | Resource limits and circuit-breaker guard for convergence loops |

`HarnessResult` shape: `{"level": str, "score": float, "grade": str, "verdict": str, "domain_scores": dict, "findings": list}`.

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

## SLO / SLI — Execution Level Performance Targets

| Level | Name | Domains | P50 Duration | P99 Duration | Error Rate Target |
|-------|------|---------|-------------|-------------|-------------------|
| L0 | Fast-Screen | D1+D2+D3 subset | ≤ 5 min | ≤ 10 min | ≤ 1% |
| L1 | Standard | D1-D3 | ≤ 30 min | ≤ 45 min | ≤ 0.5% |
| L2 | Deep | D1-D4 | ≤ 2 h | ≤ 3 h | ≤ 0.5% |
| L3 | Comprehensive | D1-D5 | ≤ 8 h | ≤ 12 h | ≤ 0.5% |
| L4 | Evolution | D5 lifecycle | ≤ 72 h | ≤ 96 h | ≤ 1% |

> **Note**: These are CI-baseline targets for the zero-cost / mock-LLM path. Real LLM inference times will vary by model provider and API latency.
