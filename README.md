# MAS-TS-001 Evaluation Harness

**Version**: v0.1.0 | **Standard**: MAS-TS-001 v2.1 | **License**: CC-BY-SA 4.0

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

## Test

```bash
pytest tests/ -v           # 122 tests
pytest --cov               # 60% coverage
```

## Docs

Architecture documentation and audit reports: `Athena知识库/执行项目/2026/003-open human/.../02-agent 测试平台项目/`
