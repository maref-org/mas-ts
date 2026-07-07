"""Tests for D4 Federation Evaluation (MAS-TS-001 v4.0)

Covers: TrustScorer, check_trust_score, check_vendor_diversity,
check_mcp_supply_chain, run_d4_federation, run_d4 federation integration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from mas_eval.domains.d4_governance_security import (
    D4_WEIGHTS,
    FEDERATION_WEIGHTS,
    GossipTrustProtocol,
    TrustScorer,
    _score_gossip_trust,
    check_mcp_supply_chain,
    check_trust_score,
    check_vendor_diversity,
    run_d4,
    run_d4_federation,
)

FED_CARD = {
    "agent_id": "urn:agent:test:fed:fed-01",
    "name": "Federation Agent",
    "version": "2.0.0",
    "vendor_id": "vendor-a",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": True,
        "model_backend_location": "US",
        "audit_trail_required": True,
    },
    "constitution": {
        "envelope": {
            "message_id": "m1",
            "correlation_id": "c1",
            "timestamp": "2026-06-11T00:00:00Z",
            "sender": "urn:agent:test:fed:fed-01",
        },
        "health_state": "HEALTHY",
        "heartbeat_interval_seconds": 15,
    },
    "model_backend": {
        "provider": "test",
        "model": "test",
        "deployment": "cloud",
        "endpoint": "https://test.com/v1",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        },
        {
            "skill_id": "agent_tool",
            "description": "spawn",
            "input_schema": {},
            "output_schema": {},
            "examples": ["spawn"],
        },
    ],
    "authentication": {
        "type": "OAuth2",
        "scopes": ["agent:spawn", "agent:communicate"],
    },
    "endpoints": {"a2a": "https://a2a.test", "mcp": "https://mcp.test"},
    "orchestration_hints": {
        "preferred_role": "worker",
        "parallel_safe": True,
        "stateful": False,
    },
    "federation": {
        "role": "primary",
        "trust_score": 0.85,
        "trust_history": [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.80, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.82, "source": "peer"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.85, "source": "oracle"},
        ],
        "federation_protocols": {
            "mcp": {"version": "2025-03-26", "enabled": True},
            "a2a": {"version": "1.0", "enabled": True},
        },
        "allowed_mcp_servers": [
            "https://mcp1.vendor-a.com",
            "wss://mcp2.vendor-a.com",
            "https://mcp3.vendor-a.com",
        ],
    },
}

NO_FED_CARD = {
    "agent_id": "urn:agent:test:nofed:nofed-01",
    "name": "No Federation Agent",
    "version": "1.2.0",
    "vendor_id": "vendor-b",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "constitution": {"health_state": "HEALTHY", "heartbeat_interval_seconds": 60},
    "model_backend": {
        "provider": "test",
        "model": "test",
        "deployment": "cloud",
        "endpoint": "https://test.com/v1",
    },
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
        }
    ],
    "authentication": {"type": "None"},
    "endpoints": {},
    "orchestration_hints": {},
}

VENDOR_A_CARD = {
    "agent_id": "urn:agent:test:va:va-01",
    "vendor_id": "vendor-a",
    "federation": {"role": "primary", "trust_score": 0.9},
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
}

VENDOR_B_CARD = {
    "agent_id": "urn:agent:test:vb:vb-01",
    "vendor_id": "vendor-b",
    "federation": {"role": "secondary", "trust_score": 0.8},
    "compliance": {
        "data_residency": "EU",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "EU",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
}

VENDOR_C_CARD = {
    "agent_id": "urn:agent:test:vc:vc-01",
    "vendor_id": "vendor-c",
    "federation": {"role": "observer", "trust_score": 0.7},
    "compliance": {
        "data_residency": "CN",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "CN",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
}

INSECURE_MCP_CARD = {
    "agent_id": "urn:agent:test:insecure:in-01",
    "vendor_id": "vendor-d",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
    "federation": {
        "allowed_mcp_servers": [
            "http://insecure-server.com",
            "https://secure-server.com",
        ],
    },
}

NO_MCP_CARD = {
    "agent_id": "urn:agent:test:nomcp:nm-01",
    "vendor_id": "vendor-e",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
    "federation": {},
}

TLS_MCP_CARD = {
    "agent_id": "urn:agent:test:tls:tls-01",
    "vendor_id": "vendor-f",
    "compliance": {
        "data_residency": "US",
        "data_classification": "public",
        "cross_border": False,
        "model_backend_location": "US",
        "audit_trail_required": False,
    },
    "authentication": {"type": "None"},
    "orchestration_hints": {},
    "federation": {
        "allowed_mcp_servers": [
            "https://mcp1.example.com:443",
            "wss://mcp2.example.com:443",
            "https://mcp3.example.com:9090?tls=true",
        ],
    },
}


class TestTrustScorer:
    def test_default_score(self):
        ts = TrustScorer()
        score = ts.score()
        assert 0 <= score <= 1

    def test_with_base_score(self):
        ts = TrustScorer(trust_score=0.9)
        score = ts.score()
        assert score > 0.5

    def test_with_object_base_score(self):
        ts = TrustScorer(
            trust_score={"value": 0.9, "evaluated_by": "urn:agent:mas-ts:evaluator"}
        )
        score = ts.score()
        assert score > 0.5

    def test_with_history(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.5, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.7, "source": "peer"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.9, "source": "oracle"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.5)
        score = ts.score()
        assert score > 0.5

    def test_integrity_with_history(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.8, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.8, "source": "self"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.8, "source": "self"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert round(ts._score_integrity(), 6) == 0.8

    def test_integrity_no_history(self):
        ts = TrustScorer(trust_score=0.7)
        assert ts._score_integrity() == 0.7

    def test_consistency_low_variance(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.8, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.81, "source": "self"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.79, "source": "self"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert ts._score_consistency() > 0.9

    def test_consistency_high_variance(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.1, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.9, "source": "self"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert ts._score_consistency() <= 0.21

    def test_consistency_no_history(self):
        ts = TrustScorer(trust_score=0.5)
        assert ts._score_consistency() == 0.5

    def test_compliance_with_oracle(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.8, "source": "oracle"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.8, "source": "peer"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert ts._score_compliance() >= 0.5

    def test_compliance_no_history(self):
        ts = TrustScorer(trust_score=0.5)
        assert ts._score_compliance() == 0.5

    def test_responsiveness_frequent(self):
        history = [
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.8, "source": "self"},
            {"timestamp": "2026-06-10T00:01:00Z", "score": 0.8, "source": "self"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert ts._score_responsiveness() > 0.5

    def test_responsiveness_infrequent(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.8, "source": "self"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.8, "source": "self"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.0)
        assert ts._score_responsiveness() < 0.5

    def test_responsiveness_no_history(self):
        ts = TrustScorer(trust_score=0.5)
        assert ts._score_responsiveness() == 0.5

    def test_reputation_returns_base(self):
        ts = TrustScorer(trust_score=0.75)
        assert ts._score_reputation() == 0.75

    def test_dimension_weights_sum_to_one(self):
        total = sum(TrustScorer.DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_score_in_range(self):
        history = [
            {"timestamp": "2026-06-01T00:00:00Z", "score": 0.2, "source": "self"},
            {"timestamp": "2026-06-05T00:00:00Z", "score": 0.5, "source": "peer"},
            {"timestamp": "2026-06-10T00:00:00Z", "score": 0.8, "source": "oracle"},
        ]
        ts = TrustScorer(trust_history=history, trust_score=0.3)
        score = ts.score()
        assert 0 <= score <= 1

    def test_trust_transfer_direct(self):
        result = TrustScorer.trust_transfer(0.9, depth=1)
        assert abs(result - 0.9) < 0.01

    def test_trust_transfer_two_hop(self):
        result = TrustScorer.trust_transfer(0.9, depth=2)
        assert abs(result - 0.63) < 0.01

    def test_trust_transfer_three_hop(self):
        result = TrustScorer.trust_transfer(0.9, depth=3)
        assert abs(result - 0.36) < 0.01

    def test_trust_transfer_deep(self):
        result = TrustScorer.trust_transfer(0.9, depth=5)
        assert abs(result - 0.09) < 0.01

    def test_trust_transfer_with_context(self):
        result = TrustScorer.trust_transfer(0.9, depth=1, context_relevance=0.5)
        assert abs(result - 0.45) < 0.01


class TestCheckTrustScore:
    def test_no_federation(self):
        score, findings = check_trust_score(NO_FED_CARD)
        assert score == 0.0
        assert any("skipped" in f["detail"] for f in findings)

    def test_with_federation(self):
        score, findings = check_trust_score(FED_CARD)
        assert score > 50
        assert any("Trust score" in f["detail"] for f in findings)

    def test_with_object_trust_score(self):
        card = dict(FED_CARD)
        card["federation"] = dict(FED_CARD["federation"])
        card["federation"]["trust_score"] = {
            "value": 0.85,
            "evaluated_by": "urn:agent:mas-ts:evaluator",
        }
        score, findings = check_trust_score(card)
        assert score > 50
        assert any("Reputation baseline" in f["detail"] for f in findings)

    def test_object_trust_score_reports_evaluator(self):
        card = dict(FED_CARD)
        card["federation"] = dict(FED_CARD["federation"])
        card["federation"]["trust_score"] = {
            "value": 0.85,
            "evaluated_by": "urn:agent:mas-ts:evaluator",
        }
        score, findings = check_trust_score(card)
        assert any("evaluated by" in f["detail"] for f in findings)

    def test_object_trust_score_missing_evaluator_warns(self):
        card = dict(FED_CARD)
        card["federation"] = dict(FED_CARD["federation"])
        card["federation"]["trust_score"] = {"value": 0.85}
        score, findings = check_trust_score(card)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_trend_improving(self):
        card = {
            "agent_id": "urn:agent:test:trend:tr-01",
            "vendor_id": "vendor-t",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
            },
            "authentication": {"type": "None"},
            "orchestration_hints": {},
            "federation": {
                "trust_score": 0.5,
                "trust_history": [
                    {
                        "timestamp": "2026-06-01T00:00:00Z",
                        "score": 0.5,
                        "source": "self",
                    },
                    {
                        "timestamp": "2026-06-05T00:00:00Z",
                        "score": 0.7,
                        "source": "self",
                    },
                    {
                        "timestamp": "2026-06-10T00:00:00Z",
                        "score": 0.9,
                        "source": "self",
                    },
                ],
            },
        }
        score, findings = check_trust_score(card)
        assert any("improving" in f["detail"] for f in findings)

    def test_trend_declining(self):
        card = {
            "agent_id": "urn:agent:test:trend:tr-02",
            "vendor_id": "vendor-t",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
            },
            "authentication": {"type": "None"},
            "orchestration_hints": {},
            "federation": {
                "trust_score": 0.9,
                "trust_history": [
                    {
                        "timestamp": "2026-06-01T00:00:00Z",
                        "score": 0.9,
                        "source": "self",
                    },
                    {
                        "timestamp": "2026-06-05T00:00:00Z",
                        "score": 0.7,
                        "source": "self",
                    },
                    {
                        "timestamp": "2026-06-10T00:00:00Z",
                        "score": 0.5,
                        "source": "self",
                    },
                ],
            },
        }
        score, findings = check_trust_score(card)
        assert any("declining" in f["detail"] for f in findings)

    def test_reputation_baseline_reported(self):
        score, findings = check_trust_score(FED_CARD)
        assert any("Reputation" in f["detail"] for f in findings)

    def test_score_range(self):
        score, findings = check_trust_score(FED_CARD)
        assert 0 <= score <= 100


class TestCheckVendorDiversity:
    def test_no_cards(self):
        score, findings = check_vendor_diversity([])
        assert score == 100.0

    def test_no_vendor_id(self):
        score, findings = check_vendor_diversity([NO_FED_CARD])
        assert score == 0.0

    def test_single_vendor(self):
        score, findings = check_vendor_diversity([VENDOR_A_CARD])
        assert any("Single vendor" in f["detail"] for f in findings)

    def test_two_vendors(self):
        score, findings = check_vendor_diversity([VENDOR_A_CARD, VENDOR_B_CARD])
        assert score > 0
        assert score < 100

    def test_three_vendors(self):
        score, findings = check_vendor_diversity(
            [VENDOR_A_CARD, VENDOR_B_CARD, VENDOR_C_CARD]
        )
        assert any("Multi-vendor" in f["detail"] for f in findings)

    def test_dedup_same_vendor(self):
        cards = [VENDOR_A_CARD, VENDOR_A_CARD]
        score, findings = check_vendor_diversity(cards)
        assert any("Single vendor" in f["detail"] for f in findings)

    def test_score_decreases_with_concentration(self):
        single_score, _ = check_vendor_diversity([VENDOR_A_CARD])
        three_score, _ = check_vendor_diversity(
            [VENDOR_A_CARD, VENDOR_B_CARD, VENDOR_C_CARD]
        )
        assert three_score > single_score


class TestCheckMCPChain:
    def test_no_federation(self):
        score, findings = check_mcp_supply_chain(NO_FED_CARD)
        assert score == 0.0
        assert any("skipped" in f["detail"] for f in findings)

    def test_no_allowed_servers(self):
        score, findings = check_mcp_supply_chain(NO_MCP_CARD)
        assert score == 0.0
        assert any("CRITICAL" in f["severity"] for f in findings)

    def test_all_secure_servers(self):
        score, findings = check_mcp_supply_chain(FED_CARD)
        assert score > 50
        assert any("secure protocols" in f["detail"] for f in findings)

    def test_insecure_servers_detected(self):
        score, findings = check_mcp_supply_chain(INSECURE_MCP_CARD)
        assert any("Insecure" in f["detail"] for f in findings)
        assert score < 100

    def test_tls_certificates_detected(self):
        score, findings = check_mcp_supply_chain(TLS_MCP_CARD)
        assert any("TLS" in f["detail"] for f in findings)
        assert score > 50

    def test_limited_surface_bonus(self):
        score, findings = check_mcp_supply_chain(FED_CARD)
        count = len(FED_CARD["federation"]["allowed_mcp_servers"])
        assert count <= 3
        assert any("Limited" in f["detail"] for f in findings)

    def test_large_whitelist_warning(self):
        card = {
            "agent_id": "urn:agent:test:large:lg-01",
            "vendor_id": "vendor-l",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
            },
            "authentication": {"type": "None"},
            "orchestration_hints": {},
            "federation": {
                "allowed_mcp_servers": [
                    f"https://mcp{i}.example.com" for i in range(15)
                ],
            },
        }
        score, findings = check_mcp_supply_chain(card)
        assert any("Large" in f["detail"] for f in findings)

    def test_score_capped_at_100(self):
        card = {
            "agent_id": "urn:agent:test:perfect:pf-01",
            "vendor_id": "vendor-p",
            "compliance": {
                "data_residency": "US",
                "data_classification": "public",
                "cross_border": False,
                "model_backend_location": "US",
                "audit_trail_required": False,
            },
            "authentication": {"type": "None"},
            "orchestration_hints": {},
            "federation": {
                "allowed_mcp_servers": [
                    "https://mcp1.example.com?crt=chain.pem",
                ],
            },
        }
        score, findings = check_mcp_supply_chain(card)
        assert score <= 100


class TestRunD4Federation:
    def test_single_card(self):
        result = run_d4_federation([FED_CARD])
        assert "subscores" in result
        assert "trust" in result["subscores"]
        assert "vendor_diversity" in result["subscores"]
        assert "mcp_supply_chain" in result["subscores"]
        assert result["score"] >= 0

    def test_multiple_cards(self):
        result = run_d4_federation([FED_CARD, NO_FED_CARD])
        assert result["score"] >= 0
        assert result["summary"]["agents_scored"] == 2

    def test_empty_cards(self):
        result = run_d4_federation([])
        assert result["score"] == 0.0

    def test_weighted_score(self):
        result = run_d4_federation([FED_CARD])
        expected_weighted = (
            result["subscores"]["trust"] * FEDERATION_WEIGHTS["trust"]
            + result["subscores"]["vendor_diversity"]
            * FEDERATION_WEIGHTS["vendor_diversity"]
            + result["subscores"]["mcp_supply_chain"]
            * FEDERATION_WEIGHTS["mcp_supply_chain"]
            + result["subscores"]["gossip_trust"] * FEDERATION_WEIGHTS["gossip_trust"]
        )
        assert abs(result["score"] - expected_weighted) < 1.0

    def test_federation_weights_include_all_subscores(self):
        result = run_d4_federation([FED_CARD])
        assert set(result["subscores"]) == set(FEDERATION_WEIGHTS)

    def test_findings_present(self):
        result = run_d4_federation([FED_CARD])
        assert result["summary"]["total_findings"] > 0


class TestRunD4FederationIntegration:
    def test_backward_compatible(self):
        result = run_d4(NO_FED_CARD)
        assert "score" in result
        assert "federation" in result

    def test_with_federation_data(self):
        result = run_d4(FED_CARD)
        assert result["subscores"]["trust"] > 0
        assert result["summary"]["trust_score"] > 0

    def test_federation_subscore_keys(self):
        result = run_d4(FED_CARD)
        assert "trust" in result["subscores"]
        assert "vendor_diversity" in result["subscores"]
        assert "mcp_supply_chain" in result["subscores"]
        assert "gossip_trust" in result["subscores"]

    def test_federation_section_present(self):
        result = run_d4(FED_CARD)
        assert "trust_score" in result["federation"]
        assert "vendor_diversity" in result["federation"]
        assert "mcp_supply_chain" in result["federation"]
        assert "gossip_trust" in result["federation"]
        assert "findings" in result["federation"]

    def test_d4_weights_sum_to_one(self):
        # Use tolerance for floating-point summation (0.35+0.11+0.07+0.07+0.05+fed = 1.0±ε)
        assert abs(sum(D4_WEIGHTS.values()) - 1.0) < 1e-9

    def test_new_weights_applied(self):
        result = run_d4(FED_CARD)
        gov = result["governance"]["score"]
        sec = result["security"]["score"]
        action = result["subscores"].get("action_safety", 0)
        trust = result["subscores"]["trust"]
        vendor = result["subscores"]["vendor_diversity"]
        mcp = result["subscores"]["mcp_supply_chain"]
        gossip = result["subscores"]["gossip_trust"]
        dl = result["subscores"].get("data_leakage", 0)
        hitl = result["subscores"].get("hitl_gate", 0)
        expected = (
            gov * D4_WEIGHTS["governance"]
            + sec * D4_WEIGHTS["security"]
            + action * D4_WEIGHTS.get("action_safety", 0.08)
            + trust * D4_WEIGHTS["trust"]
            + vendor * D4_WEIGHTS["vendor_diversity"]
            + mcp * D4_WEIGHTS["mcp_supply_chain"]
            + gossip * D4_WEIGHTS["gossip_trust"]
            + dl * D4_WEIGHTS.get("data_leakage", 0.07)
            + hitl * D4_WEIGHTS.get("hitl_gate", 0.05)
        )
        assert abs(result["score"] - expected) < 0.1

    def test_with_federation_cards_param(self):
        result = run_d4(FED_CARD, federation_cards=[VENDOR_A_CARD, VENDOR_B_CARD])
        assert result["score"] >= 0


class TestGossipTrustProtocol:
    def test_init_defaults(self):
        gtp = GossipTrustProtocol()
        assert gtp.n == 5
        assert len(gtp.trust) == 5
        assert len(gtp.trust[0]) == 5

    def test_init_custom_agents(self):
        gtp = GossipTrustProtocol(agents=["a", "b"])
        assert gtp.n == 2
        assert gtp.agents == ["a", "b"]

    def test_self_trust_accurate(self):
        gtp = GossipTrustProtocol()
        for i in range(gtp.n):
            name = gtp.agents[i]
            assert gtp.trust[i][i] == gtp.ground_truth[name]

    def test_add_malicious(self):
        gtp = GossipTrustProtocol()
        assert len(gtp.malicious) == 0
        gtp.add_malicious(0)
        assert 0 in gtp.malicious

    def test_round_reduces_variance(self):
        gtp = GossipTrustProtocol(seed=42)
        initial_var = gtp.trust_variance()
        for _ in range(10):
            gtp.round()
        later_var = gtp.trust_variance()
        assert later_var < initial_var

    def test_convergence_reduces_variance(self):
        gtp = GossipTrustProtocol(seed=42)
        rounds = gtp.run_until_convergence(max_rounds=100)
        assert rounds <= 100
        assert gtp.trust_variance() < 0.001

    def test_accuracy_after_convergence(self):
        gtp = GossipTrustProtocol(seed=42)
        gtp.run_until_convergence()
        accuracy = gtp.consensus_accuracy()
        assert 0.0 <= accuracy <= 1.0
        assert accuracy > 0.8

    def test_malicious_detection_no_malicious(self):
        gtp = GossipTrustProtocol(seed=42)
        score = gtp.malicious_detection_score()
        assert score == 1.0

    def test_malicious_detection_with_malicious(self):
        gtp = GossipTrustProtocol(seed=42)
        gtp.add_malicious(4)
        gtp.run_until_convergence()
        score = gtp.malicious_detection_score()
        assert 0.0 <= score <= 1.0

    def test_reset_clears_state(self):
        gtp = GossipTrustProtocol(seed=42)
        gtp.run_until_convergence()
        gtp.reset()
        assert gtp.rounds_run == 0
        assert gtp.converged_at is None
        assert len(gtp.malicious) == 0

    def test_reproducible_seed(self):
        gtp1 = GossipTrustProtocol(seed=42)
        gtp2 = GossipTrustProtocol(seed=42)
        gtp1.run_until_convergence()
        gtp2.run_until_convergence()
        assert gtp1.rounds_run == gtp2.rounds_run
        assert gtp1.consensus_accuracy() == gtp2.consensus_accuracy()


class TestScoreGossipTrust:
    def test_score_range(self):
        score, findings = _score_gossip_trust()
        assert 0 <= score <= 100

    def test_has_findings(self):
        score, findings = _score_gossip_trust()
        assert len(findings) > 0

    def test_findings_have_correct_structure(self):
        score, findings = _score_gossip_trust()
        for f in findings:
            assert "severity" in f
            assert "category" in f
            assert "detail" in f

    def test_clean_gossip_finding(self):
        score, findings = _score_gossip_trust()
        clean = [f for f in findings if f["category"] == "gossip_clean"]
        assert len(clean) == 1

    def test_malicious_gossip_finding(self):
        score, findings = _score_gossip_trust()
        mal = [f for f in findings if f["category"] == "gossip_malicious"]
        assert len(mal) == 1

    def test_summary_finding(self):
        score, findings = _score_gossip_trust()
        summary = [f for f in findings if f["category"] == "gossip_summary"]
        assert len(summary) == 1

    def test_reproducible_score(self):
        s1, _ = _score_gossip_trust(seed=42)
        s2, _ = _score_gossip_trust(seed=42)
        assert s1 == s2
