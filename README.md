# MAS-TS-001 Evaluation Harness

**Version**: v0.1.0 | **Standard**: MAS-TS-001 v3.0 | **License**: Apache-2.0

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

7 standalone scripts + `mas_eval/` package built on the **D1-D5 × L0-L4 matrix**:

| Script | Function | Levels |
|--------|----------|--------|
| `mas_fast_screen.py` | Fast-Screen orchestrator (CI gate) | D1+D2+D3 subset |
| `mas_full_run.py` | Full-Run, dispatches L0-L4 | L0-L4 |
| `compliance_scan.py` | Static Agent Card scanner | D1 |
| `compliance_sidecar.py` | Runtime proxy interceptor | Runtime |
| `mock_llm.py` | Rule-based LLM simulator (zero-cost) | D2 |
| `mock_calibrate.py` | Golden trajectory calibration | QA |
| `generate_anchor.py` | Hardware benchmark coefficient | Infra |

## Evaluation Model: D1-D5 × L0-L4 Matrix

MAS-TS-001 v3.0 evaluates agents across **5 Domains (D1-D5)** at **5 Execution Levels (L0-L4)**:

### Domains

| Domain | Name | Weight | Evaluates |
|--------|------|--------|-----------|
| D1 | Compliance | ×0.10 | Schema validation, data residency, constitution, DAG acyclicity |
| D2 | Single Agent | ×0.25 | Model quality, tool coverage, task completion, E2E scenarios |
| D3 | Multi-Agent | ×0.25 | Spawn, protocol, orchestration, isolation, conflict, persistence |
| D4 | Governance & Security | ×0.20 | State machine, circuit breaker, oscillation, audit, security |
| D5 | Evolution & Robustness | ×0.20 | Chaos engineering, drift detection, reflection, convergence |

### Execution Levels

| Level | Name | Domains | Duration | Cost |
|-------|------|---------|----------|------|
| L0 | Fast-Screen | D1+D2+D3 subset | <5 min | $0 (zero LLM) |
| L1 | Standard | D1-D3 | ~30 min | Low |
| L2 | Deep | D1-D4 | ~2 h | Medium |
| L3 | Comprehensive | D1-D5 | ~8 h | High |
| L4 | Evolution | D5 lifecycle | Multi-day | Variable |

**Usage**:
```bash
python mas_full_run.py --card <card.json> --level L3
python mas_full_run.py --card <card.json> --level all   # runs L0 → L1 → L2 → L3 → L4
```

## Test

```bash
pytest tests/ -v           # 806 tests
pytest --cov               # 94% coverage
```

## Docs

Architecture documentation and audit reports: 内部知识库中 Agent 测试平台项目文档
