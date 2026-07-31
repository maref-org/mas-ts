# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""End-to-end integration tests for MAS-TS-001 v3.0 Oracle Framework.

Validates the full pipeline: Oracle → run_d2_with_oracle → MultiModelRunner
→ Harness (L1/L2) → Absolute Scoring.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.harness.l1_standard import run_l1_with_oracle
from mas_eval.harness.l2_deep import run_l2_with_oracle
from mas_eval.oracle.oracle_base import (
    OracleRegistry,
    run_d2_with_oracle,
)
from mas_eval.oracle.tau_bench import TauBenchOracle
from mas_eval.scoring.multi_model import MultiModelRunner

SAMPLE_CARD = {
    "agent_id": "test-agent-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "card_version": "1.2",
    "model_backend": {
        "provider": "test",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_read",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_edit",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_write",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "glob",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "grep",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_search",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_fetch",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-07-15",
        },
    ],
}

MOCK_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_search",
                "input": {"query": "test"},
            }
        },
        {
            "action": {
                "type": "task_complete",
                "result": "success",
                "tool_id": "",
                "input": {},
            }
        },
    ]
}


class TestPipelineIntegration:
    """Full pipeline: Oracle → D2 → Harness → Scoring."""

    def setup_method(self):
        OracleRegistry.clear()
        self.tau = TauBenchOracle()
        OracleRegistry.register(self.tau)

    def teardown_method(self):
        OracleRegistry.clear()

    def test_oracle_to_d2(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "tau-bench", mock_trajectory=MOCK_TRAJECTORY
        )
        assert result["domain"] == "D2"
        assert "oracle_score" in result["subscores"]
        assert result["summary"]["oracle_name"] == "tau-bench"
        assert 0 <= result["score"] <= 100

    def test_oracle_to_l1_harness(self):
        result = run_l1_with_oracle(
            SAMPLE_CARD, "tau-bench", mock_trajectory=MOCK_TRAJECTORY
        )
        assert result["level"] == "L1"
        assert "Oracle" in result["name"]
        assert result["verdict"] in ("APPROVED", "CONDITIONAL", "BLOCKED")
        assert 0 <= result["score"] <= 100
        assert "oracle" in str(
            result["domains"]["d2_detail"]["findings"][-1]["category"]
        )

    def test_oracle_to_l2_harness(self):
        result = run_l2_with_oracle(
            SAMPLE_CARD, "tau-bench", mock_trajectory=MOCK_TRAJECTORY
        )
        assert result["level"] == "L2"
        assert "Oracle" in result["name"]
        assert 0 <= result["score"] <= 100

    def test_l1_findings_include_oracle_info(self):
        result = run_l1_with_oracle(
            SAMPLE_CARD, "tau-bench", mock_trajectory=MOCK_TRAJECTORY
        )
        oracle_findings = [
            f for f in result["findings"] if f.get("category") == "oracle"
        ]
        assert len(oracle_findings) >= 1

    def test_l2_domain_scores_include_all_four(self):
        result = run_l2_with_oracle(
            SAMPLE_CARD, "tau-bench", mock_trajectory=MOCK_TRAJECTORY
        )
        for domain in ("d1", "d2", "d3", "d4"):
            assert domain in result["domain_scores"]


class TestMultiModelOracle:
    """MultiModelRunner.oracle_run() integration."""

    def setup_method(self):
        OracleRegistry.clear()
        self.tau = TauBenchOracle()
        OracleRegistry.register(self.tau)

    def teardown_method(self):
        OracleRegistry.clear()

    def test_oracle_run_basic(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_model("claude-sonnet-4", {"provider": "test", "tier": "premium"})
        mm.add_model("gpt-4o", {"provider": "test", "tier": "premium"})

        result = mm.oracle_run("tau-bench")
        assert result["mode"] == "multi-model-oracle"
        assert result["oracle_name"] == "tau-bench"
        assert result["model_count"] == 2

    def test_oracle_run_scores(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_model("claude-sonnet-4", {"provider": "test"})

        result = mm.oracle_run("tau-bench")
        d2 = result["results"][0]["d2"]
        assert "oracle_score" in d2
        assert 0 <= d2["score"] <= 100

    def test_oracle_run_specific_task(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_model("claude-sonnet-4", {"provider": "test"})

        result = mm.oracle_run("tau-bench", task_id="tau-bench-airline-001")
        assert result["results"][0]["d2"]["score"] >= 0

    def test_print_matrix_oracle(self, capsys):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_model("claude-sonnet-4", {"provider": "test"})

        result = mm.oracle_run("tau-bench", mock_trajectory=MOCK_TRAJECTORY)
        mm.print_matrix(result)
        captured = capsys.readouterr()
        assert "Oracle Comparison" in captured.out
        assert "tau-bench" in captured.out


class TestMultiOracleRegistration:
    """Multiple oracles can coexist."""

    def setup_method(self):
        OracleRegistry.clear()

    def teardown_method(self):
        OracleRegistry.clear()

    def test_multiple_oracles_registered(self):
        from mas_eval.oracle.swe_bench import SWEBenchOracle
        from mas_eval.oracle.tau_bench import TauBenchOracle
        from mas_eval.oracle.web_arena import WebArenaOracle

        OracleRegistry.register(TauBenchOracle())
        OracleRegistry.register(SWEBenchOracle())
        OracleRegistry.register(WebArenaOracle())

        assert len(OracleRegistry.list()) == 3
        assert OracleRegistry.get("tau-bench") is not None
        assert OracleRegistry.get("swe-bench") is not None
        assert OracleRegistry.get("web-arena") is not None

    def test_each_oracle_has_unique_tasks(self):
        from mas_eval.oracle.swe_bench import SWEBenchOracle
        from mas_eval.oracle.tau_bench import TauBenchOracle
        from mas_eval.oracle.web_arena import WebArenaOracle

        tau_ids = {t.task_id for t in TauBenchOracle().list_tasks()}
        swe_ids = {t.task_id for t in SWEBenchOracle().list_tasks()}
        web_ids = {t.task_id for t in WebArenaOracle().list_tasks()}

        all_ids = tau_ids | swe_ids | web_ids
        total = len(tau_ids) + len(swe_ids) + len(web_ids)
        assert len(all_ids) == total, "Task IDs must be globally unique across oracles"
