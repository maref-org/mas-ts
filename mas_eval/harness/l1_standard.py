# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""L1 Standard Evaluation for MAS-TS-001 v3.0.

Covers D1-D3 fully. ~30 minutes.
"""

import logging
import time
import warnings

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.harness.aggregation import aggregate_level
from mas_eval.harness.trajectory_builder import build_scenario_trajectories
from mas_eval.oracle.oracle_base import run_d2_with_oracle

logger = logging.getLogger(__name__)


def run_l1_standard(card, tasks=None, golden_trajectory=None, mock_trajectory=None):
    """Run L1 Standard evaluation (D1-D3 fully, ~30 min).

    Aggregates compliance (D1), single-agent (D2), and multi-agent (D3) scores
    into an overall score with verdict.

    Args:
    card: Agent card dict.
    tasks: Deprecated alias for `golden_trajectory`; emits DeprecationWarning
        when not None. Use `golden_trajectory` instead.
    golden_trajectory: Optional expected trajectory for D2 task completion.
    mock_trajectory: Optional observed trajectory for D2 task completion.

    Returns:
    Dict with keys: level, name, elapsed_seconds, score, grade, verdict,
    domain_scores, domains, findings.
    """
    if tasks is not None:
        warnings.warn(
            "run_l1_standard parameter 'tasks' is deprecated; "
            "use 'golden_trajectory' instead. The 'tasks' alias will be "
            "removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
    start = time.time()
    d1 = run_d1(card)
    trajectory = golden_trajectory if golden_trajectory is not None else tasks
    scenario_trajectories = build_scenario_trajectories(card, trajectory)
    d2 = run_d2(
        card,
        trajectory,
        mock_trajectory,
        scenario_trajectories=scenario_trajectories,
    )
    d3 = run_d3(card)

    return aggregate_level(
        "L1",
        "Standard",
        start,
        {"d1": d1, "d2": d2, "d3": d3},
    )


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

    return aggregate_level(
        "L1",
        "Standard (Oracle)",
        start,
        {"d1": d1, "d2": d2, "d3": d3},
    )
