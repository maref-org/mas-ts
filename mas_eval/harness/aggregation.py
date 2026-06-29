import time
from typing import Any

from mas_eval.scoring.absolute import (
    compute_overall,
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
