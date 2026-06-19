# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for L4 multi-epoch evolution lifecycle."""

from typing import Any

from mas_eval.harness.epoch_state import EpochState
from mas_eval.harness.l4_evolution import run_l4_evolution

FINDING = {"severity": "WARNING", "category": "test", "detail": "warning"}


class TestEpochState:
    def test_init(self):
        state = EpochState()
        assert state.epoch == 0
        assert state.history == []

    def test_record_epoch(self):
        state = EpochState()
        findings = [{"severity": "INFO", "category": "test", "detail": "ok"}]
        state.record(1, 80.0, findings, "epoch 1")
        assert state.epoch == 1
        assert state.history == [
            {"epoch": 1, "score": 80.0, "findings": findings, "summary": "epoch 1"}
        ]

    def test_trend_improving(self):
        state = EpochState()
        state.record(1, 70.0, [])
        state.record(2, 75.0, [])
        state.record(3, 81.0, [])
        assert state.trend() == "improving"

    def test_trend_regressing(self):
        state = EpochState()
        state.record(1, 81.0, [])
        state.record(2, 75.0, [])
        state.record(3, 70.0, [])
        assert state.trend() == "regressing"

    def test_trend_stable(self):
        state = EpochState()
        state.record(1, 80.0, [])
        state.record(2, 81.0, [])
        state.record(3, 80.5, [])
        assert state.trend() == "stable"

    def test_epoch_improvement_pct(self):
        state = EpochState()
        state.record(1, 50.0, [])
        state.record(2, 75.0, [])
        assert state.improvement_pct() == 50.0

    def test_epoch_improvement_pct_zero_start(self):
        state = EpochState()
        state.record(1, 0.0, [])
        state.record(2, 5.0, [])
        assert state.improvement_pct() == 100.0


class TestRunL4EvolutionMultiEpoch:
    def test_multi_epoch(self):
        r = run_l4_evolution(max_epochs=3)
        assert r["epoch_count"] >= 2
        assert r["trend"] in ("improving", "regressing", "stable")
        assert isinstance(r["improvement_pct"], (int, float))

    def test_epoch_history_present(self):
        r = run_l4_evolution(max_epochs=2)
        assert len(r["epoch_history"]) >= 1
        for e in r["epoch_history"]:
            assert "epoch" in e
            assert "score" in e
            assert "seed" in e

    def test_early_convergence(self):
        r = run_l4_evolution(max_epochs=5, convergence_delta=50.0)
        assert r["epoch_count"] == 3

    def test_epoch_findings_do_not_compound_final_score_penalties(
        self, monkeypatch: Any
    ) -> None:
        def fake_run_d5(
            card: dict[str, Any] | None = None,
            seed: int | None = None,
            verifier_registry: Any = None,
        ) -> dict[str, Any]:
            return {
                "domain": "D5",
                "score": 90.0,
                "findings": [FINDING],
                "summary": "stable warning",
            }

        monkeypatch.setattr("mas_eval.harness.l4_evolution.run_d5", fake_run_d5)

        r = run_l4_evolution(max_epochs=3, convergence_delta=2.0)

        assert r["score"] == 90.0
        assert r["domain_scores"]["d5"] == 90.0
        assert len(r["findings"]) == 3
