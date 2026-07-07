# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Coordination Efficiency: D3 Gold Standard metric for multi-agent communication.

Gold Standard §5.2 — measures inter-agent communication efficiency:
  - Message Efficiency: actual_messages / optimal_messages
  - Communication Overhead: communication_time / total_task_time
  - Coordination Complexity: coordination_turns / task_steps
  - Irrelevant Message Ratio: irrelevant_messages / total_messages
  - Serialization Loss: idle_wait_time / total_task_time

Usage:
    result = run_coordination_efficiency(messages, task_time_ms)
    print(result["message_efficiency"], result["comm_overhead"])
"""

from typing import Any


def run_coordination_efficiency(
    messages: list[dict[str, Any]] | None = None,
    task_time_ms: int = 0,
    idle_wait_time_ms: int = 0,
    task_steps: int = 0,
) -> dict[str, Any]:
    """Compute Coordination Efficiency metrics from inter-agent messages.

    Gold Standard §5.2 — measures:
      - Message Efficiency: actual_messages / optimal_messages ≤1.5x
      - Communication Overhead: communication_time / total_task_time ≤30%
      - Coordination Complexity: coordination_turns / task_steps ≤0.4
      - Irrelevant Message Ratio: irrelevant_messages / total_messages ≤10%
      - Serialization Loss: idle_wait_time / total_task_time ≤15%

    Args:
        messages: Inter-agent message logs.
        task_time_ms: Total task execution time in milliseconds.
        idle_wait_time_ms: Total idle waiting time in milliseconds.
        task_steps: Number of task execution steps.

    Returns:
        Dict with 5 efficiency metrics and overall coordination efficiency.
    """
    # Handle empty messages
    if not messages:
        return {
            "message_efficiency_ratio": 0.0,
            "comm_overhead_ratio": 0.0,
            "coordination_complexity": 0.0,
            "irrelevant_message_ratio": 0.0,
            "serialization_loss": 0.0,
            "message_efficiency_score": 0.0,
            "comm_overhead_score": 0.0,
            "coordination_complexity_score": 0.0,
            "irrelevant_message_score": 0.0,
            "serialization_loss_score": 0.0,
            "coordination_efficiency": 0.0,
            "total_messages": 0,
            "coordination_turns": 0,
            "warnings": [],
        }

    total_messages = len(messages)

    # Calculate message latency and communication time
    total_comm_time_ms = 0
    coordination_turns = 0
    irrelevant_messages = 0
    unique_sequences = set()

    for msg in messages:
        # Communication time
        latency = msg.get("latency_ms", 0)
        total_comm_time_ms += latency

        # Coordination turns (sender-receiver pairs)
        sender = msg.get("sender", "")
        receiver = msg.get("receiver", "")
        if sender and receiver:
            turn_key = f"{sender}->{receiver}"
            unique_sequences.add(turn_key)

        # Count irrelevant messages
        if msg.get("is_relevant", True) is False:
            irrelevant_messages += 1

    coordination_turns = len(unique_sequences)

    # 1. Message Efficiency: actual / optimal (optimal = unique coordination turns)
    optimal_messages = max(coordination_turns, 1)
    message_efficiency = total_messages / optimal_messages

    # 2. Communication Overhead Ratio
    comm_overhead_ratio = total_comm_time_ms / max(task_time_ms, 1)

    # 3. Coordination Complexity
    coordination_complexity = coordination_turns / max(task_steps, 1)

    # 4. Irrelevant Message Ratio
    irrelevant_message_ratio = irrelevant_messages / max(total_messages, 1)

    # 5. Serialization Loss
    serialization_loss = idle_wait_time_ms / max(task_time_ms, 1)

    # Calculate individual scores (higher is better, 1.0 = perfect)
    # Message Efficiency: ≤1.5x is good, >3x is bad
    message_efficiency_score = max(0.0, 1.0 - (message_efficiency - 1.0) / 1.5)

    # Communication Overhead: ≤30% is good, >50% is unacceptable
    if comm_overhead_ratio <= 0.3:
        comm_overhead_score = 1.0
    elif comm_overhead_ratio <= 0.5:
        # Linear decay from 30% to 50%
        comm_overhead_score = 1.0 - (comm_overhead_ratio - 0.3) / 0.2 * 0.5
    else:
        # >50% = 0 (unacceptable per Gold Standard)
        comm_overhead_score = 0.0

    # Coordination Complexity: ≤0.4 is good
    coordination_complexity_score = max(0.0, 1.0 - coordination_complexity / 0.4)

    # Irrelevant Messages: ≤10% is good
    irrelevant_message_score = max(0.0, 1.0 - irrelevant_message_ratio / 0.1)

    # Serialization Loss: ≤15% is good
    serialization_loss_score = max(0.0, 1.0 - serialization_loss / 0.15)

    # Overall coordination efficiency (weighted average)
    weights = {
        "message_efficiency": 0.30,
        "comm_overhead": 0.25,
        "coordination_complexity": 0.20,
        "irrelevant_messages": 0.15,
        "serialization_loss": 0.10,
    }

    coordination_efficiency = (
        message_efficiency_score * weights["message_efficiency"]
        + comm_overhead_score * weights["comm_overhead"]
        + coordination_complexity_score * weights["coordination_complexity"]
        + irrelevant_message_score * weights["irrelevant_messages"]
        + serialization_loss_score * weights["serialization_loss"]
    )

    # Check for warnings
    warnings = []
    if comm_overhead_ratio > 0.5:
        warnings.append("通信开销过大: Communication Overhead > 50%")
    if irrelevant_message_ratio > 0.2:
        warnings.append("无用消息过多: Irrelevant Messages > 20%")

    return {
        "message_efficiency_ratio": round(message_efficiency, 3),
        "comm_overhead_ratio": round(comm_overhead_ratio, 3),
        "coordination_complexity": round(coordination_complexity, 3),
        "irrelevant_message_ratio": round(irrelevant_message_ratio, 3),
        "serialization_loss": round(serialization_loss, 3),
        "message_efficiency_score": round(message_efficiency_score, 3),
        "comm_overhead_score": round(comm_overhead_score, 3),
        "coordination_complexity_score": round(coordination_complexity_score, 3),
        "irrelevant_message_score": round(irrelevant_message_score, 3),
        "serialization_loss_score": round(serialization_loss_score, 3),
        "coordination_efficiency": round(coordination_efficiency, 3),
        "total_messages": total_messages,
        "coordination_turns": coordination_turns,
        "warnings": warnings,
    }


def check_coordination_efficiency_thresholds(
    comm_overhead_ratio: float,
    message_efficiency: float,
    irrelevant_message_ratio: float,
    level: str = "L2",
) -> dict[str, Any]:
    """Check Coordination Efficiency metrics against Gold Standard thresholds.

    Gold Standard thresholds:
        L2: Comm Overhead ≤40%, Message Efficiency ≤2.0x, Irrelevant ≤20%
        L3: Comm Overhead ≤35%, Message Efficiency ≤1.8x, Irrelevant ≤15%
        L4: Comm Overhead ≤30%, Message Efficiency ≤1.5x, Irrelevant ≤10%

    Args:
        comm_overhead_ratio: Communication overhead ratio (0.0-1.0).
        message_efficiency: Message efficiency ratio (1.0-∞).
        irrelevant_message_ratio: Irrelevant message ratio (0.0-1.0).
        level: Execution level (L2, L3, L4).

    Returns:
        Dict with pass/fail status and details.
    """
    thresholds = {
        "L2": {"comm_overhead": 0.40, "message_efficiency": 2.0, "irrelevant": 0.20},
        "L3": {"comm_overhead": 0.35, "message_efficiency": 1.8, "irrelevant": 0.15},
        "L4": {"comm_overhead": 0.30, "message_efficiency": 1.5, "irrelevant": 0.10},
    }

    if level not in thresholds:
        raise ValueError(f"Unknown level: {level}. Must be L2, L3, or L4.")

    level_thresholds = thresholds[level]

    results: dict[str, Any] = {
        "level": level,
        "comm_overhead": {
            "value": comm_overhead_ratio,
            "threshold": level_thresholds["comm_overhead"],
            "passed": comm_overhead_ratio <= level_thresholds["comm_overhead"],
        },
        "message_efficiency": {
            "value": message_efficiency,
            "threshold": level_thresholds["message_efficiency"],
            "passed": message_efficiency <= level_thresholds["message_efficiency"],
        },
        "irrelevant_messages": {
            "value": irrelevant_message_ratio,
            "threshold": level_thresholds["irrelevant"],
            "passed": irrelevant_message_ratio <= level_thresholds["irrelevant"],
        },
        "overall_pass": True,
    }

    results["overall_pass"] = (
        results["comm_overhead"]["passed"]
        and results["message_efficiency"]["passed"]
        and results["irrelevant_messages"]["passed"]
    )

    return results
