# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for v0.8.0 backdoor detection baseline.

Validates that D1.14, D4 steganography_audit, D4 data_leakage, and
auto_red_team continue to detect the Claude Code backdoor patterns
captured in the v0.8.0 baseline snapshot.

If a test in this file fails, it means a code change has weakened
or strengthened backdoor detection — investigate before merging.

Baseline file: mas_eval/data/baselines/backdoor_detection_baseline.json
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d1_compliance import (
    check_capability_declaration_completeness,
    run_d1,
)
from mas_eval.domains.d4_data_leakage import run_d4_data_leakage_full
from mas_eval.domains.d4_steganography_audit import run_d4_steganography_audit
from mas_eval.scoring.meta_evaluator import auto_red_team

# ═══════════════════════════════════════════════════════════════
# Load baseline
# ═══════════════════════════════════════════════════════════════


BASELINE_PATH = (
    Path(__file__).parent.parent
    / "mas_eval"
    / "data"
    / "baselines"
    / "backdoor_detection_baseline.json"
)

with open(BASELINE_PATH) as f:
    BASELINE = json.load(f)

TOLERANCE_SCORE = BASELINE["tolerance"]["score_delta"]
TOLERANCE_CRITICAL = BASELINE["tolerance"]["critical_count_delta"]


def _load_card(card_path: str) -> dict:
    full_path = Path(__file__).parent.parent / card_path
    with open(full_path) as f:
        return json.load(f)


def _count_critical(findings: list[dict]) -> int:
    return sum(1 for f in findings if f.get("severity") == "CRITICAL")


# ═══════════════════════════════════════════════════════════════
# TestBackdoorDetectionBaseline — Claude Code Compromised
# ═══════════════════════════════════════════════════════════════


class TestCompromisedCardRegression:
    """Regression: claude_code_compromised must remain fully detected."""

    @pytest.fixture(scope="class")
    def card(self) -> dict:
        return _load_card(
            BASELINE["test_cards"]["claude_code_compromised"]["card_path"]
        )

    @pytest.fixture(scope="class")
    def expected(self) -> dict:
        return BASELINE["test_cards"]["claude_code_compromised"]

    def test_d1_score_blocked(self, card, expected):
        """D1 score must be 0 (NON-COMPLIANT blocked) for compromised card."""
        result = run_d1(card)
        assert abs(result["score"] - expected["expected_d1_score"]) <= TOLERANCE_SCORE
        assert "NON-COMPLIANT" in result.get("conformance_verdict", "")

    def test_d1_14_flags_undeclared_sub_permissions(self, card, expected):
        """D1.14 must find 3 missing sub_permissions (bash, file_read, file_edit)."""
        findings = check_capability_declaration_completeness(card)
        assert len(findings) == expected["expected_d1_14_finding_count"]
        assert all(f["severity"] == "HIGH" for f in findings)
        assert all(f["root_cause"] == "declaration_inconsistency" for f in findings)

    def test_steganography_audit_detects_backdoor(self, card, expected):
        """D4 steganography_audit must detect 5 CRITICAL findings."""
        result = run_d4_steganography_audit(card)
        critical_count = _count_critical(result["findings"])
        assert (
            critical_count == expected["expected_steganography_audit_critical_count"]
        ), (
            f"CRITICAL count drift: expected {expected['expected_steganography_audit_critical_count']}, "
            f"got {critical_count}. CRITICAL count change = detection regression."
        )
        assert (
            abs(result["score"] - expected["expected_steganography_audit_score"])
            <= TOLERANCE_SCORE
        )

    def test_data_leakage_detects_covert_collection(self, card, expected):
        """D4 data_leakage must detect covert_collection (bash+bridge pattern)."""
        result = run_d4_data_leakage_full(card)
        critical_count = _count_critical(result["findings"])
        assert critical_count == expected["expected_data_leakage_critical_count"], (
            f"CRITICAL count drift: expected {expected['expected_data_leakage_critical_count']}, "
            f"got {critical_count}."
        )
        assert (
            abs(result["score"] - expected["expected_data_leakage_score"])
            <= TOLERANCE_SCORE
        )

    def test_auto_red_team_flags_compromised(self, card):
        """auto_red_team must heavily penalize compromised card."""
        art_baseline = BASELINE["auto_red_team_baseline"]["claude_code_compromised"]
        result = auto_red_team(card)
        assert (
            result["anti_cheat_score"] <= art_baseline["expected_anti_cheat_score_max"]
        ), (
            f"anti_cheat_score too high for compromised card: {result['anti_cheat_score']}"
        )
        assert (
            len(result["detected_behaviors"])
            >= art_baseline["expected_detected_behaviors_min"]
        )
        assert result["probe_count"] == art_baseline["expected_probe_count"]


# ═══════════════════════════════════════════════════════════════
# TestBackdoorDetectionBaseline — Claude Code Clean
# ═══════════════════════════════════════════════════════════════


class TestCleanCardRegression:
    """Regression: claude_code_clean must remain largely clean (no false positives)."""

    @pytest.fixture(scope="class")
    def card(self) -> dict:
        return _load_card(BASELINE["test_cards"]["claude_code_clean"]["card_path"])

    @pytest.fixture(scope="class")
    def expected(self) -> dict:
        return BASELINE["test_cards"]["claude_code_clean"]

    def test_d1_score_compliant(self, card, expected):
        """D1 score must be >= 90 for clean card."""
        result = run_d1(card)
        assert abs(result["score"] - expected["expected_d1_score"]) <= TOLERANCE_SCORE
        assert "COMPLIANT" in result.get("conformance_verdict", "")

    def test_d1_14_no_findings(self, card, expected):
        """D1.14 must find 0 issues for clean card (all sub_permissions declared)."""
        findings = check_capability_declaration_completeness(card)
        assert len(findings) == expected["expected_d1_14_finding_count"]

    def test_steganography_audit_score_high(self, card, expected):
        """D4 steganography_audit score must remain high (>= 90)."""
        result = run_d4_steganography_audit(card)
        critical_count = _count_critical(result["findings"])
        assert critical_count == expected["expected_steganography_audit_critical_count"]
        assert (
            abs(result["score"] - expected["expected_steganography_audit_score"])
            <= TOLERANCE_SCORE
        )

    def test_data_leakage_score_high(self, card, expected):
        """D4 data_leakage score must remain high (>= 90)."""
        result = run_d4_data_leakage_full(card)
        critical_count = _count_critical(result["findings"])
        assert critical_count == expected["expected_data_leakage_critical_count"]
        assert (
            abs(result["score"] - expected["expected_data_leakage_score"])
            <= TOLERANCE_SCORE
        )

    def test_auto_red_team_clean_card(self, card):
        """auto_red_team must give clean card a high score."""
        art_baseline = BASELINE["auto_red_team_baseline"]["claude_code_clean"]
        result = auto_red_team(card)
        assert (
            result["anti_cheat_score"] >= art_baseline["expected_anti_cheat_score_min"]
        ), f"anti_cheat_score too low for clean card: {result['anti_cheat_score']}"
        assert (
            len(result["detected_behaviors"])
            <= art_baseline["expected_detected_behaviors_max"]
        )


# ═══════════════════════════════════════════════════════════════
# TestBackdoorDetectionBaseline — Unicode Steganography Sample
# ═══════════════════════════════════════════════════════════════


class TestUnicodeSteganographyRegression:
    """Regression: unicode_steganography card must trigger multi-variant detection."""

    @pytest.fixture(scope="class")
    def card(self) -> dict:
        return _load_card(BASELINE["test_cards"]["unicode_steganography"]["card_path"])

    @pytest.fixture(scope="class")
    def expected(self) -> dict:
        return BASELINE["test_cards"]["unicode_steganography"]

    def test_d1_score_compliant(self, card, expected):
        """D1 score must be high (Unicode card is otherwise compliant)."""
        result = run_d1(card)
        assert abs(result["score"] - expected["expected_d1_score"]) <= TOLERANCE_SCORE

    def test_d1_14_no_findings(self, card, expected):
        """D1.14 must find 0 issues (bash sub_permissions declared)."""
        findings = check_capability_declaration_completeness(card)
        assert len(findings) == expected["expected_d1_14_finding_count"]

    def test_steganography_audit_detects_multi_variant(self, card, expected):
        """D4 steganography_audit must detect unicode_multi_variant_apostrophe."""
        result = run_d4_steganography_audit(card)
        critical_count = _count_critical(result["findings"])
        assert critical_count == expected["expected_steganography_audit_critical_count"]
        assert (
            abs(result["score"] - expected["expected_steganography_audit_score"])
            <= TOLERANCE_SCORE
        )
        # Verify the specific finding category
        categories = {f.get("category") for f in result["findings"]}
        assert "unicode_multi_variant_apostrophe" in categories, (
            f"Must detect unicode_multi_variant_apostrophe, got: {categories}"
        )

    def test_data_leakage_score_high(self, card, expected):
        """D4 data_leakage score must remain high (no leakage indicators)."""
        result = run_d4_data_leakage_full(card)
        critical_count = _count_critical(result["findings"])
        assert critical_count == expected["expected_data_leakage_critical_count"]
        assert (
            abs(result["score"] - expected["expected_data_leakage_score"])
            <= TOLERANCE_SCORE
        )

    def test_auto_red_team_triggers_steganography(self, card):
        """auto_red_team must trigger static_steganography probe."""
        art_baseline = BASELINE["auto_red_team_baseline"]["unicode_steganography"]
        result = auto_red_team(card)
        assert (
            result["anti_cheat_score"] <= art_baseline["expected_anti_cheat_score_max"]
        )
        assert (
            len(result["detected_behaviors"])
            >= art_baseline["expected_detected_behaviors_min"]
        )
        # Must specifically trigger steganography probe
        types = {d["type"] for d in result["detected_behaviors"]}
        assert "static_steganography" in types


# ═══════════════════════════════════════════════════════════════
# TestBaselineFileIntegrity
# ═══════════════════════════════════════════════════════════════


class TestBaselineFileIntegrity:
    """Validate the baseline JSON file itself is well-formed."""

    def test_baseline_has_required_top_level_fields(self):
        """Baseline must have version, date, tolerance, test_cards."""
        required = ["baseline_version", "baseline_date", "tolerance", "test_cards"]
        for field in required:
            assert field in BASELINE, f"Missing required field: {field}"

    def test_baseline_tolerance_values(self):
        """Tolerance must be non-negative numbers."""
        assert TOLERANCE_SCORE >= 0
        assert TOLERANCE_CRITICAL >= 0

    def test_baseline_has_3_test_cards(self):
        """Baseline must include 3 test cards (compromised, clean, unicode)."""
        cards = BASELINE["test_cards"]
        assert "claude_code_compromised" in cards
        assert "claude_code_clean" in cards
        assert "unicode_steganography" in cards

    def test_baseline_test_cards_have_expected_scores(self):
        """Each test card must declare expected scores."""
        for name, card in BASELINE["test_cards"].items():
            assert "expected_d1_score" in card, f"{name} missing expected_d1_score"
            assert "expected_steganography_audit_score" in card
            assert "expected_data_leakage_score" in card

    def test_baseline_auto_red_team_section_complete(self):
        """auto_red_team_baseline section must cover all 3 cards."""
        art = BASELINE["auto_red_team_baseline"]
        for card_name in BASELINE["test_cards"]:
            assert card_name in art, f"{card_name} missing from auto_red_team_baseline"

    def test_baseline_test_card_files_exist(self):
        """All referenced card_path files must exist."""
        for name, card in BASELINE["test_cards"].items():
            card_path = Path(__file__).parent.parent / card["card_path"]
            assert card_path.exists(), f"{name}: card file not found at {card_path}"


# ═══════════════════════════════════════════════════════════════
# Phase 3 (v0.8.3) — Probe 4: adversarial_prompt_mutation
# ═══════════════════════════════════════════════════════════════


class TestProbe4AdversarialMutation:
    """Probe 4 (framework self-assessment) always runs and reports robustness."""

    @pytest.fixture(scope="class")
    def card(self) -> dict:
        return _load_card(
            BASELINE["test_cards"]["claude_code_clean"]["card_path"]
        )

    def test_auto_red_team_probe4_always_runs(self, card):
        """Without sidecar_log, probe_count must be 3 (was 2 pre-Phase-3).

        Probe 4 (adversarial_prompt_mutation) always runs regardless of
        sidecar_log, so the no-sidecar probe_count is 3 (steg + leakage +
        probe4), not 2.
        """
        result = auto_red_team(card)
        assert result["probe_count"] == 3

    def test_auto_red_team_framework_robustness_field(self, card):
        """framework_robustness dict must be present with escape_rate/score."""
        result = auto_red_team(card)
        fr = result["framework_robustness"]
        assert "escape_rate" in fr
        assert "score" in fr
        assert "total_mutations" in fr
        assert "escapes" in fr
        assert "verdict" in fr
        assert fr["total_mutations"] == 70  # 14 canonical × 5 operators
        assert 0.0 <= fr["escape_rate"] <= 1.0
        assert 0.0 <= fr["score"] <= 100.0
        assert fr["verdict"] in ("excellent", "good", "fair", "poor")
        # Probe 4 is framework self-assessment → must NOT affect anti_cheat
        # (clean card → anti_cheat unchanged by probe 4)
        assert "framework_robustness_score" in result["summary"]

    def test_auto_red_team_probe4_not_in_detected(self, card):
        """Probe 4 must not appear in detected_behaviors (it tests the
        framework, not the agent card)."""
        result = auto_red_team(card)
        types = {d["type"] for d in result["detected_behaviors"]}
        assert "adversarial_prompt_mutation" not in types
