# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Evidence-mode contract for evaluation results.

``evidence_mode`` answers a single question: **where did the behaviour being
scored come from?**

- ``declared_input`` — the score is computed from caller-supplied artifacts
  (Agent Card JSON, golden/mock trajectories). This is what every current
  path does. It validates declarations and scoring consistency; it does NOT
  prove that an agent performed the task.
- ``live_run`` — the score is computed from a real execution (process/model
  invocation, real oracle environment). No current path sets this.

Consumers must not describe a ``declared_input`` score as an agent capability
benchmark. Adding a real runner is tracked separately (P0-2).
"""

from __future__ import annotations

EVIDENCE_MODE_DECLARED = "declared_input"
EVIDENCE_MODE_LIVE = "live_run"

VALID_EVIDENCE_MODES = frozenset({EVIDENCE_MODE_DECLARED, EVIDENCE_MODE_LIVE})

# Single switch to flip once a real execution path lands.
CURRENT_EVIDENCE_MODE = EVIDENCE_MODE_DECLARED

__all__ = [
    "EVIDENCE_MODE_DECLARED",
    "EVIDENCE_MODE_LIVE",
    "VALID_EVIDENCE_MODES",
    "CURRENT_EVIDENCE_MODE",
]
