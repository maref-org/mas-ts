# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""L2 Deep Evaluation for MAS-TS-001 v3.0.

Covers D1-D4 fully. ~2 hours with real LLM subset.
"""

import logging
import time
import warnings

from mas_eval.cross_cutting.cost_efficiency import compute_cost_efficiency
from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.harness.aggregation import (
    compute_gold_report,
    extract_gold_metrics,
)
from mas_eval.harness.trajectory_builder import build_scenario_trajectories
from mas_eval.oracle.oracle_base import run_d2_with_oracle
from mas_eval.scoring.gold_certificate import generate_gold_certificate
from mas_eval.scoring.gold_thresholds import check_level_thresholds

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
    scenario_trajectories = build_scenario_trajectories(card, trajectory)
    d2 = run_d2(
        card,
        trajectory,
        mock_trajectory,
        scenario_trajectories=scenario_trajectories,
    )
    d3 = run_d3(card)
    d4 = run_d4(card, federation_cards=federation_cards)

    # L2 不运行 D5，consistency_index 为 None
    consistency_index_value = None

    # 计算 cost efficiency
    trajectory_data = golden_trajectory or mock_trajectory
    cost_efficiency_value = None
    if trajectory_data and card:
        cost_result = compute_cost_efficiency(
            trajectory=trajectory_data,
            model_name=card.get("model_backend", {}).get("model", "unknown"),
        )
        cost_efficiency_value = cost_result.get("efficiency", 0.0)

    # 生成金标报告
    domain_results = {"d1": d1, "d2": d2, "d3": d3, "d4": d4}
    gold_report = compute_gold_report(
        domain_results=domain_results,
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
    )

    # 生成金标证书
    agent_id = card.get("agent_id", card.get("name", "unknown"))
    certificate = generate_gold_certificate(
        agent_id=agent_id,
        score=gold_report["overall"],
        grade=gold_report["grade"],
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
    )

    # Gold Standard §9.2 — threshold compliance check for L2.
    metrics = extract_gold_metrics(
        domain_results=domain_results,
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
        overall_score=gold_report["overall"],
    )
    threshold_compliance = check_level_thresholds(metrics, level="L2")

    # 构建返回结果
    result = {
        "level": "L2",
        "name": "Deep",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": gold_report["overall"],
        "grade": gold_report["grade"],
        "verdict": gold_report["gold_verdict"],
        "domain_scores": gold_report["domain_scores"],
        "domains": {f"{key}_detail": v for key, v in domain_results.items()},
        "findings": gold_report["findings"],
        "gold_standard": {
            "consistency_index": consistency_index_value,
            "cost_efficiency": cost_efficiency_value,
            "compliance_report": gold_report,
            "threshold_compliance": threshold_compliance,
        },
        "certificate": certificate,
    }

    return result


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
    domain_scores, domains, findings, gold_standard, certificate.
    """
    start = time.time()
    d1 = run_d1(card)
    d2 = run_d2_with_oracle(card, oracle_name, task_id, mock_trajectory)
    d3 = run_d3(card)
    d4 = run_d4(card, federation_cards=federation_cards)

    # L2 不运行 D5，consistency_index 为 None
    consistency_index_value = None

    # 计算 cost efficiency
    cost_efficiency_value = None
    if mock_trajectory and card:
        cost_result = compute_cost_efficiency(
            trajectory=mock_trajectory,
            model_name=card.get("model_backend", {}).get("model", "unknown"),
        )
        cost_efficiency_value = cost_result.get("efficiency", 0.0)

    # 生成金标报告
    domain_results = {"d1": d1, "d2": d2, "d3": d3, "d4": d4}
    gold_report = compute_gold_report(
        domain_results=domain_results,
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
    )

    # 生成金标证书
    agent_id = card.get("agent_id", card.get("name", "unknown"))
    certificate = generate_gold_certificate(
        agent_id=agent_id,
        score=gold_report["overall"],
        grade=gold_report["grade"],
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
    )

    # Gold Standard §9.2 — threshold compliance check for L2. run_l2_with_oracle
    # previously omitted this field that run_l2_deep reports, leaving the oracle
    # path's gold_standard schema inconsistent with the standard path.
    metrics = extract_gold_metrics(
        domain_results=domain_results,
        consistency_index=consistency_index_value,
        cost_efficiency=cost_efficiency_value,
        overall_score=gold_report["overall"],
    )
    threshold_compliance = check_level_thresholds(metrics, level="L2")

    # 构建返回结果
    result = {
        "level": "L2",
        "name": "Deep (Oracle)",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": gold_report["overall"],
        "grade": gold_report["grade"],
        "verdict": gold_report["gold_verdict"],
        "domain_scores": gold_report["domain_scores"],
        "domains": {f"{key}_detail": v for key, v in domain_results.items()},
        "findings": gold_report["findings"],
        "gold_standard": {
            "consistency_index": consistency_index_value,
            "cost_efficiency": cost_efficiency_value,
            "compliance_report": gold_report,
            "threshold_compliance": threshold_compliance,
        },
        "certificate": certificate,
    }

    return result
