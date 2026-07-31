# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.scoring.standards_mapping (Phase 3 §6.3)."""

from mas_eval.scoring.standards_mapping import (
    MITRE_ATLAS_TECHNIQUES,
    NIST_RMF_CONTROLS,
    OWASP_AGENTIC_TOP_10,
    map_category_to_standards,
    map_findings_to_standards,
)


class TestMapCategoryToStandards:
    def test_owasp_map_injection(self):
        r = map_category_to_standards("direct_injection_critical")
        assert r["owasp"] == ["A04"]

    def test_mitre_map_injection(self):
        r = map_category_to_standards("jailbreak_resistance_weak")
        assert r["mitre_atlas"] == ["AML.T0051"]

    def test_nist_map_injection(self):
        r = map_category_to_standards("indirect_injection_tool_output")
        assert "SI-10" in r["nist_rmf"]
        assert "SI-3" in r["nist_rmf"]

    def test_map_category_unknown_default(self):
        r = map_category_to_standards("totally_unknown_category_xyz")
        # Fallback defaults per framework
        assert r["owasp"] == ["A10"]
        assert r["mitre_atlas"] == ["AML.T0051"]
        assert r["nist_rmf"] == ["SI-10"]

    def test_runtime_injection_maps(self):
        # sidecar / runtime injection categories → A04
        r = map_category_to_standards("runtime_injection_critical")
        assert r["owasp"] == ["A04"]
        assert r["mitre_atlas"] == ["AML.T0051"]

    def test_supply_chain_maps(self):
        r1 = map_category_to_standards("vendor_diversity")
        assert r1["owasp"] == ["A09"]
        assert "SR-3" in r1["nist_rmf"]
        r2 = map_category_to_standards("mcp_supply_chain_risk")
        assert r2["owasp"] == ["A09"]
        assert "AML.T0048" in r2["mitre_atlas"]

    def test_all_three_frameworks_present(self):
        r = map_category_to_standards("audit_hmac_missing")
        assert set(r.keys()) == {"owasp", "mitre_atlas", "nist_rmf"}
        assert isinstance(r["owasp"], list)
        assert isinstance(r["mitre_atlas"], list)
        assert isinstance(r["nist_rmf"], list)


class TestMapFindingsToStandards:
    def test_map_findings_empty(self):
        r = map_findings_to_standards([])
        assert r["summary"]["total_findings"] == 0
        assert r["summary"]["mapped_findings"] == 0
        assert r["mappings"] == []
        assert r["unmapped_categories"] == []
        assert r["summary"]["owasp_top_hit"] is None

    def test_map_findings_basic(self):
        findings = [
            {"severity": "CRITICAL", "category": "direct_injection_critical"},
            {"severity": "HIGH", "category": "audit_hmac_missing"},
        ]
        r = map_findings_to_standards(findings)
        assert r["summary"]["total_findings"] == 2
        assert r["summary"]["mapped_findings"] == 2
        assert len(r["mappings"]) == 2
        assert r["mappings"][0]["owasp"] == ["A04"]
        assert r["mappings"][1]["owasp"] == ["A10"]

    def test_map_findings_coverage_aggregation(self):
        # Same prefix twice → coverage count = 2
        findings = [
            {"severity": "CRITICAL", "category": "direct_injection_critical"},
            {"severity": "HIGH", "category": "direct_injection_elevated"},
            {"severity": "WARNING", "category": "jailbreak_resistance_weak"},
        ]
        r = map_findings_to_standards(findings)
        assert r["coverage"]["owasp_agentic"]["A04"] == 3

    def test_unmapped_categories_tracked(self):
        findings = [
            {"severity": "INFO", "category": "unknown_weird_thing"},
            {"severity": "CRITICAL", "category": "direct_injection_critical"},
        ]
        r = map_findings_to_standards(findings)
        assert "unknown_weird_thing" in r["unmapped_categories"]
        # mapped_findings counts only the one that hit a specific prefix
        assert r["summary"]["mapped_findings"] == 1
        assert r["summary"]["total_findings"] == 2

    def test_summary_top_hit(self):
        findings = [
            {"severity": "CRITICAL", "category": "direct_injection_critical"},
            {"severity": "HIGH", "category": "jailbreak_resistance_weak"},
            {"severity": "WARNING", "category": "audit_hmac_missing"},
        ]
        r = map_findings_to_standards(findings)
        # A04 appears twice (injection), A10 once → top hit A04
        assert r["summary"]["owasp_top_hit"] == "A04"

    def test_frameworks_metadata(self):
        r = map_findings_to_standards(
            [{"severity": "INFO", "category": "direct_injection_critical"}]
        )
        assert "owasp_agentic" in r["frameworks"]
        assert "mitre_atlas" in r["frameworks"]
        assert "nist_rmf" in r["frameworks"]
        assert r["frameworks"]["owasp_agentic"]["controls"] is OWASP_AGENTIC_TOP_10


class TestReferenceDicts:
    def test_owasp_top_10_dict_complete(self):
        assert len(OWASP_AGENTIC_TOP_10) == 10
        for i in range(1, 11):
            assert f"A{i:02d}" in OWASP_AGENTIC_TOP_10

    def test_mitre_atlas_dict_populated(self):
        assert "AML.T0051" in MITRE_ATLAS_TECHNIQUES
        assert "AML.T0048" in MITRE_ATLAS_TECHNIQUES

    def test_nist_rmf_dict_populated(self):
        assert "SI-10" in NIST_RMF_CONTROLS
        assert "SR-3" in NIST_RMF_CONTROLS
        assert "AU-6" in NIST_RMF_CONTROLS
