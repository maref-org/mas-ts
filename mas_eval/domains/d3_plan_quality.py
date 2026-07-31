# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Plan Quality: D3 Gold Standard metric for agent planning assessment.

Gold Standard §5.3 — measures agent planning quality:
  - Plan Completeness: coverage of all necessary steps
  - Plan Adherence: deviation between planned and actual execution
  - Plan Stability: consistency across multiple runs

Usage:
    result = run_plan_quality(plan, execution, multiple_plans)
    print(result["completeness"], result["adherence"], result["stability"])
"""

from typing import Any


def run_plan_quality(
    plan: list[dict[str, Any]] | dict[str, Any] | None = None,
    execution: list[dict[str, Any]] | dict[str, Any] | None = None,
    multiple_plans: list[list[dict[str, Any]] | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute Plan Quality metrics from agent planning data.

    Gold Standard §5.3 — measures:
      - Plan Completeness: plan covers all necessary steps
      - Plan Adherence: actual execution follows planned path
      - Plan Stability: consistency across multiple planning runs

    Args:
        plan: Agent's planned steps.
        execution: Actual executed steps.
        multiple_plans: Plans from multiple runs (for stability).

    Returns:
        Dict with 3 quality metrics and overall plan quality.
    """
    # Handle empty plan
    if not plan:
        return {
            "completeness": 0.0,
            "adherence": 0.0,
            "stability": 0.0,
            "plan_quality": 0.0,
        }

    # Extract plan steps
    plan_steps: list[dict[str, Any]] = (
        plan if isinstance(plan, list) else plan.get("steps", [])
    )

    # Extract execution steps if provided
    execution_steps: list[dict[str, Any]] = []
    if execution:
        execution_steps = (
            execution if isinstance(execution, list) else execution.get("events", [])
        )

    # 1. Plan Completeness
    completeness_score = _calculate_completeness(plan_steps, execution_steps)

    # 2. Plan Adherence
    adherence_score = _calculate_adherence(plan_steps, execution_steps)

    # 3. Plan Stability
    stability_score = _calculate_stability(plan_steps, multiple_plans)

    # Overall plan quality (weighted average)
    weights = {
        "completeness": 0.35,
        "adherence": 0.40,
        "stability": 0.25,
    }

    plan_quality = (
        completeness_score * weights["completeness"]
        + adherence_score * weights["adherence"]
        + stability_score * weights["stability"]
    )

    return {
        "completeness": round(completeness_score, 3),
        "adherence": round(adherence_score, 3),
        "stability": round(stability_score, 3),
        "plan_quality": round(plan_quality, 3),
        "plan_steps": len(plan_steps),
        "execution_steps": len(execution_steps),
    }


def _calculate_completeness(
    plan_steps: list[dict[str, Any]],
    execution_steps: list[dict[str, Any]],
) -> float:
    """Calculate plan completeness based on coverage of necessary steps."""
    if not plan_steps:
        return 0.0

    if not execution_steps:
        # Without execution, can't assess completeness
        return 0.5

    # Extract tool IDs from plan and execution
    plan_tools = {s.get("tool_id", "") for s in plan_steps if s.get("tool_id")}
    execution_tools = {s.get("action", {}).get("tool_id", "") for s in execution_steps}
    execution_tools.discard("")  # Remove empty strings

    if not plan_tools or not execution_tools:
        return 0.5

    # Completeness: proportion of execution tools covered by plan
    covered_tools = plan_tools.intersection(execution_tools)
    completeness = len(covered_tools) / max(len(execution_tools), 1)

    return min(1.0, completeness)


def _calculate_adherence(
    plan_steps: list[dict[str, Any]],
    execution_steps: list[dict[str, Any]],
) -> float:
    """Calculate plan adherence based on execution path deviation."""
    if not plan_steps:
        return 0.0

    if not execution_steps:
        # Without execution, can't assess adherence
        return 0.5

    # Extract tool sequences
    plan_sequence = [s.get("tool_id", "") for s in plan_steps if s.get("tool_id")]
    execution_sequence = [
        s.get("action", {}).get("tool_id", "") for s in execution_steps
    ]
    execution_sequence = [t for t in execution_sequence if t]  # Remove empty

    if not plan_sequence or not execution_sequence:
        return 0.5

    # Simple position-wise matching (could use proper edit distance)
    matches = 0
    for i, planned_tool in enumerate(plan_sequence):
        if i < len(execution_sequence) and planned_tool == execution_sequence[i]:
            matches += 1

    # Adherence: proportion of planned steps followed in order
    adherence = matches / max(len(plan_sequence), 1)

    # Also consider length difference penalty
    length_diff = abs(len(plan_sequence) - len(execution_sequence))
    length_penalty = min(0.3, length_diff / max(len(plan_sequence), 1) * 0.3)

    return max(0.0, adherence - length_penalty)


def _calculate_stability(
    current_plan: list[dict[str, Any]],
    multiple_plans: list[list[dict[str, Any]] | dict[str, Any]] | None,
) -> float:
    """Calculate plan stability based on consistency across multiple runs."""
    if not multiple_plans or len(multiple_plans) < 2:
        # Need at least 2 plans to assess stability
        return 0.5

    # Extract tool sequences from all plans
    all_sequences = []
    for plan in multiple_plans:
        steps = plan if isinstance(plan, list) else plan.get("steps", [])
        sequence = [s.get("tool_id", "") for s in steps if s.get("tool_id")]
        all_sequences.append(sequence)

    # Include current plan
    current_sequence = [s.get("tool_id", "") for s in current_plan if s.get("tool_id")]
    all_sequences.append(current_sequence)

    # Calculate pairwise similarity
    similarities = []
    for i in range(len(all_sequences)):
        for j in range(i + 1, len(all_sequences)):
            seq1 = all_sequences[i]
            seq2 = all_sequences[j]

            # Simple similarity: proportion of matching tools at same positions
            min_len = min(len(seq1), len(seq2))
            if min_len == 0:
                similarity = 0.0
            else:
                matches = sum(1 for k in range(min_len) if seq1[k] == seq2[k])
                similarity = matches / min_len

            similarities.append(similarity)

    if not similarities:
        return 0.5

    # Stability is average similarity
    avg_similarity = sum(similarities) / len(similarities)
    return avg_similarity


def check_plan_quality_thresholds(
    adherence: float,
    stability: float,
    level: str = "L2",
) -> dict[str, Any]:
    """Check Plan Quality metrics against Gold Standard thresholds.

    Gold Standard thresholds:
        L2: Adherence ≥0.65, Stability ≥0.65
        L3: Adherence ≥0.75, Stability ≥0.75
        L4: Adherence ≥0.82, Stability ≥0.82

    Args:
        adherence: Plan adherence score (0.0-1.0).
        stability: Plan stability score (0.0-1.0).
        level: Execution level (L2, L3, L4).

    Returns:
        Dict with pass/fail status and details.
    """
    thresholds = {
        "L2": {"adherence": 0.65, "stability": 0.65},
        "L3": {"adherence": 0.75, "stability": 0.75},
        "L4": {"adherence": 0.82, "stability": 0.82},
    }

    if level not in thresholds:
        raise ValueError(f"Unknown level: {level}. Must be L2, L3, or L4.")

    level_thresholds = thresholds[level]

    results: dict[str, Any] = {
        "level": level,
        "adherence": {
            "value": adherence,
            "threshold": level_thresholds["adherence"],
            "passed": adherence >= level_thresholds["adherence"],
        },
        "stability": {
            "value": stability,
            "threshold": level_thresholds["stability"],
            "passed": stability >= level_thresholds["stability"],
        },
        "overall_pass": True,
    }

    results["overall_pass"] = (
        results["adherence"]["passed"] and results["stability"]["passed"]
    )

    return results
