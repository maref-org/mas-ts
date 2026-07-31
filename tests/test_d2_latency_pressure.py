# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.domains.d2_latency_pressure (R4 — Handbook §4.4.2).

Verifies TTFT extraction, P99 calculation, tiered scoring (Gold/Silver/Bronze/
decay/critical), findings generation, and subscore dict structure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d2_latency_pressure import (
    TTFT_GOLD_MS,
    TTFT_SILVER_MS,
    TTFT_THRESHOLD_MS,
    run_latency_pressure,
)

# ═══════════════════════════════════════════════════════════════
# Empty / invalid trajectory handling (3 tests)
# ═══════════════════════════════════════════════════════════════


class TestEmptyAndInvalid:
    def test_empty_trajectory_returns_zero(self):
        """Empty trajectory returns score 0.0 with empty findings."""
        score, findings, sub = run_latency_pressure([])
        assert score == 0.0
        assert findings == []
        assert sub["sample_count"] == 0

    def test_none_trajectory_returns_zero(self):
        """None trajectory returns score 0.0 with empty findings."""
        score, findings, sub = run_latency_pressure(None)
        assert score == 0.0
        assert findings == []
        assert sub["sample_count"] == 0

    def test_no_ttft_field_returns_zero_with_warning(self):
        """Actions without ttft_ms/latency_ms return 0.0 + WARNING finding."""
        traj = [{"action": "read"}, {"action": "write"}]
        score, findings, sub = run_latency_pressure(traj)
        assert score == 0.0
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARNING"
        assert findings[0]["category"] == "latency"
        assert sub["sample_count"] == 0


# ═══════════════════════════════════════════════════════════════
# Tiered scoring (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestTieredScoring:
    def test_all_below_gold_returns_100(self):
        """All TTFT ≤ Gold (200ms) returns score 100.0 with INFO finding."""
        traj = [{"ttft_ms": 100}, {"ttft_ms": 150}, {"ttft_ms": 200}]
        score, findings, _ = run_latency_pressure(traj)
        assert score == 100.0
        assert findings[0]["severity"] == "INFO"

    def test_all_below_silver_returns_85(self):
        """P99 in (200, 350] returns score 85.0 with INFO finding."""
        traj = [{"ttft_ms": 250}, {"ttft_ms": 300}, {"ttft_ms": 350}]
        score, findings, _ = run_latency_pressure(traj)
        assert score == 85.0
        assert findings[0]["severity"] == "INFO"

    def test_all_below_threshold_returns_70(self):
        """P99 in (350, 500] returns score 70.0 with WARNING finding."""
        traj = [{"ttft_ms": 400}, {"ttft_ms": 450}, {"ttft_ms": 500}]
        score, findings, _ = run_latency_pressure(traj)
        assert score == 70.0
        assert findings[0]["severity"] == "WARNING"

    def test_above_threshold_linear_decay(self):
        """P99 in (500, 1000) returns linearly decayed score with HIGH finding."""
        # P99 = 750ms → decay = 70 * (1 - (750-500)/500) = 70 * 0.5 = 35.0
        traj = [{"ttft_ms": 750}]
        score, findings, _ = run_latency_pressure(traj)
        assert score == pytest.approx(35.0, abs=0.1)
        assert findings[0]["severity"] == "HIGH"

    def test_above_2x_threshold_returns_zero(self):
        """P99 > 2x threshold (1000ms) returns 0.0 with CRITICAL finding."""
        traj = [{"ttft_ms": 1200}]
        score, findings, _ = run_latency_pressure(traj)
        assert score == 0.0
        assert findings[0]["severity"] == "CRITICAL"


# ═══════════════════════════════════════════════════════════════
# P99 calculation & field fallback (3 tests)
# ═══════════════════════════════════════════════════════════════


class TestP99AndFallback:
    def test_p99_calculation_correctness(self):
        """With 100 samples, P99 should be the 99th-percentile value.

        Nearest-rank method: P99 index = ceil(n*0.99)-1 = ceil(99.0)-1 = 98.
        With 98 samples at 100ms (indices 0-97) and 2 at 600ms (indices 98-99),
        sorted[98] = 600ms → P99 catches the slow outlier.
        """
        # 98 samples at 100ms + 2 at 600ms → P99 = 600ms (index 98)
        traj = [{"ttft_ms": 100}] * 98 + [{"ttft_ms": 600}] * 2
        score, findings, sub = run_latency_pressure(traj)
        assert sub["p99_ttft_ms"] == 600.0
        assert sub["sample_count"] == 100
        # 600ms is in decay range → score = 70 * (1 - (600-500)/500) = 70 * 0.8 = 56.0
        assert score == pytest.approx(56.0, abs=0.1)
        assert findings[0]["severity"] == "HIGH"

    def test_p99_small_sample_n2(self):
        """With n=2 samples, P99 should pick the larger value (index 1).

        Regression guard: the previous formula ``int(n*0.99)-1`` returned
        index 0 (smaller value) for n=2, underestimating P99. The fixed
        nearest-rank formula ``ceil(n*0.99)-1`` returns index 1.
        """
        traj = [{"ttft_ms": 100}, {"ttft_ms": 600}]
        _, _, sub = run_latency_pressure(traj)
        assert sub["p99_ttft_ms"] == 600.0  # larger value, not 100
        assert sub["sample_count"] == 2

    def test_latency_ms_field_fallback(self):
        """Actions using latency_ms (no ttft_ms) should also be extracted."""
        traj = [{"latency_ms": 100}, {"latency_ms": 150}]
        score, _, sub = run_latency_pressure(traj)
        assert sub["sample_count"] == 2
        assert score == 100.0  # Both ≤ Gold

    def test_invalid_ttft_values_skipped(self):
        """Non-positive or non-numeric ttft_ms values should be skipped."""
        traj = [
            {"ttft_ms": 100},
            {"ttft_ms": 0},  # skipped (not > 0)
            {"ttft_ms": -50},  # skipped (not > 0)
            {"ttft_ms": "fast"},  # skipped (not numeric)
            {"ttft_ms": 150},
        ]
        score, _, sub = run_latency_pressure(traj)
        assert sub["sample_count"] == 2  # only 100 and 150


# ═══════════════════════════════════════════════════════════════
# Subscore dict structure (2 tests)
# ═══════════════════════════════════════════════════════════════


class TestSubscoreStructure:
    def test_subscore_dict_keys(self):
        """Subscore dict should have p99_ttft_ms, threshold_ms, sample_count."""
        traj = [{"ttft_ms": 100}]
        _, _, sub = run_latency_pressure(traj)
        assert set(sub.keys()) == {"p99_ttft_ms", "threshold_ms", "sample_count"}

    def test_custom_threshold_respected(self):
        """Custom threshold_ms should appear in subscore and affect scoring."""
        traj = [{"ttft_ms": 600}]
        score, _, sub = run_latency_pressure(traj, threshold_ms=1000.0)
        assert sub["threshold_ms"] == 1000.0
        # 600ms ≤ 1000ms threshold but > Silver(350) → score 70.0 (Bronze tier)
        # Note: Gold/Silver tiers are fixed at 200/350ms regardless of threshold
        assert score == 70.0

    def test_threshold_constants_exist(self):
        """Module should export TTFT threshold constants."""
        assert TTFT_THRESHOLD_MS == 500.0
        assert TTFT_GOLD_MS == 200.0
        assert TTFT_SILVER_MS == 350.0
