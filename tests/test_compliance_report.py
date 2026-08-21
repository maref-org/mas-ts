"""Tests for Federation Compliance Report (MAS-TS-001 v5.0)"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.scoring.compliance_report import (
    DOMAIN_WEIGHTS,
    _build_agent_entry,
    _compute_federation_health,
    _extract_domain_scores,
    build_report,
    validate_compliance_report,
)

SAMPLE_CARD = {
    "agent_id": "urn:agent:test:test-01",
    "name": "Test Agent",
    "version": "1.0.0",
    "vendor_id": "vendor-a",
    "card_version": "1.2",
    "federation": {
        "role": "primary",
        "trust_score": 0.75,
        "audit": {"trace_enabled": True},
    },
}

SAMPLE_RESULT = {
    "D1": {"domain": "D1", "score": 95.0},
    "D2": {"domain": "D2", "score": 80.0},
    "D3": {
        "domain": "D3",
        "score": 75.0,
        "subscores": {
            "federation_matrix": 85.0,
            "federation_role": 5,
            "federation_compat": 10,
        },
    },
    "D4": {
        "domain": "D4",
        "score": 82.0,
        "subscores": {
            "trust": 65.0,
            "vendor_diversity": 80.0,
            "mcp_supply_chain": 70.0,
            "gossip_trust": 75.0,
        },
    },
    "D5": {"domain": "D5", "score": 88.0},
    "findings": [{"severity": "INFO", "category": "test", "detail": "ok"}],
}


class TestExtractDomainScores:
    def test_with_score(self):
        result = {"domain": "D1", "score": 95.0}
        out = _extract_domain_scores(result)
        assert out["domain_score"] == 95.0

    def test_with_subscores(self):
        result = {"domain": "D1", "score": 90.0, "subscores": {"a": 1}}
        out = _extract_domain_scores(result)
        assert out["subscores"]["a"] == 1

    def test_without_subscores(self):
        result = {"domain": "D1", "score": 90.0}
        out = _extract_domain_scores(result)
        assert out["subscores"] == {}


class TestComputeFederationHealth:
    def test_single_agent(self):
        data = [{"scores": {"D1": 90, "D2": 80, "D3": 70, "D4": 85, "D5": 75}}]
        health = _compute_federation_health(data)
        expected = 90 * 0.10 + 80 * 0.25 + 70 * 0.25 + 85 * 0.20 + 75 * 0.20
        assert health == round(expected, 1)

    def test_empty(self):
        assert _compute_federation_health([]) == 0.0

    def test_partial_scores(self):
        data = [{"scores": {"D1": 90, "D3": 70}}]
        health = _compute_federation_health(data)
        assert health > 0

    def test_multi_agent(self):
        data = [
            {"scores": {"D1": 90, "D2": 80, "D3": 70, "D4": 85, "D5": 75}},
            {"scores": {"D1": 85, "D2": 75, "D3": 65, "D4": 80, "D5": 70}},
        ]
        health = _compute_federation_health(data)
        d1_avg = (90 + 85) / 2
        d2_avg = (80 + 75) / 2
        d3_avg = (70 + 65) / 2
        d4_avg = (85 + 80) / 2
        d5_avg = (75 + 70) / 2
        expected = (
            d1_avg * 0.10
            + d2_avg * 0.25
            + d3_avg * 0.25
            + d4_avg * 0.20
            + d5_avg * 0.20
        )
        assert health == round(expected, 1)


class TestBuildReport:
    def test_single_agent(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert report["report_type"] == "federation_compliance_report"
        assert report["report_version"] == "1.0"
        assert len(report["agents"]) == 1

    def test_two_agents(self):
        cards = [SAMPLE_CARD, dict(SAMPLE_CARD, agent_id="agent-02", name="Agent 2")]
        results = {c["agent_id"]: SAMPLE_RESULT for c in cards}
        report = build_report(results, cards)
        assert len(report["agents"]) == 2

    def test_report_has_required_keys(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert "report_type" in report
        assert "report_version" in report
        assert "generated_at" in report
        assert "agents" in report
        assert "federation" in report
        assert "gaps" in report
        assert "recommendations" in report
        assert "summary" in report

    def test_agent_entry_has_scores(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        agent = report["agents"][0]
        for d in ("D1", "D2", "D3", "D4", "D5"):
            assert d in agent["scores"]

    def test_agent_entry_has_verdict(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert report["agents"][0]["verdict"] in ("PASS", "NOTES", "REVIEW", "BLOCKED")

    def test_federation_has_agent_count(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert report["federation"]["agent_count"] == 1

    def test_federation_has_domain_averages(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        for d in DOMAIN_WEIGHTS:
            assert d in report["federation"]["domain_averages"]

    def test_federation_has_overall_health(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert 0 <= report["federation"]["overall_health"] <= 100

    def test_summary_keys(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        s = report["summary"]
        assert "total_agents" in s
        assert "agents_passing" in s
        assert "agents_blocked" in s
        assert "total_gaps" in s
        assert "total_recommendations" in s
        assert "federation_health" in s

    def test_gaps_is_list(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert isinstance(report["gaps"], list)

    def test_recommendations_is_list(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert isinstance(report["recommendations"], list)

    def test_critical_finding_triggers_verdict(self):
        result = copy.deepcopy(SAMPLE_RESULT)
        result["findings"] = [
            {"severity": "CRITICAL", "category": "critical", "detail": "blocked"}
        ]
        report = build_report({"urn:agent:test:test-01": result}, [SAMPLE_CARD])
        assert report["agents"][0]["verdict"] == "BLOCKED"

    def test_health_score_reasonable(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        h = report["federation"]["overall_health"]
        assert 0 <= h <= 100

    def test_recommendation_for_missing_trace(self):
        card = copy.deepcopy(SAMPLE_CARD)
        card["federation"] = {"role": "primary", "trust_score": 0.5}
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [card])
        trace_recs = [r for r in report["recommendations"] if "trace" in r.lower()]
        assert len(trace_recs) >= 0

    def test_no_false_positive_role_conflict(self):
        card = copy.deepcopy(SAMPLE_CARD)
        result = copy.deepcopy(SAMPLE_RESULT)
        result["D3"]["subscores"]["federation_role"] = 5
        report = build_report({"urn:agent:test:test-01": result}, [card])
        role_recs = [
            r for r in report["recommendations"] if "role conflict" in r.lower()
        ]
        assert len(role_recs) == 0

    def test_agent_entry_includes_federation_details(self):
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        agent = report["agents"][0]
        fd = agent.get("federation_details", {})
        assert isinstance(fd, dict)

    def test_reproducible(self):
        r1 = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        r2 = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD])
        assert r1["summary"] == r2["summary"]


class TestRecommendations:
    def test_without_federation_blocked(self):
        card = copy.deepcopy(SAMPLE_CARD)
        card.pop("federation")
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [card])
        fed_recs = [
            r for r in report["recommendations"] if "federation block" in r.lower()
        ]
        assert len(fed_recs) >= 1

    def test_with_all_trace_enabled(self):
        card = copy.deepcopy(SAMPLE_CARD)
        card["federation"] = {"audit": {"trace_enabled": True}}
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [card])
        trace_recs = [r for r in report["recommendations"] if "trace" in r.lower()]
        assert len(trace_recs) == 0

    def test_with_top_level_audit_trace_flags(self):
        card = copy.deepcopy(SAMPLE_CARD)
        card["federation"] = {"role": "primary"}
        card["audit"] = {
            "trace_id_required": True,
            "timestamp_required": True,
            "source_agent_required": True,
            "target_agent_required": True,
        }
        report = build_report({"urn:agent:test:test-01": SAMPLE_RESULT}, [card])
        trace_recs = [r for r in report["recommendations"] if "trace" in r.lower()]
        assert len(trace_recs) == 0

    def test_no_role_conflict_false_positive(self):
        card = copy.deepcopy(SAMPLE_CARD)
        result = copy.deepcopy(SAMPLE_RESULT)
        result["D3"]["subscores"]["federation_role"] = 5
        report = build_report({"urn:agent:test:test-01": result}, [card])
        role_recs = [
            r for r in report["recommendations"] if "role conflict" in r.lower()
        ]
        assert len(role_recs) == 0

    def test_role_conflict_detected(self):
        card = copy.deepcopy(SAMPLE_CARD)
        result = copy.deepcopy(SAMPLE_RESULT)
        result["D3"]["subscores"]["federation_role"] = 0
        report = build_report({"urn:agent:test:test-01": result}, [card])
        role_recs = [
            r for r in report["recommendations"] if "role conflict" in r.lower()
        ]
        assert len(role_recs) >= 1


class TestEdgeCases:
    def test_empty_agent_results(self):
        report = build_report({}, [])
        assert report["summary"]["total_agents"] == 0
        assert report["federation"]["overall_health"] == 0.0
        assert report["federation"]["agent_count"] == 0

    def test_all_blocked(self):
        cards = [
            {"agent_id": "a1", "name": "A1", "vendor_id": "v1"},
            {"agent_id": "a2", "name": "A2", "vendor_id": "v2"},
        ]
        results = {
            c["agent_id"]: {
                "findings": [
                    {"severity": "CRITICAL", "category": "x", "detail": "fail"}
                ],
            }
            for c in cards
        }
        report = build_report(results, cards)
        assert report["summary"]["total_agents"] == 2
        assert report["summary"]["agents_passing"] == 0
        assert report["summary"]["agents_blocked"] == 2

    def test_score_clamping_low(self):
        result = {
            "D1": {"domain": "D1", "score": -50},
            "D2": {"domain": "D2", "score": 80},
            "D3": {"domain": "D3", "score": 70},
            "D4": {"domain": "D4", "score": 85},
            "D5": {"domain": "D5", "score": 75},
        }
        entry = _build_agent_entry("test", SAMPLE_CARD, result)
        assert entry["scores"]["D1"] == 0.0

    def test_score_clamping_high(self):
        result = {
            "D1": {"domain": "D1", "score": 150},
            "D2": {"domain": "D2", "score": 80},
            "D3": {"domain": "D3", "score": 70},
            "D4": {"domain": "D4", "score": 85},
            "D5": {"domain": "D5", "score": 75},
        }
        entry = _build_agent_entry("test", SAMPLE_CARD, result)
        assert entry["scores"]["D1"] == 100.0

    def test_missing_all_domain_results(self):
        report = build_report({"urn:agent:test:test-01": {}}, [SAMPLE_CARD])
        for d in ("D1", "D2", "D3", "D4", "D5"):
            assert report["agents"][0]["scores"][d] == 0.0

    def test_no_findings(self):
        result = copy.deepcopy(SAMPLE_RESULT)
        result.pop("findings", None)
        report = build_report({"urn:agent:test:test-01": result}, [SAMPLE_CARD])
        assert report["summary"]["total_gaps"] == 0

    def test_findings_at_top_level_appear_in_gaps(self):
        result = copy.deepcopy(SAMPLE_RESULT)
        result.setdefault("findings", []).append(
            {"severity": "HIGH", "category": "extra", "detail": "extra finding"}
        )
        report = build_report({"urn:agent:test:test-01": result}, [SAMPLE_CARD])
        high_gaps = [g for g in report["gaps"] if g["severity"] == "HIGH"]
        assert len(high_gaps) >= 1

    def test_findings_nested_in_domains_not_in_gaps(self):
        result = copy.deepcopy(SAMPLE_RESULT)
        result.setdefault("findings", [])
        result["D1"]["findings"] = [
            {"severity": "HIGH", "category": "extra", "detail": "inside D1 only"}
        ]
        report = build_report({"urn:agent:test:test-01": result}, [SAMPLE_CARD])
        high_gaps = [g for g in report["gaps"] if g["severity"] == "HIGH"]
        assert len(high_gaps) == 0


class TestComplianceReportSchemaV1:
    def test_build_report_validates_against_schema(self):
        report = build_report(
            {"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD]
        )
        outcome = validate_compliance_report(report)
        assert outcome["valid"] is True
        assert outcome["errors"] == []

    def test_empty_report_validates(self):
        report = build_report({}, [])
        outcome = validate_compliance_report(report)
        assert outcome["valid"] is True

    def test_missing_required_field_fails(self):
        report = build_report(
            {"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD]
        )
        del report["report_version"]
        outcome = validate_compliance_report(report)
        assert outcome["valid"] is False
        assert outcome["errors"]

    def test_wrong_report_version_fails(self):
        report = build_report(
            {"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD]
        )
        report["report_version"] = "2.0"
        outcome = validate_compliance_report(report)
        assert outcome["valid"] is False

    def test_invalid_verdict_fails(self):
        report = build_report(
            {"urn:agent:test:test-01": SAMPLE_RESULT}, [SAMPLE_CARD]
        )
        report["agents"][0]["verdict"] = "BOGUS"
        outcome = validate_compliance_report(report)
        assert outcome["valid"] is False
