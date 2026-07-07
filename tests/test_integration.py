# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""End-to-end integration tests for MAS-TS-001 v3.0 pipeline.

Tests the full flow: Agent Card → D1-D5 domain evaluation → L0/L3 harness → report.
"""

import json
import time

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.domains.d5_robustness import run_d5
from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
from mas_eval.harness.l3_comprehensive import run_l3_comprehensive
from mas_eval.scoring.absolute import compute_overall, determine_verdict, score_to_grade

SAMPLE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:test:integration-001",
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
            "message_id": "msg-int-001",
            "correlation_id": "corr-int-001",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": "urn:agent:test:test:integration-001",
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
            # v0.8.0 D1.14: declare sub_permissions for high-risk capabilities
            "sub_permissions": {
                "env_read": "bash can read environment variables (declared)",
                "timezone_read": "bash can read timezone info (declared)",
                "network_access": "bash can make network calls (declared)",
            },
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-05-01",
            "sub_permissions": {
                "system_files": "file_read can access /etc, /proc, /sys (declared)",
                "credential_files": "file_read can access ~/.ssh, ~/.aws (declared)",
            },
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-05-01",
            "sub_permissions": {
                "system_files": "file_edit can modify /etc, /proc, /sys (declared)",
                "credential_files": "file_edit can modify ~/.ssh, ~/.aws (declared)",
            },
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


class TestD1D5Pipeline:
    def test_all_domains_run(self):
        d1 = run_d1(SAMPLE_CARD)
        d2 = run_d2(SAMPLE_CARD, [])
        d3 = run_d3(SAMPLE_CARD)
        d4 = run_d4(SAMPLE_CARD)
        d5 = run_d5()

        assert d1["domain"] == "D1"
        assert d2["domain"] == "D2"
        assert d3["domain"] == "D3"
        assert d4["domain"] == "D4"
        assert d5["domain"] == "D5"

    def test_all_domain_scores_in_range(self):
        d1 = run_d1(SAMPLE_CARD)
        d2 = run_d2(SAMPLE_CARD, [])
        d3 = run_d3(SAMPLE_CARD)
        d4 = run_d4(SAMPLE_CARD)
        d5 = run_d5()

        for name, result in [
            ("D1", d1),
            ("D2", d2),
            ("D3", d3),
            ("D4", d4),
            ("D5", d5),
        ]:
            assert 0 <= result["score"] <= 100, (
                f"{name} score {result['score']} out of range"
            )

    def test_all_domains_have_findings(self):
        d1 = run_d1(SAMPLE_CARD)
        d2 = run_d2(SAMPLE_CARD, [])
        d3 = run_d3(SAMPLE_CARD)
        d4 = run_d4(SAMPLE_CARD)
        d5 = run_d5()

        for name, result in [
            ("D1", d1),
            ("D2", d2),
            ("D3", d3),
            ("D4", d4),
            ("D5", d5),
        ]:
            assert isinstance(result.get("findings"), list), f"{name} missing findings"
            assert len(result["findings"]) > 0, f"{name} has no findings"

    def test_overall_score_composition(self):
        d1 = run_d1(SAMPLE_CARD)
        d2 = run_d2(SAMPLE_CARD, [])
        d3 = run_d3(SAMPLE_CARD)
        d4 = run_d4(SAMPLE_CARD)
        d5 = run_d5()

        overall = compute_overall(
            d1=d1["score"],
            d2=d2["score"],
            d3=d3["score"],
            d4=d4["score"],
            d5=d5["score"],
        )
        assert 0 <= overall <= 100

        grade = score_to_grade(overall)
        assert grade in (
            "A+",
            "A",
            "A-",
            "B+",
            "B",
            "B-",
            "C+",
            "C",
            "C-",
            "D+",
            "D",
            "D-",
            "F",
        )

    def test_verdict_determined(self):
        d1 = run_d1(SAMPLE_CARD)
        d2 = run_d2(SAMPLE_CARD, [])
        d3 = run_d3(SAMPLE_CARD)
        d4 = run_d4(SAMPLE_CARD)
        d5 = run_d5()

        all_findings = (
            d1["findings"]
            + d2["findings"]
            + d3["findings"]
            + d4["findings"]
            + d5["findings"]
        )
        overall = compute_overall(
            d1=d1["score"],
            d2=d2["score"],
            d3=d3["score"],
            d4=d4["score"],
            d5=d5["score"],
        )
        verdict = determine_verdict(overall, findings=all_findings)
        assert verdict in ("APPROVED", "CONDITIONAL", "BLOCKED")

    def test_full_pipeline_under_5_seconds(self):
        t0 = time.time()
        run_d1(SAMPLE_CARD)
        run_d2(SAMPLE_CARD, [])
        run_d3(SAMPLE_CARD)
        run_d4(SAMPLE_CARD)
        run_d5()
        elapsed = time.time() - t0
        assert elapsed < 5, f"Pipeline took {elapsed:.2f}s"


class TestL0Pipeline:
    def test_l0_accepts_sample_card(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert result["level"] == "L0"
        assert result["status"] in ("PASS", "WARNING")

    def test_l0_under_2_seconds(self):
        t0 = time.time()
        run_l0_fast_screen(SAMPLE_CARD)
        assert time.time() - t0 < 2

    def test_l0_has_6_stages(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        assert len(result["stages"]) == 6
        stage_names = [s["stage"] for s in result["stages"]]
        assert stage_names == [
            "card_validation",
            "constitution_check",
            "mock_tasks",
            "agent_spawn",
            "step_efficiency",
            "traffic_light",
        ]

    def test_l0_each_stage_has_score(self):
        result = run_l0_fast_screen(SAMPLE_CARD)
        for s in result["stages"]:
            assert isinstance(s["score"], (int, float))
            assert 0 <= s["score"] <= 100


class TestL3Pipeline:
    def test_l3_accepts_sample_card(self):
        result = run_l3_comprehensive(SAMPLE_CARD)
        assert result["level"] == "L3"
        assert 0 <= result["score"] <= 100

    def test_l3_has_5_domain_scores(self):
        result = run_l3_comprehensive(SAMPLE_CARD)
        assert len(result["domain_scores"]) == 5
        assert set(result["domain_scores"].keys()) == {"d1", "d2", "d3", "d4", "d5"}

    def test_l3_under_3_seconds(self):
        t0 = time.time()
        run_l3_comprehensive(SAMPLE_CARD)
        assert time.time() - t0 < 3

    def test_l3_has_verdict(self):
        result = run_l3_comprehensive(SAMPLE_CARD)
        assert result["verdict"] in ("GOLD", "SILVER", "BRONZE", "FAIL")


class TestCLIEntryPoints:
    def test_fast_screen_v3_flag(self):
        import os
        import subprocess
        import sys
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_CARD, f)
            card_path = f.name
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    "mas_fast_screen.py",
                    "--engine",
                    "v3",
                    "--card",
                    card_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert r.returncode == 0
        finally:
            os.unlink(card_path)

    def test_full_run_v3_flag(self):
        import os
        import subprocess
        import sys
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_CARD, f)
            card_path = f.name
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    "mas_full_run.py",
                    "--engine",
                    "v3",
                    "--level",
                    "L1",
                    "--card",
                    card_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert r.returncode == 0
        finally:
            os.unlink(card_path)


class TestScoringPipeline:
    def test_elo_leaderboard(self):
        from mas_eval.scoring.elo import EloRating

        elo = EloRating()
        for i in range(5):
            elo.add_contestant(f"agent_{i}")
        elo.record_match("agent_0", "agent_1", 90, 70)
        elo.record_match("agent_2", "agent_3", 85, 75)
        elo.record_match("agent_0", "agent_4", 95, 60)
        lb = elo.leaderboard()
        assert len(lb) == 5
        assert lb[0]["elo"] >= lb[-1]["elo"]

    def test_elo_confidence_interval(self):
        from mas_eval.scoring.elo import EloRating

        elo = EloRating()
        for i in range(60):
            elo.record_match(f"opp_{i}", "target", 80, 70)
        ci = elo.confidence_interval("target")
        assert ci is not None
        assert ci["ci_lower"] < ci["rating"] < ci["ci_upper"]

    # ═══════════════════════════════════════════════════════════
    # Gold Standard Pipeline Tests
    # ═══════════════════════════════════════════════════════════

    def test_gold_pipeline_step_efficiency(self):
        """Full pipeline with step efficiency scoring."""
        from mas_eval.domains.d2_single_agent import run_step_efficiency

        scenario = {"expected_steps": "3-5"}
        trajectory = {
            "events": [
                {"action": {"type": "tool_call", "tool_id": "grep", "is_retry": False}},
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_read",
                        "is_retry": False,
                    }
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_edit",
                        "is_retry": False,
                    }
                },
            ]
        }
        score, findings = run_step_efficiency(trajectory, scenario)
        assert score >= 60, f"StepEfficiency score too low: {score}"

    def test_gold_pipeline_trajectory_quality(self):
        """Full pipeline with trajectory quality scoring."""
        from mas_eval.domains.d2_single_agent import run_trajectory_quality

        golden = {
            "events": [
                {"action": {"type": "tool_call", "tool_id": "grep"}},
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_read",
                        "reasoning": "check content",
                    }
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_edit",
                        "reasoning": "apply fix",
                    }
                },
            ]
        }
        score, findings = run_trajectory_quality(golden, golden)
        assert score >= 80, f"TrajectoryQuality score too low: {score}"

    def test_gold_pipeline_tool_selection(self):
        """Full pipeline with tool selection correctness."""
        from mas_eval.domains.d2_single_agent import run_tool_selection_correctness

        trajectory = {
            "events": [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "grep",
                        "input": {"pattern": "TODO"},
                    }
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_read",
                        "input": {"path": "main.py"},
                    }
                },
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "file_edit",
                        "input": {"path": "main.py", "content": "fix"},
                    }
                },
            ]
        }
        score, findings = run_tool_selection_correctness(
            trajectory, ["grep", "file_read", "file_edit"]
        )
        assert score >= 70, f"ToolSelection score too low: {score}"

    def test_gold_scoring(self):
        """Gold scoring with cross-cutting adjustments."""
        from mas_eval.scoring.absolute import (
            compute_gold_overall,
            determine_gold_verdict,
        )

        overall = compute_gold_overall(
            d1=95,
            d2=88,
            d3=82,
            d4=90,
            d5=85,
            consistency_index=0.80,
            cost_efficiency=0.70,
        )
        assert overall >= 80
        verdict = determine_gold_verdict(overall, consistency_index=0.80)
        assert verdict in ("GOLD", "SILVER")

    def test_gold_verdict_critical_block(self):
        """Gold verdict blocked by CRITICAL finding."""
        from mas_eval.scoring.absolute import (
            compute_gold_overall,
            determine_gold_verdict,
        )

        overall = compute_gold_overall(
            d1=95,
            d2=88,
            d3=82,
            d4=90,
            d5=85,
            consistency_index=0.80,
        )
        verdict = determine_gold_verdict(
            overall,
            findings=[{"severity": "CRITICAL", "layer": "tool"}],
            consistency_index=0.80,
        )
        assert verdict != "GOLD", "CRITICAL finding should block GOLD verdict"

    def test_gold_aggregation_report(self):
        """Gold aggregation report from harness."""
        from mas_eval.harness.aggregation import compute_gold_report

        domain_results = {
            "d1": {"score": 95, "findings": []},
            "d2": {"score": 88, "findings": [{"severity": "INFO", "category": "test"}]},
            "d3": {"score": 82, "findings": []},
            "d4": {"score": 90, "findings": []},
            "d5": {"score": 85, "findings": []},
        }
        report = compute_gold_report(
            domain_results, consistency_index=0.80, cost_efficiency=0.70
        )
        assert report["overall"] >= 80
        assert report["gold_verdict"] in ("GOLD", "SILVER")
        assert report["consistency_index"] == 0.80
        assert report["cost_efficiency"] == 0.70

    # ═══════════════════════════════════════════════════════════
    # Phase 2: Coordination Efficiency + Consistency Index
    # ═══════════════════════════════════════════════════════════

    def test_gold_pipeline_coordination_efficiency(self):
        """Full pipeline with coordination efficiency scoring."""
        from mas_eval.domains.d3_multi_agent import run_coordination_efficiency

        msgs = [
            {
                "message_type": "request",
                "source_agent": "a1",
                "target_agent": "a2",
                "latency_ms": 100,
                "is_coordination": True,
                "is_waiting_response": False,
            },
            {"action": {"type": "tool_call"}, "latency_ms": 50},
            {
                "message_type": "response",
                "source_agent": "a2",
                "target_agent": "a1",
                "latency_ms": 50,
                "is_coordination": True,
                "is_waiting_response": False,
            },
        ]
        score, findings = run_coordination_efficiency(msgs)
        assert score >= 50
        assert any(f["category"] == "coordination_efficiency" for f in findings)

    def test_gold_pipeline_plan_quality(self):
        """Full pipeline with plan quality scoring."""
        from mas_eval.domains.d3_multi_agent import run_plan_quality

        plan = [
            {"action": {"type": "tool_call", "tool_id": "grep"}},
            {"action": {"type": "tool_call", "tool_id": "file_read"}},
            {"action": {"type": "tool_call", "tool_id": "file_edit"}},
        ]
        score, findings = run_plan_quality(plan, actual_trajectory=plan)
        assert score >= 85
        assert any(f["category"] == "plan_quality" for f in findings)

    def test_gold_pipeline_consistency_index(self):
        """Full pipeline with consistency index."""
        from mas_eval.domains.d5_robustness import ConsistencyIndex

        ci = ConsistencyIndex()
        for _ in range(3):
            ci.add_run(
                {
                    "result": {"value": 42},
                    "elapsed_seconds": 10.0,
                    "events": [{"action": {"type": "tool_call", "tool_id": "grep"}}],
                }
            )
        result = ci.score()
        assert result["ci"] >= 0.9
        assert "c_task" in result["dimensions"]

    # ═══════════════════════════════════════════════════════════
    # Phase 3: Action Safety + Federation Cascade
    # ═══════════════════════════════════════════════════════════

    def test_gold_pipeline_action_safety(self):
        """Full pipeline with action safety scoring."""
        from mas_eval.domains.d4_governance_security import run_action_safety

        card = {
            "authentication": {"type": "OAuth2", "scopes": ["file_read", "file_write"]},
            "constitution": {"data_sanitizer": True, "prompt_guard": True},
            "governance": {
                "human_in_the_loop": {"required_for": ["delete"]},
                "compensating_transactions": True,
            },
        }
        score, findings = run_action_safety(card)
        assert score >= 50
        assert any(f["category"] == "action_safety" for f in findings)

    def test_gold_pipeline_federation_cascade(self):
        """Full pipeline with federation cascade testing."""
        from mas_eval.domains.d5_robustness import run_federation_cascade

        result = run_federation_cascade()
        assert result["score"] >= 0
        assert result["score"] <= 100
        assert "dimensions" in result
        assert "containment" in result["dimensions"]

    # ═══════════════════════════════════════════════════════════
    # Phase 4: Cost Efficiency + Meta Evaluation
    # ═══════════════════════════════════════════════════════════

    def test_gold_pipeline_cost_efficiency(self):
        """Full pipeline with cost efficiency."""
        from mas_eval.cross_cutting.cost_efficiency import compute_cost_efficiency

        traj = {
            "events": [
                {
                    "action": {"type": "tool_call", "tool_id": "grep"},
                    "cost_usd": 0.02,
                    "token_usage": {"total": 200},
                }
            ]
        }
        result = compute_cost_efficiency(traj)
        assert result["cpt"] == 0.02
        assert result["total_tokens"] == 200
        assert result["efficiency"] > 0

    def test_gold_pipeline_meta_evaluation(self):
        """Full pipeline with meta evaluation."""
        from mas_eval.scoring.meta_evaluator import MetaEvaluator

        me = MetaEvaluator()
        for _ in range(3):
            me.record_run({"model": "x"}, {"overall": 85.0})
        result = me.overall_meta_score(
            weak_result={"overall": 30}, strong_result={"overall": 90}
        )
        assert result["meta_score"] >= 0.7
        assert result["confidence"] == "high"
