# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Pluggable verifier governance for MAS-TS-001 D5 + Loop Engineering.

Provides a registry of Verifier instances that can cross-validate evaluation
results, replacing mock-only scoring with real LLM-as-judge or oracle backends.
"""

import abc
import logging
from typing import Any

logger = logging.getLogger(__name__)


class Verifier(abc.ABC):
    """Abstract base for an evaluation verifier.

    Subclasses implement evaluate() to provide quality scores for task responses.
    Extend with LLM-as-judge, oracle comparison, or rule-based backends.
    """

    def __init__(self, name: str):
        self.name = name
        self._eval_count = 0
        self._accuracy: float | None = None

    @abc.abstractmethod
    def evaluate(self, task_id: str, responses: list[str]) -> dict[str, Any]:
        """Evaluate response quality for a given task.

        Args:
            task_id: Identifier for the task being evaluated.
            responses: List of response strings from the agent.

        Returns:
            Dict with at least {"score": float (0-100)}.
        """

    def record_accuracy(self, accuracy: float) -> None:
        self._accuracy = accuracy

    @property
    def eval_count(self) -> int:
        return self._eval_count

    @property
    def accuracy(self) -> float | None:
        return self._accuracy


class MockVerifier(Verifier):
    """Deterministic mock verifier for testing.

    Returns a fixed score regardless of input.
    Useful for test fixtures and CI scenarios.
    """

    def __init__(self, name: str, score: float = 85.0):
        super().__init__(name)
        self._fixed_score = score

    def evaluate(self, task_id: str, responses: list[str]) -> dict[str, Any]:
        self._eval_count += 1
        return {
            "verifier": self.name,
            "task_id": task_id,
            "score": self._fixed_score,
            "response_count": len(responses),
        }


class VerifierRegistry:
    """Registry of verifiers for cross-validation.

    Manages multiple Verifier instances and provides:
    - Individual evaluation via evaluate_all()
    - Consensus scoring via consensus_evaluate()
    - Verifier lifecycle (register/unregister/list)
    """

    def __init__(self) -> None:
        self._verifiers: dict[str, Verifier] = {}

    def register(self, verifier: Verifier) -> None:
        self._verifiers[verifier.name] = verifier
        logger.info("Registered verifier: %s", verifier.name)

    def unregister(self, name: str) -> None:
        self._verifiers.pop(name, None)

    def list_verifiers(self) -> list[str]:
        return list(self._verifiers.keys())

    def get(self, name: str) -> Verifier | None:
        return self._verifiers.get(name)

    def evaluate_all(self, task_id: str, responses: list[str]) -> list[dict[str, Any]]:
        """Evaluate task against all registered verifiers.

        Returns a list of result dicts, one per verifier.
        Failed verifiers return score=0 with an error field.
        """
        results: list[dict[str, Any]] = []
        for v in self._verifiers.values():
            try:
                r = v.evaluate(task_id, responses)
                results.append(r)
            except Exception as e:
                logger.error("Verifier %s failed: %s", v.name, e)
                results.append(
                    {
                        "verifier": v.name,
                        "task_id": task_id,
                        "score": 0.0,
                        "error": str(e),
                    }
                )
        return results

    def consensus_evaluate(self, task_id: str, responses: list[str]) -> dict[str, Any]:
        """Evaluate with cross-validation consensus.

        Runs all verifiers, computes average score, and measures
        inter-verifier agreement (proportion within 15 pts of average).

        Returns:
            Dict with consensus_score, individual_scores, agreement, verifier_count.
        """
        results = self.evaluate_all(task_id, responses)
        scores = [r["score"] for r in results if "error" not in r]

        if not scores:
            return {
                "consensus_score": 0.0,
                "individual_scores": results,
                "agreement": 0.0,
                "verifier_count": 0,
            }

        avg = sum(scores) / len(scores)
        agreements = [s for s in scores if abs(s - avg) <= 15.0]
        agreement_pct = len(agreements) / len(scores) if scores else 0.0

        return {
            "consensus_score": round(avg, 1),
            "individual_scores": results,
            "agreement": round(agreement_pct, 2),
            "verifier_count": len(scores),
        }
