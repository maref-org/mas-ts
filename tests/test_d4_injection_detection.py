# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for D4 Prompt Injection Detection (v0.8.1).

Covers OWASP Agentic Top 10 #4 detection engine: vector library integrity,
defense declaration detection, risk-based scoring, and D4 security integration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d4_governance_security import run_d4_security
from mas_eval.domains.d4_injection_detection import (
    CATEGORY_TO_DEFENSES,
    DEFENSE_FIELD_PROBES,
    DIRECT_INJECTION_VECTORS,
    HIGH_RISK_CAPS,
    INDIRECT_INJECTION_VECTORS,
    INJECTION_WEIGHTS,
    JAILBREAK_VECTORS,
    detect_declared_defenses,
    run_d4_injection_detection,
)


class TestVectorLibrary:
    def test_all_vector_libraries_non_empty(self):
        assert len(DIRECT_INJECTION_VECTORS) >= 5
        assert len(INDIRECT_INJECTION_VECTORS) >= 5
        assert len(JAILBREAK_VECTORS) >= 5

    def test_vectors_have_required_fields(self):
        for v in DIRECT_INJECTION_VECTORS + INDIRECT_INJECTION_VECTORS + JAILBREAK_VECTORS:
            assert "id" in v
            assert "pattern" in v
            assert "category" in v

    def test_vector_ids_unique(self):
        all_ids = [v["id"] for v in (
            DIRECT_INJECTION_VECTORS + INDIRECT_INJECTION_VECTORS + JAILBREAK_VECTORS
        )]
        assert len(all_ids) == len(set(all_ids))

    def test_all_categories_mapped_to_defenses(self):
        all_cats = {v["category"] for v in (
            DIRECT_INJECTION_VECTORS + INDIRECT_INJECTION_VECTORS + JAILBREAK_VECTORS
        )}
        for cat in all_cats:
            assert cat in CATEGORY_TO_DEFENSES, f"category {cat} has no defense mapping"
            assert len(CATEGORY_TO_DEFENSES[cat]) > 0

    def test_weights_sum_to_one(self):
        assert abs(sum(INJECTION_WEIGHTS.values()) - 1.0) < 1e-9


class TestDetectDeclaredDefenses:
    def test_no_defenses_in_bare_card(self):
        card = {"name": "bare", "capabilities": [{"skill_id": "bash"}]}
        assert detect_declared_defenses(card) == set()

    def test_detects_safety_input_filter(self):
        card = {"safety": {"input_filter": True}}
        assert "input_filter" in detect_declared_defenses(card)

    def test_detects_guardrails_prompt(self):
        card = {"guardrails": {"prompt": "enabled"}}
        assert "prompt_guard" in detect_declared_defenses(card)

    def test_detects_defense_via_capability_skill_id(self):
        card = {"capabilities": [{"skill_id": "injection_detection", "description": "x"}]}
        assert "injection_detector" in detect_declared_defenses(card)

    def test_detects_defense_via_capability_description(self):
        card = {"capabilities": [{"skill_id": "x", "description": "jailbreak detection layer"}]}
        assert "jailbreak_detector" in detect_declared_defenses(card)

    def test_falsy_values_not_detected(self):
        card = {"safety": {"input_filter": False, "output_filter": "disabled"}}
        declared = detect_declared_defenses(card)
        assert "input_filter" not in declared
        assert "output_filter" not in declared

    def test_all_probes_have_fields(self):
        for defense, probes in DEFENSE_FIELD_PROBES.items():
            assert len(probes) > 0, f"{defense} has no probes"


class TestScoring:
    def test_empty_card_returns_zero_with_critical(self):
        result = run_d4_injection_detection({})
        assert result["score"] == 0.0
        assert result["findings"][0]["severity"] == "CRITICAL"
        assert result["domain"] == "D4"

    def test_bare_card_moderate_score_with_warning(self):
        card = {"name": "bare", "capabilities": [{"skill_id": "todo_write"}]}
        result = run_d4_injection_detection(card)
        # No high-risk caps, no defenses → base 60 - 15 (medium/2) per undefended dim
        assert 30 <= result["score"] <= 70
        severities = {f["severity"] for f in result["findings"]}
        assert "WARNING" in severities

    def test_bash_without_defense_triggers_critical(self):
        card = {
            "name": "shell-agent",
            "capabilities": [{"skill_id": "bash"}],
            "dependencies": ["bash"],
        }
        result = run_d4_injection_detection(card)
        assert result["score"] < 50
        cats = {f["category"] for f in result["findings"]}
        assert any("undefended" in c for c in cats)
        assert result["summary"]["critical_count"] >= 1

    def test_declared_input_filter_raises_score(self):
        card = {
            "capabilities": [{"skill_id": "bash"}],
            "safety": {"input_filter": True, "prompt_guard": True},
        }
        result = run_d4_injection_detection(card)
        bare = run_d4_injection_detection({"capabilities": [{"skill_id": "bash"}]})
        assert result["score"] > bare["score"]

    def test_web_fetch_without_sanitizer_triggers_critical(self):
        card = {"capabilities": [{"skill_id": "web_fetch"}]}
        result = run_d4_injection_detection(card)
        cats = {f["category"] for f in result["findings"]}
        assert "indirect_injection_undefended" in cats

    def test_all_subscores_in_range(self):
        card = {"capabilities": [{"skill_id": "bash"}, {"skill_id": "web_fetch"}]}
        result = run_d4_injection_detection(card)
        for name, val in result["subscores"].items():
            assert 0 <= val <= 100, f"{name}={val} out of range"

    def test_overall_score_in_range(self):
        for card in [
            {},
            {"capabilities": [{"skill_id": "bash"}]},
            {"safety": {"input_filter": True}},
            {"capabilities": [{"skill_id": "web_search"}]},
        ]:
            r = run_d4_injection_detection(card)
            assert 0 <= r["score"] <= 100

    def test_summary_fields_present(self):
        result = run_d4_injection_detection({"name": "x"})
        s = result["summary"]
        assert "declared_defenses" in s
        assert "vector_library_size" in s
        assert "critical_count" in s
        assert s["vector_library_size"] == (
            len(DIRECT_INJECTION_VECTORS) + len(INDIRECT_INJECTION_VECTORS) + len(JAILBREAK_VECTORS)
        )

    def test_findings_have_layer_and_root_cause(self):
        result = run_d4_injection_detection({"capabilities": [{"skill_id": "bash"}]})
        for f in result["findings"]:
            assert "layer" in f
            assert "root_cause" in f

    def test_high_risk_caps_defined(self):
        for dim in ("direct", "indirect", "jailbreak"):
            assert len(HIGH_RISK_CAPS[dim]) > 0


class TestD4SecurityIntegration:
    def test_run_d4_security_includes_injection_detection(self):
        card = {"name": "x", "capabilities": [{"skill_id": "bash"}]}
        result = run_d4_security(card)
        assert "injection_detection" in result["subscores"]
        assert "injection_detection_score" in result["summary"]
        assert 0 <= result["subscores"]["injection_detection"] <= 100

    def test_run_d4_security_findings_include_injection(self):
        card = {"capabilities": [{"skill_id": "bash"}]}
        result = run_d4_security(card)
        inj_cats = {f["category"] for f in result["findings"]} & {
            "direct_injection_undefended",
            "indirect_injection_no_defense_declared",
            "jailbreak_undefended",
        }
        assert len(inj_cats) > 0
