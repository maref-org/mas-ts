# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L2 Deep Evaluation for MAS-TS-001 v3.0.

Covers D1-D4 fully. ~2 hours with real LLM subset.
"""

import logging
import time
import warnings

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.harness.aggregation import aggregate_level
from mas_eval.oracle.oracle_base import run_d2_with_oracle

logger = logging.getLogger(__name__)


def run_l2_deep(
    card,
    tasks=None,
    federation_cards=None,
    golden_trajectory=None,
    mock_trajectory=None,
):
    """Run L2 Deep evaluation (D1-D4, ~2 hours).

    Adds governance and security (D4) on top of L1 for deeper analysis.

    Args:
    card: Agent card dict.
    tasks: Deprecated alias for `golden_trajectory`; emits DeprecationWarning
        when not None. Use `golden_trajectory` instead.
    federation_cards: Optional list of agent cards for cross-agent federation scoring.
    golden_trajectory: Optional expected trajectory for D2 task completion.
    mock_trajectory: Optional observed trajectory for D2 task completion.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    if tasks is not None:
        warnings.warn(
            "run_l2_deep parameter 'tasks' is deprecated; "
            "use 'golden_trajectory' instead. The 'tasks' alias will be "
            "removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
    start = time.time()
    d1 = run_d1(card)
    trajectory = golden_trajectory if golden_trajectory is not None else tasks
    d2 = run_d2(card, trajectory, mock_trajectory)
    d3 = run_d3(card)
    d4 = run_d4(card, federation_cards=federation_cards)

    return aggregate_level(
        "L2",
        "Deep",
        start,
        {"d1": d1, "d2": d2, "d3": d3, "d4": d4},
    )


def run_l2_with_oracle(
    card, oracle_name, task_id=None, mock_trajectory=None, federation_cards=None
):
    """Run L2 Deep evaluation with an executable oracle.

    Uses an oracle benchmark for D2 golden trajectory generation alongside D1/D3/D4.

    Args:
    card: Agent card dict.
    oracle_name: Registered oracle name.
    task_id: Optional specific oracle task ID.
    mock_trajectory: Optional agent trajectory for comparison.
    federation_cards: Optional list of agent cards for cross-agent federation scoring.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    start = time.time()
    d1 = run_d1(card)
    d2 = run_d2_with_oracle(card, oracle_name, task_id, mock_trajectory)
    d3 = run_d3(card)
    d4 = run_d4(card, federation_cards=federation_cards)

    return aggregate_level(
        "L2",
        "Deep (Oracle)",
        start,
        {"d1": d1, "d2": d2, "d3": d3, "d4": d4},
    )
