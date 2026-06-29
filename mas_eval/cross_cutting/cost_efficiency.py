# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Cost Efficiency: Cross-cutting metric for MAS-TS Gold Standard.

Gold Standard §8 — Tracks token consumption, tool execution cost, retry cost,
and human review cost per task. Normalized against a reference baseline.

Usage:
    result = compute_cost_efficiency(trajectory, model_name="gpt-4o")
    print(result["efficiency"], result["token_waste_rate"])
"""

from typing import Any

COST_BASELINE = {
    "model": "qwen2.5-72b",
    "hardware": "docker_cpu_baseline",
    "cpt_reference": 0.05,
}


def compute_cost_efficiency(
    trajectory: list[dict[str, Any]] | dict[str, Any] | None = None,
    model_name: str = "unknown",
    hardware_coefficient: float = 1.0,
) -> dict[str, Any]:
    """Compute cost-efficiency metrics from execution trajectory.

    Gold Standard §8.1 — measures:
      - CPT: cost per task (total, normalized)
      - Efficiency: ratio vs reference baseline
      - Token waste rate: retry/overhead fraction
      - Retry count: number of retried tool calls

    Args:
        trajectory: Execution trajectory with cost/token data.
        model_name: Model identifier (for baseline lookup).
        hardware_coefficient: Hardware cost multiplier.

    Returns:
        Dict with cpt, efficiency, token_waste_rate, retry_count, total_tokens.
    """
    if not trajectory:
        return {
            "cpt": 0.0,
            "cpt_normalized": 0.0,
            "efficiency": 0.0,
            "token_waste_rate": 0.0,
            "retry_count": 0,
            "total_tokens": 0,
        }

    events: list[dict[str, Any]] = (
        trajectory if isinstance(trajectory, list) else trajectory.get("events", [])
    )

    costs = [
        e.get("cost_usd", 0) or e.get("action", {}).get("cost_usd", 0) for e in events
    ]
    tokens = [
        e.get("token_usage", {}).get("total", 0) for e in events if e.get("token_usage")
    ]
    retries = sum(1 for e in events if e.get("action", {}).get("is_retry", False))

    total_cost = sum(costs)
    total_tokens = sum(tokens)
    retry_cost = sum(
        e.get("cost_usd", 0)
        for e in events
        if e.get("action", {}).get("is_retry", False)
    )

    normalized_cost = (
        total_cost / hardware_coefficient if hardware_coefficient > 0 else total_cost
    )

    baseline = COST_BASELINE["cpt_reference"]
    efficiency = min(1.0, baseline / max(normalized_cost, 0.001))

    waste_rate = retry_cost / max(total_cost, 0.001) if total_cost > 0 else 0.0

    return {
        "cpt": round(total_cost, 6),
        "cpt_normalized": round(normalized_cost, 6),
        "efficiency": round(efficiency, 3),
        "token_waste_rate": round(waste_rate, 3),
        "retry_count": retries,
        "total_tokens": total_tokens,
    }
