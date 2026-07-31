# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for centralized L1/L2/L3 aggregation (Phase 6.3).

Covers: missing domain, empty findings, weighted score calculation, and
structure compatibility across L1/L2/L3 harness levels.
"""

from mas_eval.harness.aggregation import aggregate_level
from mas_eval.scoring.absolute import DOMAIN_WEIGHTS, compute_overall


def test_aggregate_level_does_not_double_penalize_findings():
    d1 = {"score": 80.0, "findings": [{"severity": "CRITICAL"}]}
    d2 = {"score": 90.0, "findings": []}
    result = aggregate_level("L1", "Test", 0.0, {"d1": d1, "d2": d2})
    assert result["domain_scores"]["d1"] == 80.0
    assert result["score"] == compute_overall(d1=80.0, d2=90.0)
    assert result["verdict"] == "CONDITIONAL"


def test_aggregate_level_preserves_domain_details():
    d1 = {"score": 100.0, "findings": []}
    result = aggregate_level("L1", "Test", 0.0, {"d1": d1})
    assert result["domains"]["d1_detail"] is d1


def test_aggregate_level_clamps_scores_once():
    d1 = {"score": 120.0, "findings": [{"severity": "HIGH"}]}
    result = aggregate_level("L1", "Test", 0.0, {"d1": d1})
    assert result["domain_scores"]["d1"] == 100.0


def test_aggregate_level_handles_missing_domain():
    """Acceptance: missing domain contributes zero weight — score is normalized
    over the present domains only."""
    d1 = {"score": 80.0, "findings": []}
    d3 = {"score": 90.0, "findings": []}
    result = aggregate_level("L1", "L1-partial", 0.0, {"d1": d1, "d3": d3})
    expected = compute_overall(d1=80.0, d3=90.0)
    assert result["score"] == expected
    assert "d2" not in result["domain_scores"]
    assert "d4" not in result["domain_scores"]


def test_aggregate_level_empty_findings_verdict_approved():
    """Acceptance: empty findings list and score >= 70 → APPROVED verdict."""
    d1 = {"score": 95.0, "findings": []}
    d2 = {"score": 90.0, "findings": []}
    d3 = {"score": 85.0, "findings": []}
    result = aggregate_level("L1", "L1-clean", 0.0, {"d1": d1, "d2": d2, "d3": d3})
    assert result["verdict"] == "APPROVED"
    assert result["findings"] == []


def test_aggregate_level_weighted_score_calculation():
    """Acceptance: weighted score matches manual formula using DOMAIN_WEIGHTS."""
    d1 = {"score": 100.0, "findings": []}
    d2 = {"score": 80.0, "findings": []}
    d3 = {"score": 60.0, "findings": []}
    d4 = {"score": 90.0, "findings": []}

    result = aggregate_level(
        "L2", "L2-deep", 0.0, {"d1": d1, "d2": d2, "d3": d3, "d4": d4}
    )

    weighted_sum = (
        100.0 * DOMAIN_WEIGHTS["d1"]
        + 80.0 * DOMAIN_WEIGHTS["d2"]
        + 60.0 * DOMAIN_WEIGHTS["d3"]
        + 90.0 * DOMAIN_WEIGHTS["d4"]
    )
    total_weight = (
        DOMAIN_WEIGHTS["d1"]
        + DOMAIN_WEIGHTS["d2"]
        + DOMAIN_WEIGHTS["d3"]
        + DOMAIN_WEIGHTS["d4"]
    )
    expected = round(weighted_sum / total_weight, 1)
    assert result["score"] == expected


def test_aggregate_level_l1_structure_compatible():
    """L1 result must include keys consumed downstream."""
    d1 = {"score": 80.0, "findings": []}
    d2 = {"score": 80.0, "findings": []}
    d3 = {"score": 80.0, "findings": []}
    result = aggregate_level("L1", "Standard", 0.0, {"d1": d1, "d2": d2, "d3": d3})
    for key in (
        "level",
        "name",
        "elapsed_seconds",
        "score",
        "grade",
        "verdict",
        "domain_scores",
        "domains",
        "findings",
    ):
        assert key in result, f"missing required key: {key}"
    assert set(result["domain_scores"].keys()) == {"d1", "d2", "d3"}


def test_aggregate_level_l3_includes_all_five_domains():
    """L3 must aggregate D1-D5 scores when all five are provided."""
    d1 = {"score": 90.0, "findings": []}
    d2 = {"score": 85.0, "findings": []}
    d3 = {"score": 80.0, "findings": []}
    d4 = {"score": 75.0, "findings": []}
    d5 = {"score": 70.0, "findings": []}
    result = aggregate_level(
        "L3",
        "Comprehensive",
        0.0,
        {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5},
    )
    assert set(result["domain_scores"].keys()) == {"d1", "d2", "d3", "d4", "d5"}
    expected = compute_overall(d1=90.0, d2=85.0, d3=80.0, d4=75.0, d5=70.0)
    assert result["score"] == expected


def test_aggregate_level_empty_domain_results():
    """Edge case: zero domains yields score 0.0 and BLOCKED verdict."""
    result = aggregate_level("L1", "empty", 0.0, {})
    assert result["score"] == 0.0
    assert result["verdict"] == "BLOCKED"
    assert result["findings"] == []


def test_aggregate_level_merges_findings_across_domains():
    """Findings from all domains should be merged in order."""
    d1 = {"score": 80.0, "findings": [{"severity": "WARNING", "category": "d1_w"}]}
    d2 = {"score": 80.0, "findings": [{"severity": "HIGH", "category": "d2_h"}]}
    d3 = {"score": 80.0, "findings": [{"severity": "INFO", "category": "d3_i"}]}
    result = aggregate_level("L1", "L1-findings", 0.0, {"d1": d1, "d2": d2, "d3": d3})
    categories = [f["category"] for f in result["findings"]]
    assert categories == ["d1_w", "d2_h", "d3_i"]
