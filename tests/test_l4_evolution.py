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
            multi_run_trajectories: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            return {
                "domain": "D5",
                "score": 90.0,
                "findings": [FINDING],
                "summary": "stable warning",
                "subscores": {
                    "chaos_engineering": 90.0,
                    "drift_detection": 90.0,
                    "reflection_loop": 90.0,
                    "convergence_cycle": 90.0,
                    "consistency_index": 0.0,
                },
                "consistency_index_detail": {},
                "consistency_index_enabled": False,
            }

        monkeypatch.setattr("mas_eval.harness.l4_evolution.run_d5", fake_run_d5)

        r = run_l4_evolution(max_epochs=3, convergence_delta=2.0)

        assert r["score"] == 90.0
        assert r["domain_scores"]["d5"] == 90.0
        assert len(r["findings"]) == 3


class TestRunL4EvolutionGoldStandardTrends:
    """Gold Standard v3.0-GA §9.2/§11 — L4 trend + meta-evaluation coverage."""

    def test_trends_block_present(self):
        r = run_l4_evolution(max_epochs=3)
        assert "trends" in r
        for key in ("cost_trend", "ci_trend", "trust_trend"):
            assert key in r["trends"], f"missing trend: {key}"

    def test_trend_lengths_match_epoch_count(self):
        r = run_l4_evolution(max_epochs=3, convergence_delta=0.0)
        n = r["epoch_count"]
        assert len(r["trends"]["cost_trend"]) == n
        assert len(r["trends"]["ci_trend"]) == n
        assert len(r["trends"]["trust_trend"]) == n

    def test_meta_evaluation_has_5_dimensions(self):
        r = run_l4_evolution(max_epochs=3)
        meta = r["meta_evaluation"]
        for dim in (
            "reproducibility",
            "discriminability",
            "robustness",
            "efficiency",
            "anti_cheat",
        ):
            assert dim in meta, f"missing meta-eval dimension: {dim}"
        assert "overall" in meta
        assert "low_confidence" in meta
        assert "eval_runs_count" in meta  # backward compat

    def test_meta_evaluation_overall_not_none(self):
        r = run_l4_evolution(max_epochs=3)
        assert r["meta_evaluation"]["overall"] is not None
        assert isinstance(r["meta_evaluation"]["overall"], float)

    def test_cost_trend_5_epochs(self):
        r = run_l4_evolution(max_epochs=5, convergence_delta=0.0)
        # convergence_delta=0 forces all 5 epochs (no early break)
        assert len(r["trends"]["cost_trend"]) == 5

    def test_ci_trend_each_epoch_has_value(self):
        r = run_l4_evolution(max_epochs=3, convergence_delta=0.0)
        for entry in r["trends"]["ci_trend"]:
            assert "epoch" in entry
            assert "ci" in entry
            assert isinstance(entry["ci"], float)

    def test_trust_trend_each_epoch_has_value(self):
        r = run_l4_evolution(max_epochs=3, convergence_delta=0.0)
        for entry in r["trends"]["trust_trend"]:
            assert "epoch" in entry
            assert "trust" in entry
            assert isinstance(entry["trust"], float)

    def test_declining_flags_are_booleans(self):
        r = run_l4_evolution(max_epochs=3, convergence_delta=0.0)
        assert isinstance(r["trends"]["cost_declining"], bool)
        assert isinstance(r["trends"]["ci_declining"], bool)
        assert isinstance(r["trends"]["trust_declining"], bool)
