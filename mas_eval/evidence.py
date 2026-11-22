# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Evidence-mode contract for evaluation results.

``evidence_mode`` answers a single question: **where did the behaviour being
scored come from?**

- ``declared_input`` — the score is computed from caller-supplied artifacts
  (Agent Card JSON, golden/mock trajectories). This validates declarations and
  scoring consistency; it does NOT prove that an agent performed the task.
- ``verified_patch`` — the caller supplied the patch/trajectory, but it was
  actually applied and its tests were executed in a real isolated environment
  (e.g. Docker). Stronger than ``declared_input``: the verification ran, the
  behaviour is still self-reported.
- ``live_run`` — the score is computed from a real agent execution that
  produced the trajectory (no current path sets this).

Ranking: ``live_run`` > ``verified_patch`` > ``declared_input``. When a result
mixes domains, the strongest evidence wins and is reported explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

EVIDENCE_MODE_DECLARED = "declared_input"
EVIDENCE_MODE_VERIFIED_PATCH = "verified_patch"
EVIDENCE_MODE_LIVE = "live_run"

VALID_EVIDENCE_MODES = frozenset(
    {EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_VERIFIED_PATCH, EVIDENCE_MODE_LIVE}
)

_RANK = {
    EVIDENCE_MODE_DECLARED: 0,
    EVIDENCE_MODE_VERIFIED_PATCH: 1,
    EVIDENCE_MODE_LIVE: 2,
}

# Single switch for paths that have no execution at all.
CURRENT_EVIDENCE_MODE = EVIDENCE_MODE_DECLARED


def strongest_evidence_mode(modes: Iterable[str | None]) -> str:
    """Return the strongest valid mode from an iterable.

    Unknown/missing values are ignored; an empty input yields
    ``declared_input`` (the weakest, safest claim).
    """
    valid = [m for m in modes if m in VALID_EVIDENCE_MODES]
    if not valid:
        return EVIDENCE_MODE_DECLARED
    return max(valid, key=_RANK.__getitem__)


_SHA256_HEX = set("0123456789abcdef")


@dataclass(frozen=True)
class ExecutionRecord:
    """Proof that a runner actually executed a task.

    ``live_run`` may only be claimed when a complete record exists. The record
    is deliberately small and serialisable so it can be stored next to the
    result and checked by consumers.
    """

    runner_id: str
    task_id: str
    started_at: str
    finished_at: str
    exit_code: int
    trajectory_sha256: str
    runner_kind: str = "agent"

    def is_complete(self) -> bool:
        digest = self.trajectory_sha256.lower()
        return (
            bool(self.runner_id.strip())
            and bool(self.task_id.strip())
            and bool(self.started_at.strip())
            and bool(self.finished_at.strip())
            and isinstance(self.exit_code, int)
            and len(digest) == 64
            and set(digest) <= _SHA256_HEX
        )


def resolve_evidence_mode(
    declared_mode: str, record: ExecutionRecord | None = None
) -> str:
    """Validate an evidence claim before it reaches a result.

    ``live_run`` is fail-closed: without a complete ``ExecutionRecord`` this
    raises instead of downgrading silently, so a missing runner cannot be
    papered over. A record produced by a non-agent runner (e.g. a scripted test
    double) is not allowed to claim ``live_run``.
    """
    if declared_mode not in VALID_EVIDENCE_MODES:
        raise ValueError(f"Unknown evidence mode: {declared_mode!r}")
    if declared_mode == EVIDENCE_MODE_LIVE:
        if record is None or not record.is_complete():
            raise ValueError(
                "live_run requires a complete ExecutionRecord "
                "(runner_id/task_id/started_at/finished_at/exit_code/sha256)"
            )
        if record.runner_kind != "agent":
            raise ValueError(
                f"live_run requires runner_kind='agent', got {record.runner_kind!r}"
            )
        return EVIDENCE_MODE_LIVE
    return declared_mode


__all__ = [
    "EVIDENCE_MODE_DECLARED",
    "EVIDENCE_MODE_VERIFIED_PATCH",
    "EVIDENCE_MODE_LIVE",
    "VALID_EVIDENCE_MODES",
    "CURRENT_EVIDENCE_MODE",
    "ExecutionRecord",
    "resolve_evidence_mode",
    "strongest_evidence_mode",
]
