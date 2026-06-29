# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for Cost Efficiency cross-cutting metric (Gold Standard §8)."""

from mas_eval.cross_cutting.cost_efficiency import compute_cost_efficiency


class TestCostEfficiency:
    def test_no_trajectory(self):
        result = compute_cost_efficiency(None)
        assert result["efficiency"] == 0.0
        assert result["retry_count"] == 0

    def test_empty_events(self):
        result = compute_cost_efficiency([])
        assert result["cpt"] == 0.0

    def test_single_tool_call(self):
        traj = {
            "events": [
                {
                    "action": {"type": "tool_call", "tool_id": "grep"},
                    "cost_usd": 0.01,
                    "token_usage": {"total": 100},
                }
            ]
        }
        result = compute_cost_efficiency(traj)
        assert result["cpt"] == 0.01
        assert result["total_tokens"] == 100
        assert result["retry_count"] == 0

    def test_with_retries(self):
        traj = {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "is_retry": True,
                    },
                    "cost_usd": 0.02,
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "is_retry": False,
                    },
                    "cost_usd": 0.01,
                },
            ]
        }
        result = compute_cost_efficiency(traj)
        assert result["retry_count"] == 1
        assert result["token_waste_rate"] > 0.0

    def test_efficiency_near_baseline(self):
        traj = {
            "events": [
                {
                    "action": {"type": "tool_call", "tool_id": "search"},
                    "cost_usd": 0.05,
                }
            ]
        }
        result = compute_cost_efficiency(traj)
        assert result["efficiency"] >= 0.5

    def test_hardware_coefficient(self):
        traj = {
            "events": [
                {
                    "action": {"type": "tool_call", "tool_id": "grep"},
                    "cost_usd": 0.10,
                }
            ]
        }
        result = compute_cost_efficiency(traj, hardware_coefficient=2.0)
        assert result["cpt_normalized"] == 0.05

    def test_zero_cost_no_tokens(self):
        result = compute_cost_efficiency({"events": [{"action": {"type": "think"}}]})
        assert result["cpt"] == 0.0
