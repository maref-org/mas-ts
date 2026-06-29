import time
from typing import Any

from mas_eval.scoring.absolute import (
    compute_gold_overall,
    compute_overall,
    determine_gold_verdict,
    determine_verdict,
    score_domain,
    score_to_grade,
)


def aggregate_level(
    level: str,
    name: str,
    start_time: float,
    domain_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    domain_scores = {
        key: score_domain(result["score"]) for key, result in domain_results.items()
    }
    all_findings: list[dict[str, Any]] = []
    for result in domain_results.values():
        all_findings.extend(result.get("findings", []))
    overall = compute_overall(**domain_scores)
    return {
        "level": level,
        "name": name,
        "elapsed_seconds": round(time.time() - start_time, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": determine_verdict(overall, findings=all_findings),
        "domain_scores": domain_scores,
        "domains": {f"{key}_detail": result for key, result in domain_results.items()},
        "findings": all_findings,
    }


def compute_gold_report(
    domain_results: dict[str, dict[str, Any]],
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
) -> dict[str, Any]:
    """Gold Standard aggregation with cross-cutting adjustments.

    Uses Gold domain weights (D1=0.08, D2=0.22, D3=0.20, D4=0.25, D5=0.25)
    with Consistency Index and Cost Efficiency penalties.

    Args:
        domain_results: Dict mapping domain keys to their result dicts.
        consistency_index: Optional Consistency Index (0.0-1.0).
        cost_efficiency: Optional Cost Efficiency score (0.0-1.0).

    Returns:
        Dict with gold_verdict, overall, grade, domain_scores, findings.
    """
    domain_scores = {
        key: score_domain(result["score"]) for key, result in domain_results.items()
    }
    all_findings: list[dict[str, Any]] = []
    for result in domain_results.values():
        all_findings.extend(result.get("findings", []))
    overall = compute_gold_overall(
        **domain_scores,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
    )
    return {
        "gold_verdict": determine_gold_verdict(
            overall, all_findings, consistency_index
        ),
        "overall": overall,
        "grade": score_to_grade(overall),
        "domain_scores": domain_scores,
        "consistency_index": consistency_index,
        "cost_efficiency": cost_efficiency,
        "findings": all_findings,
    }
