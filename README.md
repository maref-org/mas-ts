# MAS-TS-001 Evaluation Harness

**Version**: v0.1.0 | **Standard**: MAS-TS-001 v2.1 | **License**: Apache-2.0

Fast-Screen and Full-Run evaluation pipeline for multi-agent systems.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

## Usage

```bash
# Fast-Screen (zero-cost, 5 min)
python mas_fast_screen.py --cards-dir ./mas_eval/data/sample_cards

# Full-Run (5-layer evaluation)
python mas_full_run.py --card ./mas_eval/data/sample_cards/claude_code.json

# Compliance scan
python compliance_scan.py --dir ./mas_eval/data/sample_cards --block

# Mock LLM test
python mock_llm.py --task-file ./mas_eval/data/fast_screen_tasks.json

# Drift calibration
python mock_calibrate.py --golden-dir ./mas_eval/data/golden_trajectories --mock-dir ./mas_eval/data/mock_outputs

# Hardware anchor
python generate_anchor.py --output reports/anchor.json
```

## Architecture

7 standalone scripts + `mas_eval/` package:

| Script | Function | Layers |
|--------|----------|--------|
| `mas_fast_screen.py` | Fast-Screen orchestrator | Layer 1 + Layer 3 (Mock) |
| `mas_full_run.py` | Full-Run 5-layer evaluation | Layer 1-5 |
| `compliance_scan.py` | Static Agent Card scanner | Layer 1 |
| `compliance_sidecar.py` | Runtime proxy interceptor | Runtime |
| `mock_llm.py` | Rule-based LLM simulator | Layer 3 (Mock) |
| `mock_calibrate.py` | Golden trajectory calibration | QA |
| `generate_anchor.py` | Hardware benchmark coefficient | Infra |

## Two Evaluation Systems

This project implements **two independent evaluation frameworks**. Understand their differences before use:

### D1-D5 Domain Evaluation (MAS-TS-001 Standard)

The **primary standard** defined by MAS-TS-001. Evaluates agent capabilities across 5 domains:

| Domain | Name | Weight | Logic |
|--------|------|--------|-------|
| D1 | Compliance | ×0.10 | Schema validation, data residency, constitution checks |
| D2 | Single Agent | ×0.25 | Model quality, tool coverage, task completion |
| D3 | Multi-Agent | ×0.25 | Spawn, protocol, orchestration, isolation, conflict resolution |
| D4 | Governance & Security | ×0.20 | State machine, circuit breaker, audit trail, security |
| D5 | Evolution & Robustness | ×0.20 | Chaos engineering, drift detection, reflection, convergence |

**Usage**: `python scripts/audit_deep_eval.py` or direct domain calls via `mas_eval/domains/`

### L1-L5 Layer Evaluation (Full-Run Mode)

A **reporting-oriented** layered evaluation used by `mas_full_run.py`:

| Layer | Name | Weight | Logic |
|-------|------|--------|-------|
| L1 | Static Audit | ×0.15 | Compliance scan, schema, cross-border, prompt rot |
| L2 | Inference Metrics | ×0.20 | Model quality DB, latency, context window |
| L3 | Action Metrics | ×0.25 | Tool coverage, schema correctness, task coverage |
| L4 | E2E Metrics | ×0.25 | Scenario coverage, auth, dependencies |
| L5 | MAS Dimension | ×0.15 | 6-dimensional MAS readiness assessment |

**Usage**: `python mas_full_run.py --card <card.json>`

### Key Differences

| Aspect | D1-D5 | L1-L5 |
|--------|-------|-------|
| Purpose | Standard compliance assessment | Detailed diagnostic report |
| Scoring | Domain-weighted (0-100) | Layer-weighted (0-100) |
| MAS Logic | D3 uses spawn/protocol/orchestration/isolation/conflict/persistence | L5 uses spawn/isolation/coordination/persistence/scheduling/remote_control |
| Recommendation | Use for official MAS-TS-001 grading | Use for debugging and improvement guidance |

## Test

```bash
pytest tests/ -v           # 122 tests
pytest --cov               # 60% coverage
```

## Docs

Architecture documentation and audit reports: 内部知识库中 Agent 测试平台项目文档
