# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Trajectory Quality: D2 Gold Standard metric for semantic trajectory assessment.

Gold Standard §4.3 — measures semantic quality of agent trajectories:
  - Optimality: edit distance between actual and expert trajectories
  - Coherence: semantic relatedness between consecutive steps
  - Determinism: consistency across multiple runs with same input
  - Recovery: success rate in recovering from errors
  - Transparency: understandability of reasoning at each step

Usage:
    result = run_trajectory_quality(trajectory, expert_trajectory)
    print(result["optimality"], result["coherence"], result["determinism"])
"""

from typing import Any


def run_trajectory_quality(
    trajectory: list[dict[str, Any]] | dict[str, Any] | None = None,
    expert_trajectory: list[dict[str, Any]] | dict[str, Any] | None = None,
    multiple_runs: list[list[dict[str, Any]] | dict[str, Any]] | None = None,
    recovery_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute Trajectory Quality metrics from execution trajectory.

    Gold Standard §4.3 — measures:
      - Optimality: edit distance between actual and expert steps
      - Coherence: semantic relatedness between consecutive steps
      - Determinism: same input → same trajectory ratio (N≥5)
      - Recovery: error recovery success rate
      - Transparency: reasoning understandability at each step

    Args:
        trajectory: Agent execution trajectory.
        expert_trajectory: Expert/minimal trajectory for comparison.
        multiple_runs: List of trajectories from multiple runs (for determinism).
        recovery_data: Data about error recovery attempts.

    Returns:
        Dict with 5 dimension scores and overall trajectory quality.
    """
    # Handle empty trajectory
    if not trajectory:
        return {
            "optimality": 0.0,
            "coherence": 0.0,
            "determinism": 0.0,
            "recovery": 0.0,
            "transparency": 0.0,
            "trajectory_quality": 0.0,
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

    # 1. Optimality: edit distance between actual and expert steps
    optimality_score = _calculate_optimality(events, expert_events)

    # 2. Coherence: semantic relatedness between consecutive steps
    coherence_score = _calculate_coherence(events)

    # 3. Determinism: consistency across multiple runs
    determinism_score = _calculate_determinism(events, multiple_runs)

    # 4. Recovery: error recovery success rate
    recovery_score = _calculate_recovery(recovery_data)

    # 5. Transparency: reasoning understandability
    transparency_score = _calculate_transparency(events)

    # Overall trajectory quality (weighted average)
    weights = {
        "optimality": 0.25,
        "coherence": 0.20,
        "determinism": 0.20,
        "recovery": 0.20,
        "transparency": 0.15,
    }

    trajectory_quality = (
        optimality_score * weights["optimality"]
        + coherence_score * weights["coherence"]
        + determinism_score * weights["determinism"]
        + recovery_score * weights["recovery"]
        + transparency_score * weights["transparency"]
    )

    return {
        "optimality": round(optimality_score, 3),
        "coherence": round(coherence_score, 3),
        "determinism": round(determinism_score, 3),
        "recovery": round(recovery_score, 3),
        "transparency": round(transparency_score, 3),
        "trajectory_quality": round(trajectory_quality, 3),
    }


def _calculate_optimality(
    events: list[dict[str, Any]],
    expert_events: list[dict[str, Any]],
) -> float:
    """Calculate optimality score based on edit distance.

    Uses simplified sequence matching since we don't have semantic embeddings.
    """
    if not expert_events:
        # Without expert trajectory, assume moderate optimality
        return 0.5

    # Extract tool sequences
    actual_sequence = [e.get("action", {}).get("tool_id", "") for e in events]
    expert_sequence = [e.get("action", {}).get("tool_id", "") for e in expert_events]

    # Simple sequence matching (could be enhanced with proper edit distance)
    matches = 0
    for i, actual_tool in enumerate(actual_sequence):
        if i < len(expert_sequence) and actual_tool == expert_sequence[i]:
            matches += 1

    # Score based on position-wise matching
    if len(expert_sequence) == 0:
        return 0.0

    match_ratio = matches / len(expert_sequence)

    # Also consider length ratio
    length_ratio = len(expert_sequence) / max(len(actual_sequence), 1)

    # Combined score
    return match_ratio * 0.7 + length_ratio * 0.3


def _calculate_coherence(events: list[dict[str, Any]]) -> float:
    """Calculate coherence score based on step relatedness.

    Simplified version without semantic embeddings.
    """
    if len(events) <= 1:
        return 1.0  # Single step is trivially coherent

    # Extract tool transitions
    tools = [e.get("action", {}).get("tool_id", "") for e in events]

    # Simple coherence measure: unique tools vs total steps
    # More unique tools relative to steps suggests diverse but potentially coherent steps
    unique_tools = set(t for t in tools if t)

    if not unique_tools:
        return 0.5  # No tools, neutral coherence

    # Coherence heuristic: balanced diversity (not too many repeats, not all unique)
    diversity_ratio = len(unique_tools) / len(tools)

    # Ideal coherence: moderate diversity (around 0.6-0.8)
    if 0.6 <= diversity_ratio <= 0.8:
        return 1.0
    elif diversity_ratio < 0.3:
        # Too repetitive
        return 0.3
    elif diversity_ratio > 0.9:
        # Too diverse (might lack coherence)
        return 0.7
    else:
        # Linear interpolation
        return 0.5 + (diversity_ratio - 0.5) * 2


def _calculate_determinism(
    current_run: list[dict[str, Any]],
    multiple_runs: list[list[dict[str, Any]] | dict[str, Any]] | None,
) -> float:
    """Calculate determinism score based on consistency across runs."""
    if not multiple_runs or len(multiple_runs) < 5:
        # Gold Standard requires N≥5 for determinism
        return 0.5  # Placeholder when insufficient data

    # Extract tool sequences from all runs
    all_sequences = []
    for run in multiple_runs:
        events = run if isinstance(run, list) else run.get("events", [])
        sequence = [e.get("action", {}).get("tool_id", "") for e in events]
        all_sequences.append(sequence)

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

    # Determinism score is average similarity
    avg_similarity = sum(similarities) / len(similarities)
    return avg_similarity


def _calculate_recovery(recovery_data: dict[str, Any] | None) -> float:
    """Calculate recovery score based on error recovery success."""
    if not recovery_data:
        return 0.5  # Placeholder when no recovery data

    # Extract recovery metrics
    total_errors = recovery_data.get("total_errors", 0)
    recovered_errors = recovery_data.get("recovered_errors", 0)

    if total_errors == 0:
        return 1.0  # No errors means perfect recovery (by definition)

    recovery_rate = recovered_errors / total_errors

    # Score based on recovery rate
    if recovery_rate >= 0.9:
        return 1.0
    elif recovery_rate >= 0.7:
        return 0.8
    elif recovery_rate >= 0.5:
        return 0.6
    elif recovery_rate >= 0.3:
        return 0.4
    else:
        return 0.2


def _calculate_transparency(events: list[dict[str, Any]]) -> float:
    """Calculate transparency score based on reasoning understandability."""
    if not events:
        return 0.0

    transparency_scores = []

    for e in events:
        action = e.get("action", {})

        # Check for reasoning/explanation
        has_reasoning = bool(action.get("reasoning") or action.get("explanation"))

        # Check for clear tool/action description
        has_clear_action = bool(action.get("tool_id") or action.get("type"))

        # Check for parameters/context
        has_context = bool(action.get("parameters") or e.get("context"))

        # Score this step
        step_score = 0.0
        if has_reasoning:
            step_score += 0.4
        if has_clear_action:
            step_score += 0.4
        if has_context:
            step_score += 0.2

        transparency_scores.append(min(1.0, step_score))

    # Average across all steps
    if not transparency_scores:
        return 0.0

    return sum(transparency_scores) / len(transparency_scores)


def check_trajectory_quality_thresholds(
    trajectory_quality: float,
    determinism: float,
    level: str = "L2",
) -> dict[str, Any]:
    """Check Trajectory Quality metrics against Gold Standard thresholds.

    Gold Standard thresholds:
        L2: Trajectory Quality ≥0.55, Determinism ≥0.55
        L3: Trajectory Quality ≥0.65, Determinism ≥0.65
        L4: Trajectory Quality ≥0.75, Determinism ≥0.75

    Args:
        trajectory_quality: Overall trajectory quality score (0.0-1.0).
        determinism: Determinism score (0.0-1.0).
        level: Execution level (L2, L3, L4).

    Returns:
        Dict with pass/fail status and details.
    """
    thresholds = {
        "L2": {"trajectory_quality": 0.55, "determinism": 0.55},
        "L3": {"trajectory_quality": 0.65, "determinism": 0.65},
        "L4": {"trajectory_quality": 0.75, "determinism": 0.75},
    }

    if level not in thresholds:
        raise ValueError(f"Unknown level: {level}. Must be L2, L3, or L4.")

    level_thresholds = thresholds[level]

    results: dict[str, Any] = {
        "level": level,
        "trajectory_quality": {
            "value": trajectory_quality,
            "threshold": level_thresholds["trajectory_quality"],
            "passed": trajectory_quality >= level_thresholds["trajectory_quality"],
        },
        "determinism": {
            "value": determinism,
            "threshold": level_thresholds["determinism"],
            "passed": determinism >= level_thresholds["determinism"],
        },
        "overall_pass": True,
    }

    results["overall_pass"] = (
        results["trajectory_quality"]["passed"] and results["determinism"]["passed"]
    )

    return results
