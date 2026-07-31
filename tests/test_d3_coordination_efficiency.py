# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for Coordination Efficiency D3 Gold Standard metric."""

from mas_eval.domains.d3_coordination_efficiency import (
    check_coordination_efficiency_thresholds,
    run_coordination_efficiency,
)


class TestCoordinationEfficiency:
    def test_empty_messages(self):
        result = run_coordination_efficiency(None)
        assert result["coordination_efficiency"] == 0.0
        assert result["message_efficiency_ratio"] == 0.0

    def test_optimal_coordination(self):
        # Perfect coordination: 3 messages, 3 turns, no overhead
        messages = [
            {"sender": "A", "receiver": "B", "latency_ms": 10, "is_relevant": True},
            {"sender": "B", "receiver": "A", "latency_ms": 10, "is_relevant": True},
            {"sender": "A", "receiver": "C", "latency_ms": 10, "is_relevant": True},
        ]

        result = run_coordination_efficiency(
            messages=messages,
            task_time_ms=1000,
            idle_wait_time_ms=50,
            task_steps=10,
        )

        # 3 messages / 3 turns = 1.0x efficiency
        assert result["message_efficiency_ratio"] == 1.0
        # Comm time = 30ms / 1000ms = 3%
        assert result["comm_overhead_ratio"] == 0.03
        # Should have high coordination efficiency
        assert result["coordination_efficiency"] > 0.8

    def test_high_overhead(self):
        # High communication overhead
        messages = [
            {"sender": "A", "receiver": "B", "latency_ms": 100, "is_relevant": True},
            {"sender": "B", "receiver": "A", "latency_ms": 100, "is_relevant": True},
        ]

        result = run_coordination_efficiency(
            messages=messages,
            task_time_ms=500,  # 200ms comm / 500ms total = 40%
            idle_wait_time_ms=100,
            task_steps=5,
        )

        assert result["comm_overhead_ratio"] == 0.4  # 200/500
        assert result["serialization_loss"] == 0.2  # 100/500

    def test_unacceptable_overhead(self):
        # Communication overhead > 50% should score 0
        messages = [
            {"sender": "A", "receiver": "B", "latency_ms": 300, "is_relevant": True},
            {"sender": "B", "receiver": "A", "latency_ms": 300, "is_relevant": True},
        ]

        result = run_coordination_efficiency(
            messages=messages,
            task_time_ms=500,  # 600ms comm / 500ms total = 120% > 50%
            idle_wait_time_ms=200,
            task_steps=5,
        )

        assert result["comm_overhead_score"] == 0.0  # >50% = 0
        assert "通信开销过大" in " ".join(result["warnings"])

    def test_irrelevant_messages(self):
        # Messages with irrelevant ones
        messages = [
            {"sender": "A", "receiver": "B", "latency_ms": 10, "is_relevant": True},
            {"sender": "B", "receiver": "A", "latency_ms": 10, "is_relevant": False},
            {"sender": "A", "receiver": "B", "latency_ms": 10, "is_relevant": False},
            {"sender": "B", "receiver": "A", "latency_ms": 10, "is_relevant": True},
        ]

        result = run_coordination_efficiency(
            messages=messages,
            task_time_ms=1000,
            idle_wait_time_ms=50,
            task_steps=10,
        )

        # 2 irrelevant out of 4 = 50%
        assert result["irrelevant_message_ratio"] == 0.5
        # Should trigger warning
        assert "无用消息过多" in " ".join(result["warnings"])

    def test_coordination_turns(self):
        # Multiple coordination turns
        messages = [
            {"sender": "A", "receiver": "B", "latency_ms": 10, "is_relevant": True},
            {
                "sender": "A",
                "receiver": "B",
                "latency_ms": 10,
                "is_relevant": True,
            },  # Same turn
            {"sender": "B", "receiver": "C", "latency_ms": 10, "is_relevant": True},
            {"sender": "C", "receiver": "A", "latency_ms": 10, "is_relevant": True},
        ]

        result = run_coordination_efficiency(
            messages=messages,
            task_time_ms=1000,
            idle_wait_time_ms=50,
            task_steps=10,
        )

        # Should have 3 unique turns: A->B, B->C, C->A
        assert result["coordination_turns"] == 3
        # 4 messages / 3 turns = 1.33x
        assert result["message_efficiency_ratio"] > 1.0

    def test_thresholds_l2_pass(self):
        # L2 thresholds: comm_overhead ≤0.40, message_efficiency ≤2.0, irrelevant ≤0.20
        result = check_coordination_efficiency_thresholds(
            comm_overhead_ratio=0.3,
            message_efficiency=1.5,
            irrelevant_message_ratio=0.1,
            level="L2",
        )
        assert result["level"] == "L2"
        assert result["comm_overhead"]["passed"] is True
        assert result["message_efficiency"]["passed"] is True
        assert result["irrelevant_messages"]["passed"] is True
        assert result["overall_pass"] is True

    def test_thresholds_l3_fail(self):
        # L3 thresholds: comm_overhead ≤0.35, message_efficiency ≤1.8, irrelevant ≤0.15
        result = check_coordination_efficiency_thresholds(
            comm_overhead_ratio=0.4,  # Above 0.35
            message_efficiency=1.5,
            irrelevant_message_ratio=0.1,
            level="L3",
        )
        assert result["level"] == "L3"
        assert result["comm_overhead"]["passed"] is False
        assert result["overall_pass"] is False

    def test_thresholds_l4_strict(self):
        # L4 thresholds: comm_overhead ≤0.30, message_efficiency ≤1.5, irrelevant ≤0.10
        result = check_coordination_efficiency_thresholds(
            comm_overhead_ratio=0.25,
            message_efficiency=1.4,
            irrelevant_message_ratio=0.08,
            level="L4",
        )
        assert result["level"] == "L4"
        assert result["comm_overhead"]["passed"] is True
        assert result["message_efficiency"]["passed"] is True
        assert result["irrelevant_messages"]["passed"] is True
        assert result["overall_pass"] is True

    def test_empty_messages_zero_metrics(self):
        result = run_coordination_efficiency(
            messages=[],
            task_time_ms=1000,
            idle_wait_time_ms=0,
            task_steps=10,
        )

        assert result["coordination_efficiency"] == 0.0
        assert result["total_messages"] == 0
        assert result["coordination_turns"] == 0
