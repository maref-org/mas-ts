# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 L0-L4 Executive Harness."""

import pytest

from mas_eval.harness.l0_fast_screen import (
    L0_STAGES,
    L0_TIMEOUT_SECONDS,
    run_l0_fast_screen,
)
from mas_eval.harness.l1_standard import run_l1_standard
from mas_eval.harness.l2_deep import run_l2_deep
from mas_eval.harness.l3_comprehensive import run_l3_comprehensive
from mas_eval.harness.l4_evolution import run_l4_evolution

SAMPLE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:harness-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "compliance": {
        "data_residency": "US",
        "data_classification": "internal",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": True,
    },
    "constitution": {
        "envelope": {
            "message_id": "msg-harness-001",
            "correlation_id": "corr-harness-001",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": "urn:agent:test:test:harness-001",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 30,
        "stale_node_timeout_seconds": 60,
    },
    "model_backend": {
        "provider": "test",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run commands",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_write",
            "description": "write files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["write"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "glob",
            "description": "glob",
            "input_schema": {},
            "output_schema": {},
            "examples": ["glob"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "grep",
            "description": "grep",
            "input_schema": {},
            "output_schema": {},
            "examples": ["grep"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_search",
            "description": "search",
            "input_schema": {},
            "output_schema": {},
            "examples": ["search"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["fetch"],
            "business_rule_version": "2026-05-01",
        },
    ],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
    "endpoints": {"a2a": "https://a2a.example.com", "mcp": "https://mcp.example.com"},
    "dependencies": ["git", "nodejs"],
    "orchestration_hints": {
        "agent_count": 3,
        "parallel_execution": True,
        "parallel_safe": True,
        "stateful": True,
        "preferred_role": "worker",
    },
    "message_format": {"protocol": "json-rpc-2.0", "transport": "stdio"},
}


class TestL0Stages:
    def test_l0_stages_defined(self):
        assert len(L0_STAGES) == 6
        assert "card_validation" in L0_STAGES
        assert "step_efficiency" in L0_STAGES
        assert "traffic_light" in L0_STAGES

    def test_timeout_constant(self):
        assert L0_TIMEOUT_SECONDS == 300


class TestRunL0FastScreen:
    def test_returns_dict(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert isinstance(result, dict)

    def test_has_all_keys(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert result["level"] == "L0"
        assert "stages" in result
        assert "summary" in result
        assert "elapsed_seconds" in result
        assert "status" in result

    def test_has_five_stages(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert len(result["stages"]) == 6

    def test_stages_have_expected_names(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        names = [s["stage"] for s in result["stages"]]
        assert names == L0_STAGES

    def test_each_stage_has_status(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        for s in result["stages"]:
            assert s["status"] in ("PASS", "FAIL", "WARNING", "SKIP")

    def test_each_stage_has_score(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        for s in result["stages"]:
            assert isinstance(s["score"], (int, float))

    def test_summary_maps_stages(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        for s in result["stages"]:
            assert s["stage"] in result["summary"]

    def test_elapsed_reasonable(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert result["elapsed_seconds"] < 5

    def test_status_is_valid(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert result["status"] in ("PASS", "FAIL", "WARNING")

    def test_with_tasks(self):
        result = run_l0_fast_screen(SAMPLE_CARD, tasks=[{"id": "t1"}])
        assert result["level"] == "L0"

    def test_reproducible(self):
        r1 = run_l0_fast_screen(SAMPLE_CARD)
        r2 = run_l0_fast_screen(SAMPLE_CARD)
        assert r1["status"] == r2["status"]


class TestRunL1Standard:
    def test_returns_dict(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert isinstance(r, dict)

    def test_has_level(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert r["level"] == "L1"

    def test_has_domain_scores(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert "d1" in r["domain_scores"]
        assert "d2" in r["domain_scores"]
        assert "d3" in r["domain_scores"]

    def test_all_scores_are_floats(self):
        r = run_l1_standard(SAMPLE_CARD)
        for v in r["domain_scores"].values():
            assert isinstance(v, (int, float))

    def test_has_verdict(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert r["verdict"] in ("APPROVED", "CONDITIONAL", "BLOCKED")

    def test_score_in_range(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert 0 <= r["score"] <= 100

    def test_has_findings(self):
        r = run_l1_standard(SAMPLE_CARD)
        assert isinstance(r["findings"], list)

    def test_accepts_explicit_d2_trajectories(self):
        event = {"action": {"type": "tool_call", "tool_id": "file_read", "input": {}}}
        r = run_l1_standard(
            SAMPLE_CARD,
            golden_trajectory=[event],
            mock_trajectory=[event],
        )
        assert r["level"] == "L1"


class TestRunL2Deep:
    def test_returns_dict(self):
        r = run_l2_deep(SAMPLE_CARD)
        assert isinstance(r, dict)

    def test_has_level(self):
        r = run_l2_deep(SAMPLE_CARD)
        assert r["level"] == "L2"

    def test_has_four_domains(self):
        r = run_l2_deep(SAMPLE_CARD)
        assert len(r["domain_scores"]) == 4

    def test_has_d4_score(self):
        r = run_l2_deep(SAMPLE_CARD)
        assert "d4" in r["domain_scores"]

    def test_score_in_range(self):
        r = run_l2_deep(SAMPLE_CARD)
        assert 0 <= r["score"] <= 100


class TestRunL3Comprehensive:
    def test_returns_dict(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert isinstance(r, dict)

    def test_has_level(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert r["level"] == "L3"

    def test_has_five_domains(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert len(r["domain_scores"]) == 5

    def test_has_d5_score(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert "d5" in r["domain_scores"]

    def test_score_in_range(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert 0 <= r["score"] <= 100

    def test_d5_score_plausible(self):
        r = run_l3_comprehensive(SAMPLE_CARD)
        assert 0 <= r["domain_scores"]["d5"] <= 100


class TestRunL4Evolution:
    def test_returns_dict(self):
        r = run_l4_evolution()
        assert isinstance(r, dict)

    def test_has_level(self):
        r = run_l4_evolution()
        assert r["level"] == "L4"

    def test_has_d5_score(self):
        r = run_l4_evolution()
        assert "d5" in r["domain_scores"]

    def test_score_in_range(self):
        r = run_l4_evolution()
        assert 0 <= r["score"] <= 100

    def test_findings_present(self):
        r = run_l4_evolution()
        assert isinstance(r["findings"], list)
        assert len(r["findings"]) > 0


class TestTasksParameterDeprecation:
    """Phase 6.4: `tasks=` is deprecated alias for `golden_trajectory=`
    in L1/L2/L3 wrappers. Must emit DeprecationWarning when used."""

    def test_l1_tasks_param_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="tasks"):
            run_l1_standard(SAMPLE_CARD, tasks=[])

    def test_l1_golden_trajectory_does_not_warn(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run_l1_standard(SAMPLE_CARD, golden_trajectory=[])
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations == [], (
            f"golden_trajectory= should not trigger DeprecationWarning, "
            f"got: {[str(w.message) for w in deprecations]}"
        )

    def test_l1_tasks_alias_routes_to_golden_trajectory(self):
        """`tasks=` argument must still forward to D2 as golden_trajectory
        so existing callers continue to function during deprecation window."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r1 = run_l1_standard(SAMPLE_CARD, tasks=[])
            r2 = run_l1_standard(SAMPLE_CARD, golden_trajectory=[])
        assert r1["domain_scores"]["d2"] == r2["domain_scores"]["d2"]

    def test_l2_tasks_param_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="tasks"):
            run_l2_deep(SAMPLE_CARD, tasks=[])

    def test_l3_tasks_param_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="tasks"):
            run_l3_comprehensive(SAMPLE_CARD, tasks=[])

    def test_l1_no_warning_when_neither_tasks_nor_golden_trajectory(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run_l1_standard(SAMPLE_CARD)
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations == []
