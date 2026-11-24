# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Upgrade evidence mode from verification result + execution record.

This module centralises the logic that takes a verification result (which may
claim ``verified_patch``) and an optional ``ExecutionRecord`` (from a real
agent run), and returns the final evidence mode plus a downgrade reason.
Both ``scripts/swebench_live_run.py`` and ``scripts/swebench_batch.py`` use
this function so the downgrade policy is identical and testable in one place.
"""

from __future__ import annotations

from typing import Any

from mas_eval.evidence import (
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_LIVE,
    EVIDENCE_MODE_VERIFIED_PATCH,
    ExecutionRecord,
    resolve_evidence_mode,
)

__all__ = ["upgrade_evidence_mode"]


def upgrade_evidence_mode(
    verification: dict[str, Any], record: ExecutionRecord | None
) -> tuple[str, str]:
    """Determine the final evidence mode and any downgrade reason.

    Args:
        verification: The result from ``SWEBenchOracle.verify_instance``.
            Must contain an ``evidence_mode`` key.
        record: The ``ExecutionRecord`` from the agent run, or ``None`` if
            no record was produced (e.g., the runner failed before emitting one).

    Returns:
        A tuple ``(evidence_mode, downgrade_reason)`` where:
        - ``evidence_mode`` is one of ``declared_input``, ``verified_patch``,
          or ``live_run``.
        - ``downgrade_reason`` is an empty string when no downgrade occurred,
          otherwise a human-readable explanation of why the mode was lowered.
    """
    if verification.get("evidence_mode") != EVIDENCE_MODE_VERIFIED_PATCH:
        return EVIDENCE_MODE_DECLARED, ""

    # Verification claims verified_patch. Try to upgrade to live_run.
    try:
        mode = resolve_evidence_mode(EVIDENCE_MODE_LIVE, record)
        return mode, ""
    except ValueError as exc:
        # Downgrade to verified_patch with the reason.
        return EVIDENCE_MODE_VERIFIED_PATCH, str(exc)