# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for D4 Action Safety — Gold Standard agent action compliance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d4_action_safety import (
    run_action_safety,
    integrate_action_safety,
)


FULLY_COMPLIANT_CARD = {
    "authentication": {
        "type": "OAuth2",
        "scopes": ["read:users", "write:tasks", "admin:audit"],
    },
    "federation": {
        "cross_border_policy": {
            "data_residency": "CN",
            "allowed_transfer_zones": ["CN", "US"],
            "requires_approval": True,
        },
        "blocked_operations": ["rm", "drop_table", "shutdown"],
    },
    "governance": {
        "circuit_breaker": {"enabled": True, "threshold": 3, "cooldown_seconds": 30},
        "oscillation_detection": {"enabled": True, "window_size": 3},
        "state_machine_version": "v3.0",
    },
    "constitution": {
        "envelope": {
            "message_id": "msg-001",
            "correlation_id": "corr-001",
            "timestamp": "2026-07-01T00:00:00Z",
            "sender": "agent-a",
            "protocol": "mcp",
        }
    },
    "audit": {
        "trace_id_required": True,
        "timestamp_required": True,
    },
}

MINIMAL_CARD = {
    "authentication": {"type": "None"},
}

HITL_ONLY_CARD = {
    "federation": {
        "cross_border_policy": {"requires_approval": True},
    },
    "authentication": {"type": "None"},
}


class TestActionSafety:
    def test_fully_compliant(self):
        result = run_action_safety(FULLY_COMPLIANT_CARD)
        assert result["domain"] == "d4_action_safety"
        assert result["score"] >= 50.0
        assert len(result["findings"]) >= 6

    def test_minimal_card_low_score(self):
        result = run_action_safety(MINIMAL_CARD)
        assert result["score"] == 0.0
        critical = [f for f in result["findings"] if f.get("severity") == "CRITICAL"]
        assert any("hitl" in f.get("category", "").lower() for f in critical)

    def test_hitl_zeros_domain_when_missing(self):
        result = run_action_safety(MINIMAL_CARD)
        assert result["score"] == 0.0

    def test_hitl_without_approval_gives_low_subscore(self):
        card = dict(FULLY_COMPLIANT_CARD)
        card["federation"]["cross_border_policy"]["requires_approval"] = False
        result = run_action_safety(card)
        hitl_sub = result.get("subscores", {}).get("hitl_protection", 100)
        assert hitl_sub <= 50

    def test_integrate_with_d4(self):
        d4_mock = {"domain": "d4", "score": 75.0, "findings": [], "subscores": {}}
        as_result = run_action_safety(HITL_ONLY_CARD)
        merged = integrate_action_safety(d4_mock, as_result)
        assert merged["domain"] == "d4"
        assert "action_safety" in merged["subscores"]
        assert merged["score"] == round(75.0 * 0.70 + as_result["score"] * 0.30, 1)

    def test_findings_have_v2_fields(self):
        result = run_action_safety(FULLY_COMPLIANT_CARD)
        for f in result["findings"]:
            assert "layer" in f
            assert "root_cause" in f
            assert "reproducibility" in f
            assert "mitigation" in f
