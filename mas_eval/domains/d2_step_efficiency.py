# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Step Efficiency: D2 Gold Standard metric for trajectory optimization.

Gold Standard §4.2 — measures how efficiently an agent completes tasks:
  - Optimality Ratio: actual steps vs minimal expected steps
  - Redundancy Ratio: proportion of unnecessary steps
  - Revisit Ratio: tool re-usage indicating potential loops

Usage:
    result = run_step_efficiency(trajectory, expert_trajectory)
    print(result["optimality"], result["redundancy"], result["revisit"])
"""

from typing import Any


def run_step_efficiency(
    trajectory: list[dict[str, Any]] | dict[str, Any] | None = None,
    expert_trajectory: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute Step Efficiency metrics from execution trajectory.

    Gold Standard §4.2 — measures:
      - Optimality Ratio: expected_min_steps / actual_steps
      - Redundancy Ratio: 1 - unnecessary_steps / total_steps
      - Revisit Ratio: revisited_tools / unique_tools

    Args:
        trajectory: Agent execution trajectory with step data.
        expert_trajectory: Expert/minimal trajectory for comparison.

    Returns:
        Dict with optimality, redundancy, revisit ratios and scores.
    """
    # Handle empty trajectory
    if not trajectory:
        return {
            "optimality_ratio": 0.0,
            "redundancy_ratio": 0.0,
            "revisit_ratio": 0.0,
            "optimality_score": 0.0,
            "redundancy_score": 0.0,
            "revisit_score": 0.0,
            "step_efficiency": 0.0,
        }

    # Extract events from trajectory
    events: list[dict[str, Any]] = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )

    # Extract expert events if provided
    expert_events: list[dict[str, Any]] = []
    if expert_trajectory:
        expert_events = (
            expert_trajectory
            if isinstance(expert_trajectory, list)
            else expert_trajectory.get("events", [])
        )

    # Calculate basic metrics
    actual_steps = len(events)
    expected_min_steps = (
        len(expert_events) if expert_events else max(1, actual_steps // 2)
    )

    # Extract tool information
    tool_sequence = []
    unique_tools = set()
    tool_usage_count: dict[str, int] = {}

    for e in events:
        action = e.get("action", {})
        tool_id = action.get("tool_id", "")
        if tool_id:
            tool_sequence.append(tool_id)
            unique_tools.add(tool_id)
            tool_usage_count[tool_id] = tool_usage_count.get(tool_id, 0) + 1

    # Identify unnecessary steps (steps not in expert trajectory or redundant)
    unnecessary_steps = 0
    if expert_events:
        expert_tools = {e.get("action", {}).get("tool_id", "") for e in expert_events}
        expert_tool_counts: dict[str, int] = {}
        for e in expert_events:
            tool_id = e.get("action", {}).get("tool_id", "")
            if tool_id:
                expert_tool_counts[tool_id] = expert_tool_counts.get(tool_id, 0) + 1

        # Count tool usage in actual trajectory
        actual_tool_counts: dict[str, int] = {}
        for e in events:
            tool_id = e.get("action", {}).get("tool_id", "")
            if tool_id:
                actual_tool_counts[tool_id] = actual_tool_counts.get(tool_id, 0) + 1

        # Calculate unnecessary steps:
        # 1. Tools not in expert trajectory
        # 2. Excess usage beyond expert count
        for tool_id, actual_count in actual_tool_counts.items():
            expert_count = expert_tool_counts.get(tool_id, 0)
            if tool_id not in expert_tools:
                # Tool not in expert trajectory at all
                unnecessary_steps += actual_count
            elif actual_count > expert_count:
                # Tool used more times than in expert trajectory
                unnecessary_steps += actual_count - expert_count
    else:
        # Without expert trajectory, can't identify unnecessary steps
        unnecessary_steps = 0

    # Calculate revisited tools (tools used more than once)
    revisited_tools = sum(1 for count in tool_usage_count.values() if count > 1)

    # Calculate ratios
    optimality_ratio = expected_min_steps / max(actual_steps, 1)
    redundancy_ratio = 1 - (unnecessary_steps / max(actual_steps, 1))
    revisit_ratio = revisited_tools / max(len(unique_tools), 1)

    # Apply thresholds and calculate scores
    # Gold Standard thresholds:
    # - Optimality Ratio < 0.4 → 该场景 0 分 (严重低效)
    # - Revisit Ratio > 0.35 → 触发 WARNING (反复调用可能死循环)

    optimality_score = 0.0
    if optimality_ratio >= 0.4:
        # Scale from 0.4 to 1.0 → 0.0 to 1.0 score
        optimality_score = min(1.0, (optimality_ratio - 0.4) / 0.6)

    redundancy_score = redundancy_ratio  # Direct mapping 0.0-1.0

    revisit_score = 1.0 - min(1.0, revisit_ratio / 0.35) if revisit_ratio > 0 else 1.0

    # Overall step efficiency (weighted average)
    step_efficiency = (
        optimality_score * 0.40  # Optimality weight 40%
        + redundancy_score * 0.30  # Redundancy weight 30%
        + revisit_score * 0.30  # Revisit weight 30%
    )

    # Check for warnings
    warnings = []
    if optimality_ratio < 0.4:
        warnings.append("严重低效: Optimality Ratio < 0.4")
    if revisit_ratio > 0.35:
        warnings.append("潜在死循环: Revisit Ratio > 0.35")

    return {
        "optimality_ratio": round(optimality_ratio, 3),
        "redundancy_ratio": round(redundancy_ratio, 3),
        "revisit_ratio": round(revisit_ratio, 3),
        "optimality_score": round(optimality_score, 3),
        "redundancy_score": round(redundancy_score, 3),
        "revisit_score": round(revisit_score, 3),
        "step_efficiency": round(step_efficiency, 3),
        "actual_steps": actual_steps,
        "expected_min_steps": expected_min_steps,
        "unnecessary_steps": unnecessary_steps,
        "unique_tools": len(unique_tools),
        "revisited_tools": revisited_tools,
        "warnings": warnings,
    }


def check_step_efficiency_thresholds(
    optimality_ratio: float,
    revisit_ratio: float,
    level: str = "L2",
) -> dict[str, Any]:
    """Check Step Efficiency metrics against Gold Standard thresholds.

    Gold Standard thresholds:
        L2: Optimality ≥0.5, Revisit ≤0.25
        L3: Optimality ≥0.65, Revisit ≤0.20
        L4: Optimality ≥0.8, Revisit ≤0.15

    Args:
        optimality_ratio: Optimality ratio (0.0-1.0).
        revisit_ratio: Revisit ratio (0.0-1.0).
        level: Execution level (L2, L3, L4).

    Returns:
        Dict with pass/fail status and details.
    """
    thresholds = {
        "L2": {"optimality": 0.5, "revisit": 0.25},
        "L3": {"optimality": 0.65, "revisit": 0.20},
        "L4": {"optimality": 0.8, "revisit": 0.15},
    }

    if level not in thresholds:
        raise ValueError(f"Unknown level: {level}. Must be L2, L3, or L4.")

    level_thresholds = thresholds[level]

    results: dict[str, Any] = {
        "level": level,
        "optimality": {
            "value": optimality_ratio,
            "threshold": level_thresholds["optimality"],
            "passed": optimality_ratio >= level_thresholds["optimality"],
        },
        "revisit": {
            "value": revisit_ratio,
            "threshold": level_thresholds["revisit"],
            "passed": revisit_ratio <= level_thresholds["revisit"],
        },
        "overall_pass": True,
    }

    results["overall_pass"] = (
        results["optimality"]["passed"] and results["revisit"]["passed"]
    )

    return results
