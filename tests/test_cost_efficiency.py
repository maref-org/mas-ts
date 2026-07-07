# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for Cost Efficiency cross-cutting metric (Gold Standard §8)."""

from mas_eval.cross_cutting.cost_efficiency import (
    aggregate_cost_metrics,
    check_gold_thresholds,
    compute_cost_efficiency,
)


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

    def test_model_name_multiplier(self):
        traj = {"events": [{"action": {"type": "tool_call"}, "cost_usd": 0.10}]}
        cheap = compute_cost_efficiency(traj, model_name="qwen-max")
        expensive = compute_cost_efficiency(traj, model_name="claude-opus-4")
        # qwen-max multiplier (0.2) → lower effective baseline → lower efficiency
        # claude-opus-4 multiplier (2.0) → higher effective baseline → higher efficiency
        assert cheap["efficiency"] < expensive["efficiency"]

    def test_unknown_model_default(self):
        traj = {"events": [{"action": {"type": "tool_call"}, "cost_usd": 0.10}]}
        result = compute_cost_efficiency(traj, model_name="unknown-model")
        assert result["efficiency"] > 0.0  # falls through to multiplier 1.0

    def test_human_review_cost(self):
        traj = {
            "events": [
                {
                    "action": {"type": "tool_call", "tool_id": "grep"},
                    "cost_usd": 0.01,
                    "human_review_cost": 0.005,
                }
            ]
        }
        result = compute_cost_efficiency(traj, include_human_review=True)
        assert "human_review_cost" in result
        assert result["human_review_cost"] == 0.005
        assert result["cpt"] == 0.01  # CPT不包括人工审核成本

    def test_coordination_cost_and_overhead(self):
        traj = {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "is_retry": True,
                    },
                    "cost_usd": 0.02,
                    "coordination_cost": 0.005,
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "is_retry": False,
                    },
                    "cost_usd": 0.01,
                    "coordination_cost": 0.003,
                },
            ]
        }
        result = compute_cost_efficiency(traj, compute_overhead=True)
        assert "direct_cost" in result
        assert "overhead_cost" in result
        assert "cost_overhead_ratio" in result
        assert result["direct_cost"] == 0.01  # 非重试成本
        # overhead_cost = retry_cost(0.02) + coordination_cost(0.005 + 0.003) = 0.028
        assert result["overhead_cost"] == 0.028
        # cost_overhead_ratio = 0.028 / 0.01 = 2.8
        assert result["cost_overhead_ratio"] == 2.8

    def test_gold_thresholds_l2_pass(self):
        # L2 thresholds: efficiency ≥0.5, waste_rate ≤0.25, overhead_ratio ≤0.4
        result = check_gold_thresholds(
            efficiency=0.6, waste_rate=0.2, overhead_ratio=0.3, level="L2"
        )
        assert result["level"] == "L2"
        assert result["efficiency"]["passed"] is True
        assert result["waste_rate"]["passed"] is True
        assert result["overhead_ratio"]["passed"] is True
        assert result["overall_pass"] is True

    def test_gold_thresholds_l3_fail(self):
        # L3 thresholds: efficiency ≥0.65, waste_rate ≤0.2, overhead_ratio ≤0.3
        result = check_gold_thresholds(
            efficiency=0.6,  # 低于0.65
            waste_rate=0.15,
            overhead_ratio=0.25,
            level="L3",
        )
        assert result["level"] == "L3"
        assert result["efficiency"]["passed"] is False
        assert result["overall_pass"] is False

    def test_gold_thresholds_l4_strict(self):
        # L4 thresholds: efficiency ≥0.8, waste_rate ≤0.15, overhead_ratio ≤0.2
        result = check_gold_thresholds(
            efficiency=0.85, waste_rate=0.12, overhead_ratio=0.18, level="L4"
        )
        assert result["level"] == "L4"
        assert result["efficiency"]["passed"] is True
        assert result["waste_rate"]["passed"] is True
        assert result["overhead_ratio"]["passed"] is True
        assert result["overall_pass"] is True

    def test_aggregate_cost_metrics_empty(self):
        result = aggregate_cost_metrics([])
        assert result["cpt_median"] == 0.0
        assert result["cpt_p95"] == 0.0
        assert result["cv"] == 0.0
        assert result["count"] == 0

    def test_aggregate_cost_metrics_single(self):
        runs = [{"cpt": 0.1}]
        result = aggregate_cost_metrics(runs)
        assert result["cpt_median"] == 0.1
        assert result["cpt_p95"] == 0.1
        assert result["cv"] == 0.0
        assert result["count"] == 1

    def test_aggregate_cost_metrics_multiple(self):
        runs = [
            {"cpt": 0.1},
            {"cpt": 0.2},
            {"cpt": 0.3},
            {"cpt": 0.4},
            {"cpt": 0.5},
        ]
        result = aggregate_cost_metrics(runs)
        assert result["cpt_median"] == 0.3
        assert result["cpt_p95"] == 0.5  # 5 * 0.95 = 4.75 → index 4
        assert result["count"] == 5
        # CV should be > 0 for varied values
