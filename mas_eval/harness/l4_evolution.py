# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L4 Evolution Evaluation for MAS-TS-001 v3.0.

Full D5 lifecycle: chaos engineering → drift detection → reflection loop → convergence cycles.
Multi-day, with persistence across sessions.
"""

import logging
import time
from typing import Any

from mas_eval.domains.d5_robustness import run_d5
from mas_eval.harness.epoch_state import EpochState
from mas_eval.scoring.absolute import determine_verdict, score_domain, score_to_grade

logger = logging.getLogger(__name__)

L4_SEEDS = [42, 137, 2048, 9999, 77777]


def run_l4_evolution(
    card: dict[str, Any] | None = None,
    max_epochs: int = 3,
    convergence_delta: float = 2.0,
    epoch_state: EpochState | None = None,
    verifier_registry: Any = None,
) -> dict[str, Any]:
    """Run L4 Evolution evaluation across multiple D5 lifecycle epochs.

    Full D5 lifecycle: chaos engineering, drift detection, reflection loop,
    and convergence cycles with persistence across sessions.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    start = time.time()
    state = epoch_state or EpochState()
    all_findings: list[dict[str, Any]] = []
    epoch_details: list[dict[str, Any]] = []

    for index in range(max_epochs):
        epoch = state.epoch + 1
        seed = L4_SEEDS[index % len(L4_SEEDS)]
        d5 = run_d5(card=card, seed=seed, verifier_registry=verifier_registry)
        findings = d5.get("findings", [])
        summary = str(d5.get("summary", ""))

        state.record(epoch, d5["score"], findings, summary)
        state.history[-1]["seed"] = seed
        all_findings.extend(findings)
        epoch_details.append(d5)

        if len(state.history) >= 3:
            recent_scores = [entry["score"] for entry in state.history[-3:]]
            if max(recent_scores) - min(recent_scores) < convergence_delta:
                break

    trend = state.trend()
    improvement = state.improvement_pct()
    final_score = state.avg_score if trend == "stable" else state.max_score
    d5_score = score_domain(final_score, all_findings)
    d5_detail = {
        "domain": "D5",
        "name": "Evolution & Robustness",
        "score": final_score,
        "epochs": epoch_details,
        "trend": trend,
        "improvement_pct": improvement,
        "findings": all_findings,
        "summary": {
            "epoch_count": len(state.history),
            "max_score": state.max_score,
            "min_score": state.min_score,
            "avg_score": state.avg_score,
        },
    }

    return {
        "level": "L4",
        "name": "Evolution",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": d5_score,
        "grade": score_to_grade(d5_score),
        "verdict": determine_verdict(d5_score, all_findings),
        "domain_scores": {"d5": d5_score},
        "domains": {"d5_detail": d5_detail},
        "findings": all_findings,
        "epoch_history": state.history,
        "epoch_count": len(state.history),
        "trend": trend,
        "improvement_pct": improvement,
    }
