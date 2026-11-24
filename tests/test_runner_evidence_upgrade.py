# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for evidence mode upgrade logic (offline, no Docker)."""

from __future__ import annotations

from mas_eval.evidence import (
    EVIDENCE_MODE_DECLARED,
    EVIDENCE_MODE_LIVE,
    EVIDENCE_MODE_VERIFIED_PATCH,
    ExecutionRecord,
)
from mas_eval.runner.evidence_upgrade import upgrade_evidence_mode


def _complete_record() -> ExecutionRecord:
    """A complete ExecutionRecord that satisfies is_complete()."""
    return ExecutionRecord(
        runner_id="local-cli-agent",
        task_id="astropy__astropy-12907",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
        exit_code=0,
        trajectory_sha256="a" * 64,
        runner_kind="agent",
    )


def _incomplete_record() -> ExecutionRecord:
    """An incomplete ExecutionRecord (missing sha256)."""
    return ExecutionRecord(
        runner_id="local-cli-agent",
        task_id="astropy__astropy-12907",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
        exit_code=0,
        trajectory_sha256="",  # incomplete
        runner_kind="agent",
    )


def _scripted_record() -> ExecutionRecord:
    """A complete record but with runner_kind != 'agent'."""
    return ExecutionRecord(
        runner_id="scripted-test",
        task_id="astropy__astropy-12907",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
        exit_code=0,
        trajectory_sha256="b" * 64,
        runner_kind="scripted",
    )


class TestUpgradeEvidenceMode:
    def test_verification_not_verified_patch_returns_declared(self):
        """When verification evidence_mode != verified_patch, return declared with empty reason."""
        verification = {"evidence_mode": EVIDENCE_MODE_DECLARED, "resolved": True}
        mode, reason = upgrade_evidence_mode(verification, _complete_record())

        assert mode == EVIDENCE_MODE_DECLARED
        assert reason == ""

    def test_verification_verified_patch_with_complete_record_returns_live(self):
        """verified_patch + complete agent record -> live_run, no downgrade."""
        verification = {"evidence_mode": EVIDENCE_MODE_VERIFIED_PATCH, "resolved": True}
        mode, reason = upgrade_evidence_mode(verification, _complete_record())

        assert mode == EVIDENCE_MODE_LIVE
        assert reason == ""

    def test_verification_verified_patch_with_none_record_returns_verified_patch_with_reason(self):
        """verified_patch + None record -> verified_patch with downgrade reason."""
        verification = {"evidence_mode": EVIDENCE_MODE_VERIFIED_PATCH, "resolved": True}
        mode, reason = upgrade_evidence_mode(verification, None)

        assert mode == EVIDENCE_MODE_VERIFIED_PATCH
        assert reason != ""
        assert "ExecutionRecord" in reason or "record" in reason.lower()

    def test_verification_verified_patch_with_incomplete_record_returns_verified_patch_with_reason(self):
        """verified_patch + incomplete record -> verified_patch with downgrade reason."""
        verification = {"evidence_mode": EVIDENCE_MODE_VERIFIED_PATCH, "resolved": True}
        mode, reason = upgrade_evidence_mode(verification, _incomplete_record())

        assert mode == EVIDENCE_MODE_VERIFIED_PATCH
        assert reason != ""
        assert "complete" in reason.lower() or "sha256" in reason.lower()

    def test_verification_verified_patch_with_scripted_record_returns_verified_patch_with_reason(self):
        """verified_patch + scripted runner_kind -> verified_patch with reason containing runner_kind."""
        verification = {"evidence_mode": EVIDENCE_MODE_VERIFIED_PATCH, "resolved": True}
        mode, reason = upgrade_evidence_mode(verification, _scripted_record())

        assert mode == EVIDENCE_MODE_VERIFIED_PATCH
        assert reason != ""
        assert "runner_kind" in reason or "scripted" in reason.lower() or "agent" in reason.lower()

    def test_empty_verification_dict_returns_declared(self):
        """Missing evidence_mode in verification defaults to declared path."""
        verification = {"resolved": True}
        mode, reason = upgrade_evidence_mode(verification, _complete_record())

        assert mode == EVIDENCE_MODE_DECLARED
        assert reason == ""