# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Gold Standard Certification JSON Report Generator.

Aggregates data from gold_certificate.py and gold_thresholds.py into a
unified JSON report consumable by CI pipelines and the ASCII dashboard.

Usage:
    report = generate_report(agent_id, domain_scores, level, findings)
    save_report(report, "reports/gold-report.json")
"""

import datetime
import json
import os
from pathlib import Path
from typing import Any

from mas_eval.scoring.absolute import (
    compute_gold_overall,
    determine_gold_verdict,
    score_to_grade,
)
from mas_eval.scoring.gold_certificate import (
    generate_gold_certificate,
)
from mas_eval.scoring.gold_thresholds import (
    GOLD_THRESHOLD_MATRIX,
)
from mas_eval.scoring.standards_mapping import map_findings_to_standards

DEFAULT_REPORT_DIR = "reports"


def generate_report(
    agent_id: str,
    domain_scores: dict[str, float],
    level: str = "L3",
    findings: list[dict[str, Any]] | None = None,
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
    valid_days: int = 90,
    signature_key: str | None = None,
    execution_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a gold standard JSON report.

    Args:
        agent_id: Unique agent identifier.
        domain_scores: Dict mapping domain keys (d1-d5) to float scores 0-100.
        level: Execution level (L0-L4).
        findings: Optional list of finding dicts.
        consistency_index: Optional Consistency Index (0.0-1.0).
        cost_efficiency: Optional Cost Efficiency score (0.0-1.0).
        valid_days: Certificate validity in days.
        signature_key: Optional HMAC key for certificate signing.
        execution_metadata: Optional extra metadata (duration_ms, tests_passed, etc).

    Returns:
        Dict with certificate, dimensions, and execution sections.
    """
    findings = findings or []
    execution_metadata = execution_metadata or {}

    overall = compute_gold_overall(
        **domain_scores,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
    )
    grade = score_to_grade(overall)
    verdict = determine_gold_verdict(overall, findings, consistency_index)

    cert = generate_gold_certificate(
        agent_id=agent_id,
        score=overall,
        grade=grade,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
        valid_days=valid_days,
        signature_key=signature_key,
    )

    thresholds = GOLD_THRESHOLD_MATRIX.get(level, {})

    dimensions: dict[str, Any] = {}
    level_threshold = float(thresholds.get("overall_score", 78))
    for dom_key, score in domain_scores.items():
        dimensions[dom_key] = {
            "score": score,
            "threshold": level_threshold,
            "passed": score >= level_threshold,
        }

    ts = datetime.datetime.now().isoformat()
    exec_meta = {
        "timestamp": ts,
        "duration_ms": execution_metadata.get("duration_ms", 0),
        "tests_passed": execution_metadata.get("tests_passed", 0),
        "tests_total": execution_metadata.get("tests_total", 0),
        "coverage_pct": execution_metadata.get("coverage_pct", 0.0),
        "level": level,
    }

    return {
        "certificate": {
            "agent_id": agent_id,
            "cert_id": cert["cert_id"],
            "score": overall,
            "grade": grade,
            "compliance_level": cert["compliance_level"],
            "ci": consistency_index,
            "ce": cost_efficiency,
            "valid_until": cert["valid_until"],
            "verdict": verdict,
            "badge": cert["badge"],
        },
        "dimensions": dimensions,
        "findings": [
            {
                "severity": f.get("severity", "INFO"),
                "category": f.get("category", "general"),
                "detail": f.get("detail", ""),
            }
            for f in findings
        ],
        "execution": exec_meta,
        "standards_mapping": map_findings_to_standards(findings) if findings else None,
    }


def save_report(report: dict[str, Any], path: str | None = None) -> str:
    """Save a gold report to a JSON file.

    Args:
        report: Report dict from generate_report().
        path: Output file path. Defaults to reports/gold-report-{agent_id}.json.

    Returns:
        The absolute path of the saved file.
    """
    if path is None:
        agent_id = report.get("certificate", {}).get("agent_id", "unknown")
        path = os.path.join(DEFAULT_REPORT_DIR, f"gold-report-{agent_id}.json")

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    return os.path.abspath(path)


def load_report(path: str) -> dict[str, Any]:
    """Load a gold report from a JSON file.

    Args:
        path: Path to the JSON report file.

    Returns:
        Report dict.
    """
    result: dict[str, Any] = json.loads(Path(path).read_text())
    return result
