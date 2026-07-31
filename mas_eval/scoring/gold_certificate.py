# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Gold Standard Certification Badge Generator.

Generates ASCII-art certification badges for Gold Standard compliance levels.

Usage:
    badge = generate_gold_certificate(agent_id, score, ci, ce)
    print(badge)
"""

import datetime
import hashlib
from typing import Any


def generate_gold_certificate(
    agent_id: str,
    score: float,
    grade: str,
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
    valid_days: int = 90,
    signature_key: str | None = None,
) -> dict[str, Any]:
    """Generate a Gold Standard certification certificate.

    Args:
        agent_id: Unique agent identifier.
        score: Overall Gold Standard score (0.0-100.0).
        grade: Grade (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-).
        consistency_index: Consistency Index score (0.0-1.0).
        cost_efficiency: Cost Efficiency score (0.0-1.0).
        valid_days: Certificate validity in days.
        signature_key: Optional HMAC key for certificate signing.

    Returns:
        Dict with certificate data and ASCII badge.
    """
    # Calculate validity period
    valid_until = datetime.datetime.now() + datetime.timedelta(days=valid_days)
    valid_until_str = valid_until.strftime("%Y-%m-%d")

    # Determine compliance level
    compliance_level = _get_compliance_level(score, consistency_index)

    # Generate certificate ID
    cert_id = _generate_cert_id(agent_id, score, valid_until_str, signature_key)

    # Generate ASCII badge
    badge = _generate_ascii_badge(
        agent_id=agent_id,
        score=score,
        grade=grade,
        compliance_level=compliance_level,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
        valid_until=valid_until_str,
        cert_id=cert_id,
    )

    return {
        "agent_id": agent_id,
        "cert_id": cert_id,
        "score": score,
        "grade": grade,
        "compliance_level": compliance_level,
        "consistency_index": consistency_index,
        "cost_efficiency": cost_efficiency,
        "valid_until": valid_until_str,
        "badge": badge,
        "verified": signature_key is not None,
    }


def _get_compliance_level(
    score: float,
    consistency_index: float | None = None,
) -> str:
    """Determine compliance level based on score and CI."""
    ci = consistency_index or 0.0

    if score >= 90 and ci >= 0.85:
        return "GOLD"
    elif score >= 78 and ci >= 0.75:
        return "GOLD"
    elif score >= 70 and ci >= 0.60:
        return "SILVER"
    elif score >= 60 and ci >= 0.50:
        return "BRONZE"
    else:
        return "FAIL"


def _generate_cert_id(
    agent_id: str,
    score: float,
    valid_until: str,
    signature_key: str | None = None,
) -> str:
    """Generate a unique certificate ID."""
    data = f"{agent_id}:{score}:{valid_until}"
    if signature_key:
        data = f"{data}:{signature_key}"

    hash_obj = hashlib.sha256(data.encode())
    return f"MAS-TS-GOLD-{hash_obj.hexdigest()[:16].upper()}"


def _generate_ascii_badge(
    agent_id: str,
    score: float,
    grade: str,
    compliance_level: str,
    consistency_index: float | None,
    cost_efficiency: float | None,
    valid_until: str,
    cert_id: str,
) -> str:
    """Generate ASCII-art certification badge."""
    ci_str = f"{consistency_index:.2f}" if consistency_index is not None else "N/A"
    ce_str = f"{cost_efficiency:.2f}" if cost_efficiency is not None else "N/A"

    # Choose badge style based on compliance level
    if compliance_level == "GOLD":
        badge = f"""
┌─────────────────────────────────────────┐
│       ★ MAS-TS-001 GOLD ★              │
│    Multi-Agent System Test Standard     │
│                                         │
│         ★ OFFICIAL GOLD ★              │
│                                         │
│    Agent: {agent_id[:30]:<30}│
│    Score: {score:.1f}/100                    │
│    Grade: {grade:<30}│
│    Consistency Index: {ci_str:<17}│
│    Cost Efficiency: {ce_str:<19}│
│                                         │
│    Cert ID: {cert_id[:28]}│
│    Valid until: {valid_until:<23}│
└─────────────────────────────────────────┘
"""
    elif compliance_level == "SILVER":
        badge = f"""
┌─────────────────────────────────────────┐
│       ◆ MAS-TS-001 SILVER ◆            │
│    Multi-Agent System Test Standard     │
│                                         │
│        ◆ OFFICIAL SILVER ◆             │
│                                         │
│    Agent: {agent_id[:30]:<30}│
│    Score: {score:.1f}/100                    │
│    Grade: {grade:<30}│
│    Consistency Index: {ci_str:<17}│
│    Cost Efficiency: {ce_str:<19}│
│                                         │
│    Cert ID: {cert_id[:28]}│
│    Valid until: {valid_until:<23}│
└─────────────────────────────────────────┘
"""
    elif compliance_level == "BRONZE":
        badge = f"""
┌─────────────────────────────────────────┐
│       ● MAS-TS-001 BRONZE ●            │
│    Multi-Agent System Test Standard     │
│                                         │
│        ● OFFICIAL BRONZE ●             │
│                                         │
│    Agent: {agent_id[:30]:<30}│
│    Score: {score:.1f}/100                    │
│    Grade: {grade:<30}│
│    Consistency Index: {ci_str:<17}│
│    Cost Efficiency: {ce_str:<19}│
│                                         │
│    Cert ID: {cert_id[:28]}│
│    Valid until: {valid_until:<23}│
└─────────────────────────────────────────┘
"""
    else:
        badge = f"""
┌─────────────────────────────────────────┐
│       ✗ MAS-TS-001 FAIL ✗              │
│    Multi-Agent System Test Standard     │
│                                         │
│    Agent: {agent_id[:30]:<30}│
│    Score: {score:.1f}/100                    │
│    Grade: {grade:<30}│
│    Status: NOT COMPLIANT                │
│                                         │
│    Cert ID: {cert_id[:28]}│
│    Valid until: {valid_until:<23}│
└─────────────────────────────────────────┘
"""

    return badge.strip()


def verify_certificate(
    certificate: dict[str, Any],
    signature_key: str | None = None,
) -> bool:
    """Verify a Gold Standard certificate.

    Args:
        certificate: Certificate dict from generate_gold_certificate().
        signature_key: Optional HMAC key for verification.

    Returns:
        True if certificate is valid, False otherwise.
    """
    # Check required fields
    required_fields = ["agent_id", "cert_id", "score", "grade", "valid_until"]
    for field in required_fields:
        if field not in certificate:
            return False

    # Check expiration
    try:
        valid_until = datetime.datetime.strptime(certificate["valid_until"], "%Y-%m-%d")
        if valid_until < datetime.datetime.now():
            return False
    except ValueError:
        return False

    # Verify certificate ID if key provided
    if signature_key and certificate.get("verified"):
        expected_id = _generate_cert_id(
            certificate["agent_id"],
            certificate["score"],
            certificate["valid_until"],
            signature_key,
        )
        if certificate["cert_id"] != expected_id:
            return False

    return True


def generate_compliance_report(
    agent_id: str,
    level_results: dict[str, Any],
    overall_score: float,
    grade: str,
) -> str:
    """Generate a detailed compliance report.

    Args:
        agent_id: Agent identifier.
        level_results: Results from check_gold_standard_compliance().
        overall_score: Overall score.
        grade: Grade.

    Returns:
        Formatted compliance report string.
    """
    report_lines = [
        "=" * 60,
        "  MAS-TS-001 Gold Standard Compliance Report",
        "=" * 60,
        "",
        f"  Agent ID: {agent_id}",
        f"  Overall Score: {overall_score:.1f}/100",
        f"  Grade: {grade}",
        f"  Verdict: {level_results.get('verdict', 'FAIL')}",
        "",
        "  Level Results:",
        "-" * 60,
    ]

    for level, result in level_results.get("levels", {}).items():
        status = "✓ PASS" if result["overall_pass"] else "✗ FAIL"
        report_lines.append(
            f"  {level}: {status} ({result['passed_count']}/{result['total_count']} metrics)"
        )

    report_lines.extend(
        [
            "-" * 60,
            f"  Critical Findings: {level_results.get('critical_findings', 0)}",
            f"  Total Findings: {level_results.get('findings_count', 0)}",
            "=" * 60,
        ]
    )

    return "\n".join(report_lines)
