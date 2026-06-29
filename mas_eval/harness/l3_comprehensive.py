# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L3 Comprehensive Evaluation for MAS-TS-001 v3.0.

Covers D1-D5 fully. ~8 hours.
"""

import logging
import time
import warnings

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.domains.d5_robustness import run_d5
from mas_eval.harness.aggregation import aggregate_level

logger = logging.getLogger(__name__)


def run_l3_comprehensive(
    card,
    tasks=None,
    federation_cards=None,
    golden_trajectory=None,
    mock_trajectory=None,
):
    """Run L3 Comprehensive evaluation (D1-D5, ~1 day).

    Full evaluation across all 5 domains including robustness (D5).

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
            "run_l3_comprehensive parameter 'tasks' is deprecated; "
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
    d5 = run_d5()

    return aggregate_level(
        "L3",
        "Comprehensive",
        start,
        {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5},
    )
