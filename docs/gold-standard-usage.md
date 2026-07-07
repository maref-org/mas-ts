# Gold Standard Usage Guide

This guide explains how to use the Gold Standard features in MAS-TS-001 v3.0-GA.

## Overview

The Gold Standard provides enhanced evaluation capabilities with:
- **Gold Standard Report**: Comprehensive evaluation with cross-cutting metrics (Consistency Index, Cost Efficiency)
- **Gold Standard Certificate**: Official certification badge for compliant agents
- **Meta-Evaluator**: Self-assessment of evaluation quality (L4 only)
- **Threshold Checks**: Level-specific compliance thresholds (L0-L4)

## L0: Fast-Screen

L0 includes automatic threshold checks against Gold Standard requirements.

```python
from mas_eval.harness.l0_fast_screen import run_l0_fast_screen

result = run_l0_fast_screen(card)

# Access threshold check results
threshold_check = result["threshold_check"]
print(f"L0 compliance: {threshold_check['overall_pass']}")
```

The threshold check validates:
- `d1_compliance`: ≥ 100 (required)
- `d2_step_efficiency`: ≥ 0.50
- `d2_tool_coverage`: ≥ 60
- `d3_spawn_rate`: ≥ 95

## L2: Deep Evaluation

L2 generates a Gold Standard report and certificate.

```python
from mas_eval.harness.l2_deep import run_l2_deep

result = run_l2_deep(
    card,
    golden_trajectory=expected_trajectory,
    mock_trajectory=actual_trajectory
)

# Access Gold Standard results
gold_standard = result["gold_standard"]
print(f"Consistency Index: {gold_standard['consistency_index']}")
print(f"Cost Efficiency: {gold_standard['cost_efficiency']}")

# Access certificate
certificate = result["certificate"]
print(f"Certificate ID: {certificate['cert_id']}")
print(f"Compliance Level: {certificate['compliance_level']}")
print(certificate["badge"])  # ASCII badge
```

## L3: Comprehensive Evaluation

L3 generates a full Gold Standard report with all cross-cutting metrics.

```python
from mas_eval.harness.l3_comprehensive import run_l3_comprehensive

result = run_l3_comprehensive(
    card,
    golden_trajectory=expected_trajectory,
    mock_trajectory=actual_trajectory
)

# Access Gold Standard results
gold_standard = result["gold_standard"]
print(f"Overall Score: {gold_standard['compliance_report']['overall']}")
print(f"Grade: {gold_standard['compliance_report']['grade']}")
print(f"Gold Verdict: {gold_standard['compliance_report']['gold_verdict']}")

# Access certificate
certificate = result["certificate"]
print(f"Certificate ID: {certificate['cert_id']}")
print(f"Valid Until: {certificate['valid_until']}")
```

### Certificate Compliance Levels

- **GOLD**: Score ≥ 90 and Consistency Index ≥ 0.85
- **SILVER**: Score ≥ 70 and Consistency Index ≥ 0.60
- **BRONZE**: Score ≥ 60 and Consistency Index ≥ 0.50
- **FAIL**: Below BRONZE thresholds

## L4: Evolution

L4 includes Meta-Evaluator integration for self-assessment.

```python
from mas_eval.harness.l4_evolution import run_l4_evolution

result = run_l4_evolution(
    card,
    max_epochs=3,
    convergence_delta=2.0
)

# Access meta-evaluation results
meta_eval = result["meta_evaluation"]
print(f"Reproducibility: {meta_eval['reproducibility']}")
print(f"Eval Runs: {meta_eval['eval_runs_count']}")
```

### Meta-Evaluator Dimensions

The Meta-Evaluator assesses evaluation quality across 5 dimensions:
- **Reproducibility**: Consistency across identical runs (CV ≤ 0.05)
- **Discriminability**: Ability to distinguish weak vs strong agents
- **Robustness**: Stability under small input perturbations
- **Efficiency**: Evaluation overhead ≤ 20% of task time
- **Anti-Cheat**: Resistance to metric gaming

## Cross-Cutting Metrics

### Consistency Index

Measures behavioral consistency across multiple runs:

```python
from mas_eval.domains.d5_robustness import ConsistencyIndex

ci = ConsistencyIndex()
ci.add_run(trajectory_1)
ci.add_run(trajectory_2)
ci.add_run(trajectory_3)

score = ci.score()
print(f"CI: {score['ci']}")
print(f"Dimensions: {score['dimensions']}")
```

Dimensions:
- **C_TASK**: Result Jaccard similarity (≥ 0.85)
- **C_TOOL**: Tool sequence edit distance (≤ 3)
- **C_TIME**: Execution time CV (≤ 0.25)

### Cost Efficiency

Tracks token consumption and cost metrics:

```python
from mas_eval.cross_cutting.cost_efficiency import compute_cost_efficiency

result = compute_cost_efficiency(
    trajectory=trajectory_data,
    model_name="gpt-4o"
)

print(f"Efficiency: {result['efficiency']}")
print(f"Token Waste Rate: {result['token_waste_rate']}")
print(f"Cost Per Task: {result['cpt']}")
```

## Gold Standard Thresholds

Thresholds are defined for each level (L0-L4) in `mas_eval/scoring/gold_thresholds.py`.

```python
from mas_eval.scoring.gold_thresholds import check_level_thresholds

metrics = {
    "d1_compliance": 100,
    "d2_step_efficiency": 0.75,
    "d2_tool_coverage": 95,
    "d3_spawn_rate": 99
}

result = check_level_thresholds(metrics, level="L3")
print(f"L3 compliance: {result['overall_pass']}")
```

## Certificate Verification

Verify a certificate's authenticity:

```python
from mas_eval.scoring.gold_certificate import verify_certificate

is_valid = verify_certificate(certificate, signature_key="your-key")
print(f"Certificate valid: {is_valid}")
```

## API Reference

### L2/L3 Result Structure

```python
{
    "level": "L2" | "L3",
    "name": str,
    "elapsed_seconds": float,
    "score": float,
    "grade": str,
    "verdict": str,
    "domain_scores": dict,
    "domains": dict,
    "findings": list,
    "gold_standard": {
        "consistency_index": float | None,
        "cost_efficiency": float | None,
        "compliance_report": {
            "overall": float,
            "grade": str,
            "gold_verdict": str,
            "domain_scores": dict,
            "findings": list
        }
    },
    "certificate": {
        "agent_id": str,
        "cert_id": str,
        "score": float,
        "grade": str,
        "compliance_level": str,
        "consistency_index": float | None,
        "cost_efficiency": float | None,
        "valid_until": str,
        "badge": str,
        "verified": bool
    }
}
```

### L4 Result Structure

```python
{
    "level": "L4",
    "name": str,
    "elapsed_seconds": float,
    "score": float,
    "grade": str,
    "verdict": str,
    "domain_scores": dict,
    "domains": dict,
    "findings": list,
    "epoch_history": list,
    "epoch_count": int,
    "trend": str,
    "improvement_pct": float,
    "meta_evaluation": {
        "reproducibility": float,
        "eval_runs_count": int
    }
}
```

## Best Practices

1. **Provide Trajectories**: Always provide `golden_trajectory` and `mock_trajectory` for accurate Cost Efficiency calculation
2. **Multiple Runs**: For Consistency Index, run the agent multiple times with the same task
3. **Check Thresholds**: Use `check_level_thresholds()` to validate compliance before certification
4. **Verify Certificates**: Always verify certificates with the signature key in production
5. **Monitor Meta-Evaluation**: For L4, monitor reproducibility scores to ensure evaluation quality

## Troubleshooting

### Certificate Shows "FAIL"

- Check if score meets minimum thresholds (≥ 60 for BRONZE)
- Verify Consistency Index is ≥ 0.50
- Review findings for critical issues

### Low Consistency Index

- Ensure agent produces consistent outputs
- Check for non-deterministic behavior
- Verify tool call sequences are stable

### Low Cost Efficiency

- Review token waste rate (should be ≤ 25%)
- Check for excessive retries
- Optimize tool call patterns

## Related Documentation

- [API Contracts](api-contracts.md)
- [Release Gate](release-gate.md)
- [Operations Readiness](operations-readiness.md)
