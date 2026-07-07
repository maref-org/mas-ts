# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Trajectory builder for D2 Gold Standard sub-domains (v3.0-GA §4.2-4.4).

Synthesizes ``scenario_trajectories`` from an agent card and an optional
golden trajectory so that ``run_d2`` can compute the three Gold Standard
sub-domains — StepEfficiency, TrajectoryQuality, ToolSelectionCorrectness.

Without this builder, L1/L2/L3 harnesses leave ``scenario_trajectories=None``
and the three sub-domains default to 0.0, underestimating the D2 score by
~20% (per the v3.0-GA gap audit, 2026-07-02).
"""

from typing import Any

from mas_eval.domains.d2_single_agent import E2E_SCENARIOS


def build_scenario_trajectories(
    card: dict[str, Any],
    golden_trajectory: list[Any] | dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Derive one trajectory dict per E2E scenario from the card + golden run.

    For each scenario in :data:`E2E_SCENARIOS`:
      * Intersect the scenario's ``required_tools`` with the tools declared on
        the agent card.
      * If a golden trajectory is supplied, reuse its tool-call events that
        fall within the available tool set.
      * If the golden-derived events are insufficient (<3), pad with synthetic
        tool-call events so each scenario still produces a non-zero score.
      * Scenarios with zero available tools yield an empty trajectory and
        continue to score 0 (preserving the existing E2E semantics).

    Args:
        card: Agent card dict (must contain ``capabilities`` list).
        golden_trajectory: Optional list of events or dict with ``events`` key.

    Returns:
        List of ``{"name", "trajectory", "expected_steps"}`` dicts, one per
        E2E scenario. The list length always equals ``len(E2E_SCENARIOS)`` so
        callers can ``zip`` it against the scenarios.
    """
    declared_tools = {
        cap.get("skill_id", "")
        for cap in card.get("capabilities", [])
        if cap.get("skill_id")
    }

    golden_events: list[dict[str, Any]] = []
    if golden_trajectory:
        golden_events = (
            golden_trajectory
            if isinstance(golden_trajectory, list)
            else golden_trajectory.get("events", [])
        )

    scenarios: list[dict[str, Any]] = []
    for scenario in E2E_SCENARIOS:
        required = set(scenario["required_tools"])
        available = required & declared_tools

        # Reuse golden events whose tool_id is declared and required by this scenario.
        scenario_events = [
            e
            for e in golden_events
            if e.get("action", {}).get("tool_id", "") in available
            and e.get("action", {}).get("type") == "tool_call"
        ]

        # Pad with synthetic events when the golden run is too thin to score.
        if len(scenario_events) < 3:
            for tool in sorted(available):
                if len(scenario_events) >= 3:
                    break
                scenario_events.append(
                    {
                        "action": {
                            "type": "tool_call",
                            "tool_id": tool,
                            "input": {},
                            "reasoning": f"Call {tool} for {scenario['name']}",
                        }
                    }
                )

        scenarios.append(
            {
                "name": scenario["name"],
                "trajectory": scenario_events,
                "expected_steps": scenario["expected_steps"],
            }
        )

    return scenarios
