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


__all__ = [
    "EVIDENCE_MODE_DECLARED",
    "EVIDENCE_MODE_VERIFIED_PATCH",
    "EVIDENCE_MODE_LIVE",
    "VALID_EVIDENCE_MODES",
    "CURRENT_EVIDENCE_MODE",
    "strongest_evidence_mode",
]
