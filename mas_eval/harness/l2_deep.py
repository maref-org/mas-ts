# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L2 Deep Evaluation for MAS-TS-001 v3.0.

Covers D1-D4 fully. ~2 hours with real LLM subset.
"""

import logging
import time

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.oracle.oracle_base import run_d2_with_oracle
from mas_eval.scoring.absolute import (
    compute_overall,
    determine_verdict,
    score_domain,
    score_to_grade,
)

logger = logging.getLogger(__name__)


def run_l2_deep(card, tasks=None):
    """Run L2 Deep evaluation (D1-D4, ~2 hours).

    Adds governance and security (D4) on top of L1 for deeper analysis.

    Args:
    card: Agent card dict.
    tasks: Optional list of task dicts for D2.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    start = time.time()
    d1 = run_d1(card)
    d2 = run_d2(card, tasks or [])
    d3 = run_d3(card)
    d4 = run_d4(card)

    d1_score = score_domain(d1["score"], d1.get("findings"))
    d2_score = score_domain(d2["score"], d2.get("findings"))
    d3_score = score_domain(d3["score"], d3.get("findings"))
    d4_score = score_domain(d4["score"], d4.get("findings"))

    overall = compute_overall(d1=d1_score, d2=d2_score, d3=d3_score, d4=d4_score)
    all_findings = (
        d1.get("findings", [])
        + d2.get("findings", [])
        + d3.get("findings", [])
        + d4.get("findings", [])
    )
    verdict = determine_verdict(overall, findings=all_findings)

    return {
        "level": "L2",
        "name": "Deep",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": verdict,
        "domain_scores": {
            "d1": d1_score,
            "d2": d2_score,
            "d3": d3_score,
            "d4": d4_score,
        },
        "domains": {"d1_detail": d1, "d2_detail": d2, "d3_detail": d3, "d4_detail": d4},
        "findings": all_findings,
    }


def run_l2_with_oracle(card, oracle_name, task_id=None, mock_trajectory=None):
    """Run L2 Deep evaluation with an executable oracle.

    Uses an oracle benchmark for D2 golden trajectory generation alongside D1/D3/D4.

    Args:
    card: Agent card dict.
    oracle_name: Registered oracle name.
    task_id: Optional specific oracle task ID.
    mock_trajectory: Optional agent trajectory for comparison.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    start = time.time()
    d1 = run_d1(card)
    d2 = run_d2_with_oracle(card, oracle_name, task_id, mock_trajectory)
    d3 = run_d3(card)
    d4 = run_d4(card)

    d1_score = score_domain(d1["score"], d1.get("findings"))
    d2_score = score_domain(d2["score"], d2.get("findings"))
    d3_score = score_domain(d3["score"], d3.get("findings"))
    d4_score = score_domain(d4["score"], d4.get("findings"))

    overall = compute_overall(d1=d1_score, d2=d2_score, d3=d3_score, d4=d4_score)
    all_findings = (
        d1.get("findings", [])
        + d2.get("findings", [])
        + d3.get("findings", [])
        + d4.get("findings", [])
    )
    verdict = determine_verdict(overall, findings=all_findings)

    return {
        "level": "L2",
        "name": "Deep (Oracle)",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": verdict,
        "domain_scores": {
            "d1": d1_score,
            "d2": d2_score,
            "d3": d3_score,
            "d4": d4_score,
        },
        "domains": {
            "d1_detail": d1,
            "d2_detail": d2,
            "d3_detail": d3,
            "d4_detail": d4,
        },
        "findings": all_findings,
    }
