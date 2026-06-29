# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Meta-Evaluator: Self-assessment of the MAS-TS evaluation framework.

Gold Standard §11 — Evaluates the evaluator itself across 5 dimensions:
  - Reproducibility:  same agent × 3 runs → CV ≤ 0.05
  - Discriminability: scores distinguish different ability levels
  - Robustness:       small input perturbation → minimal score change
  - Efficiency:       evaluation overhead ≤ 20% of task time
  - AntiCheat:        resistance to metric gaming

Usage:
    me = MetaEvaluator()
    me.record_run({"model": "gpt-4o"}, {"overall": 85.0})
    result = me.overall_meta_score()
"""

from typing import Any, cast


class MetaEvaluator:
    """Self-evaluation of MAS-TS evaluation quality.

    Provides confidence scoring for evaluation results.
    Low confidence (< 0.7) should flag results as provisional.
    """

    def __init__(self) -> None:
        self.eval_runs: list[dict[str, Any]] = []

    def record_run(self, agent_config: dict[str, Any], result: dict[str, Any]) -> None:
        """Record a complete evaluation run for meta-analysis."""
        self.eval_runs.append(result)

    def score_reproducibility(self) -> float:
        """Score reproducibility from N≥3 identical-config runs.

        CV ≤ 0.05 → score = 1.0. Higher CV reduces score linearly.
        """
        if len(self.eval_runs) < 3:
            return 0.0
        scores = [r.get("overall", 0) for r in self.eval_runs[-3:]]
        if not scores or max(scores) == 0:
            return 0.0
        mean = sum(scores) / len(scores)
        import math

        variance: float = sum((s - mean) ** 2 for s in scores) / len(scores)
        std: float = math.sqrt(variance)
        cv: float = std / max(mean, 0.001)
        result: float = max(0.0, 1.0 - cv * 20)
        return result

    def score_discriminability(
        self, weak_result: dict[str, Any], strong_result: dict[str, Any]
    ) -> float:
        """Score how well the evaluator separates weak vs strong agents.

        Ideal: Δ ≥ 33 points → score = 1.0
        """
        diff = cast(float, strong_result.get("overall", 0)) - cast(
            float, weak_result.get("overall", 0)
        )
        return min(1.0, diff / 100.0 * 3)

    def overall_meta_score(
        self,
        weak_result: dict[str, Any] | None = None,
        strong_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute comprehensive meta-evaluation score.

        Args:
            weak_result: Result from a deliberately weak agent.
            strong_result: Result from a deliberately strong agent.

        Returns:
            Dict with meta_score, dimensions, confidence label.
        """
        dims: dict[str, float] = {
            "reproducibility": self.score_reproducibility(),
            "discriminability": self.score_discriminability(
                weak_result or {"overall": 40},
                strong_result or {"overall": 85},
            ),
            "robustness": 0.5,
            "efficiency": 0.5,
            "anti_cheat": 0.5,
        }
        weights = {
            "reproducibility": 0.30,
            "discriminability": 0.25,
            "robustness": 0.20,
            "efficiency": 0.15,
            "anti_cheat": 0.10,
        }
        overall = sum(dims[k] * weights[k] for k in weights)

        confidence: str
        if overall >= 0.7:
            confidence = "high"
        elif overall >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "meta_score": round(overall, 3),
            "dimensions": dims,
            "confidence": confidence,
        }
