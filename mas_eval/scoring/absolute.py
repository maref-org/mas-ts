# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Absolute Scoring Model for MAS-TS-001 v3.0.

Usage:
  score = score_domain(raw, findings)
  grade = score_to_grade(score)
  verdict = determine_verdict(overall, findings)
  overall = compute_overall(d1, d2, d3, d4, d5)
"""

DOMAIN_WEIGHTS = {
    "d1": 0.10,
    "d2": 0.25,
    "d3": 0.25,
    "d4": 0.20,
    "d5": 0.20,
}

SEVERITY_PENALTIES = {
    "CRITICAL": -25,
    "HIGH": -15,
    "WARNING": -5,
    "INFO": 0,
}

GRADE_THRESHOLDS = [
    ("A+", 97),
    ("A", 93),
    ("A-", 90),
    ("B+", 87),
    ("B", 83),
    ("B-", 80),
    ("C+", 77),
    ("C", 73),
    ("C-", 70),
    ("D+", 67),
    ("D", 63),
    ("D-", 60),
]


def score_domain(raw_score, findings=None):
    """Score a domain result, capping at 0-100 and applying findings.

    Args:
    raw_score: Raw domain score (float).
    findings: Optional list of finding dicts from domain evaluation.

    Returns:
    Capped float score 0.0-100.0.
    """
    s = raw_score
    for f in findings or []:
        s += SEVERITY_PENALTIES.get(f.get("severity", "INFO"), 0)
    return max(0, min(100, round(s, 1)))


def score_to_grade(score):
    """Convert a numeric score to a letter grade.

    Thresholds: >=90 A, >=80 B, >=70 C, >=60 D, else F.

    Args:
    score: Numeric score 0-100.

    Returns:
    Letter grade string: "A", "B", "C", "D", or "F".
    """
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 63:
        return "D"
    if score >= 60:
        return "D-"
    return "F"


def grade_to_emoji(grade):
    """Map a letter grade to a visual emoji indicator.

    Args:
    grade: Letter grade string ("A" through "F").

    Returns:
    Emoji string.
    """
    mapping = {
        "A+": "🟢",
        "A": "🟢",
        "A-": "🟢",
        "B+": "🟢",
        "B": "🟢",
        "B-": "🟡",
        "C+": "🟡",
        "C": "🟡",
        "C-": "🟡",
        "D+": "🟠",
        "D": "🟠",
        "D-": "🟠",
        "F": "🔴",
    }
    return mapping.get(grade, "⚪")


def compute_overall(d1=None, d2=None, d3=None, d4=None, d5=None):
    """Compute weighted overall score from domain scores.

    Weights: D1=0.10, D2=0.25, D3=0.25, D4=0.20, D5=0.20.
    Only weighted domains with non-None scores contribute.

    Args:
    d1-d5: Optional domain scores (float 0-100 or None).

    Returns:
    Weighted float score 0.0-100.0.
    """
    scores = {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5}
    total_weight = 0.0
    weighted_sum = 0.0

    for key, weight in DOMAIN_WEIGHTS.items():
        s = scores.get(key)
        if s is not None:
            weighted_sum += s * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 1)


def determine_verdict(overall, findings=None, severity_threshold="CRITICAL"):
    """Determine PASS/WARNING/FAIL verdict based on overall score and findings.

    CRITICAL severity findings trigger FAIL regardless of score.
    HIGH findings or score < 70 trigger WARNING.

    Args:
    overall: Overall weighted score.
    findings: Optional list of finding dicts.
    severity_threshold: Minimum severity to auto-fail (default "CRITICAL").

    Returns:
    Verdict string: "PASS", "WARNING", or "FAIL".
    """
    has_blocker = False
    for f in findings or []:
        if f.get("severity") == severity_threshold:
            has_blocker = True
            break

    if overall >= 70 and not has_blocker:
        return "APPROVED"
    if overall >= 50:
        return "CONDITIONAL"
    return "BLOCKED"


def domain_weights_summary():
    """Return summary of domain weights used in scoring.

    Returns:
    Dict mapping domain names to their weights.
    """
    return {k: v for k, v in DOMAIN_WEIGHTS.items()}
