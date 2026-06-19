# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Epoch state tracking for L4 evolution lifecycle."""

from typing import Any, cast


class EpochState:
    def __init__(self) -> None:
        self.epoch = 0
        self.history: list[dict[str, Any]] = []

    def record(
        self,
        epoch: int,
        score: float,
        findings: list[dict[str, Any]],
        summary: str = "",
    ) -> None:
        self.history.append(
            {
                "epoch": epoch,
                "score": float(score),
                "findings": findings,
                "summary": summary,
            }
        )
        self.epoch = epoch

    def trend(self) -> str:
        recent = self.history[-3:]
        if len(recent) < 2:
            return "stable"

        scores = [cast(float, entry["score"]) for entry in recent]
        diffs = [scores[index] - scores[index - 1] for index in range(1, len(scores))]
        avg_diff = sum(diffs) / len(diffs)

        if avg_diff > 2.0:
            return "improving"
        if avg_diff < -2.0:
            return "regressing"
        return "stable"

    def improvement_pct(self) -> float:
        if len(self.history) < 2:
            return 0.0

        first = cast(float, self.history[0]["score"])
        last = cast(float, self.history[-1]["score"])
        if first == 0:
            return 100.0 if last > 0 else 0.0
        return round(((last - first) / first) * 100, 1)

    @property
    def max_score(self) -> float:
        if not self.history:
            return 0.0
        return max(cast(float, entry["score"]) for entry in self.history)

    @property
    def min_score(self) -> float:
        if not self.history:
            return 0.0
        return min(cast(float, entry["score"]) for entry in self.history)

    @property
    def avg_score(self) -> float:
        if not self.history:
            return 0.0
        return round(
            sum(cast(float, entry["score"]) for entry in self.history)
            / len(self.history),
            1,
        )

    def clear(self) -> None:
        self.epoch = 0
        self.history.clear()
