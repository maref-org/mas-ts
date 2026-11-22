# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Guard tests: ``live_run`` cannot be claimed without a runner record.

This is the v1.1 contract. The runner itself is not implemented yet, so the
only thing that can be tested today is that the claim is fail-closed.
"""

from __future__ import annotations

from typing import Any

import pytest

from mas_eval.evidence import (
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_LIVE,
    EVIDENCE_MODE_VERIFIED_PATCH,
    ExecutionRecord,
    resolve_evidence_mode,
)

VALID_SHA = "a" * 64


def _record(**overrides: Any) -> ExecutionRecord:
    values: dict[str, Any] = {
        "runner_id": "runner-01",
        "task_id": "task-01",
        "started_at": "2026-11-22T10:00:00Z",
        "finished_at": "2026-11-22T10:00:05Z",
        "exit_code": 0,
        "trajectory_sha256": VALID_SHA,
    }
    values.update(overrides)
    return ExecutionRecord(**values)


def test_complete_record_is_valid():
    assert _record().is_complete() is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"runner_id": "  "},
        {"task_id": ""},
        {"started_at": ""},
        {"finished_at": ""},
        {"exit_code": 0.0},
        {"trajectory_sha256": ""},
        {"trajectory_sha256": "abc"},
        {"trajectory_sha256": "z" * 64},
    ],
)
def test_incomplete_record_is_rejected(overrides):
    assert _record(**overrides).is_complete() is False


def test_live_run_without_record_raises():
    with pytest.raises(ValueError, match="ExecutionRecord"):
        resolve_evidence_mode(EVIDENCE_MODE_LIVE)


def test_live_run_with_incomplete_record_raises():
    with pytest.raises(ValueError, match="ExecutionRecord"):
        resolve_evidence_mode(EVIDENCE_MODE_LIVE, _record(exit_code=0.0))


def test_live_run_with_complete_record_is_allowed():
    assert (
        resolve_evidence_mode(EVIDENCE_MODE_LIVE, _record())
        == EVIDENCE_MODE_LIVE
    )


def test_live_run_rejects_non_agent_runner():
    with pytest.raises(ValueError, match="runner_kind='agent'"):
        resolve_evidence_mode(
            EVIDENCE_MODE_LIVE, _record(runner_kind="scripted")
        )


def test_weaker_modes_pass_through_without_record():
    assert (
        resolve_evidence_mode(EVIDENCE_MODE_DECLARED)
        == EVIDENCE_MODE_DECLARED
    )
    assert (
        resolve_evidence_mode(EVIDENCE_MODE_VERIFIED_PATCH)
        == EVIDENCE_MODE_VERIFIED_PATCH
    )


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown evidence mode"):
        resolve_evidence_mode("trust_me")
