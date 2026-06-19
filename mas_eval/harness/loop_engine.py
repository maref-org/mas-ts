# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Reusable iterative evaluation loop with convergence detection.

Wraps any harness-level runner with iteration tracking, convergence criteria,
regression detection, and timeout-based graceful termination.
"""

import logging
import time

logger = logging.getLogger(__name__)


class ConvergenceLoop:
    """Iterative evaluation loop with convergence detection.

    Wraps a harness runner and re-runs it until convergence criteria are met.
    Tracks full iteration history for score trajectory analysis.

    Convergence criteria (any triggers stop):
    1. Score delta < convergence_delta over last 3 iterations (converged)
    2. Max iterations reached (max_iterations)
    3. Wall clock > timeout_seconds (timeout)
    4. Score drops by > regression_threshold (regression)
    """

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_delta: float = 0.5,
        regression_threshold: float = -20.0,
        timeout_seconds: float = 3600,
    ):
        self.max_iterations = max_iterations
        self.convergence_delta = convergence_delta
        self.regression_threshold = regression_threshold
        self.timeout_seconds = timeout_seconds
        self.history: list[dict] = []

    def run(self, card, runner_fn, **runner_kwargs):
        """Run evaluation in a convergence loop.

        Args:
            card: Agent card dict.
            runner_fn: Callable that accepts (card, **runner_kwargs) and returns
                       dict with at minimum {"score": float, "findings": list}.
            **runner_kwargs: Additional kwargs forwarded to runner_fn.

        Returns:
            Dict with keys: final_score, iterations, converged, stop_reason,
            score_trajectory, history, findings.
        """
        self.history = []
        start_time = time.time()
        stop_reason = "max_iterations"

        for iteration in range(1, self.max_iterations + 1):
            if time.time() - start_time > self.timeout_seconds:
                stop_reason = "timeout"
                logger.warning(
                    "ConvergenceLoop timed out after %d iterations",
                    iteration - 1,
                )
                break

            result = runner_fn(card, **runner_kwargs)
            score = result.get("score", 0.0)
            entry = {
                "iteration": iteration,
                "score": score,
                "findings": result.get("findings", []),
                "domain_scores": result.get("domain_scores", {}),
                "elapsed_seconds": round(time.time() - start_time, 1),
            }
            self.history.append(entry)
            logger.info("Iteration %d: score=%.1f", iteration, score)

            if len(self.history) >= 3:
                prev_scores = [h["score"] for h in self.history[-3:]]
                deltas = [
                    prev_scores[i] - prev_scores[i - 1]
                    for i in range(1, len(prev_scores))
                ]

                if any(d < self.regression_threshold for d in deltas):
                    stop_reason = "regression"
                    logger.warning(
                        "Score regression detected at iteration %d", iteration
                    )
                    break

                if all(abs(d) < self.convergence_delta for d in deltas):
                    stop_reason = "converged"
                    logger.info(
                        "Converged at iteration %d (max Δ=%.2f)",
                        iteration,
                        max(abs(d) for d in deltas),
                    )
                    break

        trajectory = [h["score"] for h in self.history]
        all_findings = []
        for h in self.history:
            all_findings.extend(h.get("findings", []))

        return {
            "final_score": trajectory[-1] if trajectory else 0.0,
            "iterations": len(self.history),
            "converged": stop_reason == "converged",
            "stop_reason": stop_reason,
            "score_trajectory": trajectory,
            "history": self.history,
            "findings": all_findings,
        }
