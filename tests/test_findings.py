# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0-GA Findings Schema v2."""

import pytest

from mas_eval.scoring.findings import (
    ROOT_CAUSES,
    SEVERITY_LEVELS,
    Finding,
    legacy_to_v2,
)


class TestFindingCreation:
    def test_valid_finding(self):
        f = Finding(
            severity="HIGH",
            category="step_efficiency_poor",
            detail="Optimality ratio 0.25",
            layer="tool",
            root_cause="plan_quality",
        )
        assert f.severity == "HIGH"
        assert f.root_cause == "plan_quality"

    def test_default_values(self):
        f = Finding(severity="INFO", category="test", detail="test")
        assert f.layer == "tool"
        assert f.root_cause == "unknown"
        assert f.reproducibility == "stochastic"
        assert f.mitigation == "auto_recovery"

    def test_invalid_severity(self):
        with pytest.raises(AssertionError):
            Finding(severity="INVALID", category="test", detail="test")

    def test_invalid_layer(self):
        with pytest.raises(AssertionError):
            Finding(severity="WARNING", category="test", detail="test", layer="invalid")

    def test_invalid_root_cause(self):
        with pytest.raises(AssertionError):
            Finding(
                severity="WARNING",
                category="test",
                detail="test",
                root_cause="invalid_cause",
            )

    def test_all_severity_levels(self):
        for s in SEVERITY_LEVELS:
            f = Finding(severity=s, category="test", detail="test")
            assert f.severity == s

    def test_all_root_causes(self):
        for rc in ROOT_CAUSES:
            f = Finding(
                severity="INFO",
                category="test",
                detail="test",
                root_cause=rc,
            )
            assert f.root_cause == rc


class TestFindingToDict:
    def test_to_dict_contains_all_fields(self):
        f = Finding(
            severity="CRITICAL",
            category="action_safety_no_hitl",
            detail="No irreversible op protection",
            layer="safety",
            root_cause="permission_violation",
            reproducibility="deterministic",
            mitigation="manual_intervention",
        )
        d = f.to_dict()
        assert d["severity"] == "CRITICAL"
        assert d["layer"] == "safety"
        assert d["root_cause"] == "permission_violation"
        assert d["mitigation"] == "manual_intervention"
        assert d["reproducibility"] == "deterministic"

    def test_to_dict_backward_compatible(self):
        """v3.0 community edition only has severity/category/detail."""
        f = Finding(severity="HIGH", category="test", detail="test message")
        d = f.to_dict()
        assert d["severity"] == "HIGH"
        assert d["category"] == "test"
        assert d["detail"] == "test message"


class TestLegacyToV2:
    def test_upgrade_minimal(self):
        old = {"severity": "WARNING", "category": "old_cat", "detail": "old msg"}
        f = legacy_to_v2(old)
        assert f.severity == "WARNING"
        assert f.category == "old_cat"
        assert f.detail == "old msg"
        assert f.layer == "tool"  # default
        assert f.root_cause == "unknown"  # default

    def test_upgrade_with_optional_fields(self):
        old = {
            "severity": "CRITICAL",
            "category": "test",
            "detail": "msg",
            "layer": "safety",
            "root_cause": "data_leakage",
        }
        f = legacy_to_v2(old)
        assert f.layer == "safety"
        assert f.root_cause == "data_leakage"

    def test_upgrade_missing_fields_default(self):
        old: dict = {}
        f = legacy_to_v2(old)
        assert f.severity == "INFO"
        assert f.category == "uncategorized"
        assert f.detail == ""
