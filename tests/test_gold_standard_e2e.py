# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""End-to-end Gold Standard pipeline test (MAS-TS-001 v1.0.0 GA).

Drives a real Agent Card through the full D1-D5 evaluation stack and the Gold
Standard aggregation, asserting the pipeline produces a coherent gold_verdict
and report structure. A deterministic synthetic high-score path additionally
asserts the GOLD tier is reachable end-to-end.
"""

from mas_eval.domains.d1_compliance import run_d1
from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.domains.d4_governance_security import run_d4
from mas_eval.domains.d5_robustness import run_d5
from mas_eval.harness.aggregation import compute_gold_report
from mas_eval.scoring.adc import check_adc_alignment

# A v2.0-style card with the fields the D1-D5 domains reward.
GOLD_CARD = {
    "agent_id": "urn:agent:gold:e2e-01",
    "name": "GA Gold Agent",
    "schema_version": "2.0",
    "card_version": "2.0",
    "dependencies": ["numpy", "requests"],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
    "constitution": {
        "envelope": {
            "version": "1.5",
            "jurisdiction": "global",
            "constitution_ref": "Athena Digital Constitution v1.5",
        },
        "data_sanitizer": True,
        "prompt_guard": True,
        "health_state": "healthy",
        "heartbeat_interval_seconds": 30,
    },
    "governance": {
        "human_in_the_loop": {"required_for": ["delete", "write"]},
        "circuit_breaker": {"enabled": True, "threshold": 3},
        "compensating_transactions": True,
    },
    "endpoints": {"mcp": {"enabled": True, "version": "2024-10-01"}},
    "federation_protocols": {"mcp": {"enabled": True, "version": "2024-10-01"}},
    "federation": {"role": "primary", "trust_score": 0.85, "audit": {"trace_enabled": True}},
}


def _run_pipeline(card):
    return {
        "d1": run_d1(card),
        "d2": run_d2(card, []),
        "d3": run_d3(card),
        "d4": run_d4(card),
        "d5": run_d5(),
    }


class TestGoldStandardE2E:
    def test_full_pipeline_produces_valid_gold_report(self):
        domain_results = _run_pipeline(GOLD_CARD)
        report = compute_gold_report(domain_results, consistency_index=0.85)
        assert report["gold_verdict"] in ("GOLD", "SILVER", "BRONZE", "FAIL")
        assert 0.0 <= report["overall"] <= 100.0
        assert set(report["domain_scores"]) == {"d1", "d2", "d3", "d4", "d5"}
        assert "findings" in report

    def test_gold_tier_reachable_end_to_end(self):
        """Synthetic perfect agent must reach GOLD through the gold aggregator."""
        high = {
            "d1": {"score": 96.0, "findings": []},
            "d2": {"score": 92.0, "findings": []},
            "d3": {"score": 90.0, "findings": []},
            "d4": {"score": 94.0, "findings": []},
            "d5": {"score": 91.0, "findings": []},
        }
        report = compute_gold_report(high, consistency_index=0.85)
        assert report["gold_verdict"] == "GOLD"
        assert report["overall"] >= 78

    def test_critical_finding_blocks_gold(self):
        """A CRITICAL finding (e.g. missing HITL) forces a non-GOLD verdict."""
        high = {
            "d1": {"score": 96.0, "findings": []},
            "d2": {"score": 92.0, "findings": []},
            "d3": {"score": 90.0, "findings": []},
            "d4": {
                "score": 0.0,
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "category": "action_safety_no_hitl",
                        "detail": "No HITL for irreversible ops",
                        "layer": "safety",
                    }
                ],
            },
            "d5": {"score": 91.0, "findings": []},
        }
        report = compute_gold_report(high, consistency_index=0.85)
        assert report["gold_verdict"] != "GOLD"

    def test_low_consistency_index_blocks_gold(self):
        """CI below the GOLD threshold prevents GOLD even with high scores."""
        high = {
            "d1": {"score": 96.0, "findings": []},
            "d2": {"score": 92.0, "findings": []},
            "d3": {"score": 90.0, "findings": []},
            "d4": {"score": 94.0, "findings": []},
            "d5": {"score": 91.0, "findings": []},
        }
        report = compute_gold_report(high, consistency_index=0.5)
        assert report["gold_verdict"] != "GOLD"

    def test_adc_alignment_in_gold_pipeline(self):
        result = check_adc_alignment(GOLD_CARD)
        assert result["component"] == "adc_alignment"
        assert result["score"] >= 0.0
