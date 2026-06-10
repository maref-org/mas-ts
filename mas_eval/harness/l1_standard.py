# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L1 Standard Evaluation for MAS-TS-001 v3.0.

Covers D1-D3 fully. ~30 minutes.
"""

import logging
import time

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.oracle.oracle_base import run_d2_with_oracle
from mas_eval.scoring.absolute import (
    compute_overall,
    determine_verdict,
    score_domain,
    score_to_grade,
)

logger = logging.getLogger(__name__)


def run_l1_standard(card, tasks=None):
    """Run L1 Standard evaluation (D1-D3 fully, ~30 min).

    Aggregates compliance (D1), single-agent (D2), and multi-agent (D3) scores
    into an overall score with verdict.

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

    d1_score = score_domain(d1["score"], d1.get("findings"))
    d2_score = score_domain(d2["score"], d2.get("findings"))
    d3_score = score_domain(d3["score"], d3.get("findings"))

    overall = compute_overall(d1=d1_score, d2=d2_score, d3=d3_score)
    all_findings = (
        d1.get("findings", []) + d2.get("findings", []) + d3.get("findings", [])
    )
    verdict = determine_verdict(overall, findings=all_findings)

    return {
        "level": "L1",
        "name": "Standard",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": verdict,
        "domain_scores": {"d1": d1_score, "d2": d2_score, "d3": d3_score},
        "domains": {"d1_detail": d1, "d2_detail": d2, "d3_detail": d3},
        "findings": all_findings,
    }


def run_l1_with_oracle(card, oracle_name, task_id=None, mock_trajectory=None):
    """Run L1 Standard evaluation with an executable oracle.

    Uses an oracle benchmark to generate golden trajectories for D2 scoring.

    Args:
    card: Agent card dict.
    oracle_name: Registered oracle name (e.g. "tau-bench").
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

    d1_score = score_domain(d1["score"], d1.get("findings"))
    d2_score = score_domain(d2["score"], d2.get("findings"))
    d3_score = score_domain(d3["score"], d3.get("findings"))

    overall = compute_overall(d1=d1_score, d2=d2_score, d3=d3_score)
    all_findings = (
        d1.get("findings", []) + d2.get("findings", []) + d3.get("findings", [])
    )
    verdict = determine_verdict(overall, findings=all_findings)

    return {
        "level": "L1",
        "name": "Standard (Oracle)",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": overall,
        "grade": score_to_grade(overall),
        "verdict": verdict,
        "domain_scores": {"d1": d1_score, "d2": d2_score, "d3": d3_score},
        "domains": {"d1_detail": d1, "d2_detail": d2, "d3_detail": d3},
        "findings": all_findings,
    }
