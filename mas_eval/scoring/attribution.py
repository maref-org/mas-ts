# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Bad-Case Attribution aggregation utilities (Gold Standard v3.0-GA §10).

The Gold Standard requires every finding to carry v2 attribution fields
(``layer``, ``root_cause``, ``reproducibility``, ``mitigation``) so that bad
cases can be aggregated and triaged automatically. This module provides
aggregate-by-root-cause / aggregate-by-layer helpers plus a top-level
``generate_attribution_report`` used by L3/L4 to summarize findings.
"""

from collections import Counter
from typing import Any


def aggregate_findings_by_root_cause(
    findings: list[dict[str, Any]],
) -> dict[str, int]:
    """Group findings by their ``root_cause`` field (v2 schema)."""
    return dict(Counter(f.get("root_cause", "unknown") for f in findings))


def aggregate_findings_by_layer(
    findings: list[dict[str, Any]],
) -> dict[str, int]:
    """Group findings by their ``layer`` field (v2 schema)."""
    return dict(Counter(f.get("layer", "tool") for f in findings))


def generate_attribution_report(
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Produce a Bad-Case Attribution report from a list of v2 findings.

    Returns total/critical counts, by-root-cause and by-layer breakdowns,
    top-5 root causes, and auto-recoverable vs manual-intervention counts.
    Findings lacking v2 fields are counted under the ``unknown`` /
    ``tool`` defaults so legacy callers don't break.
    """
    by_cause = Counter(f.get("root_cause", "unknown") for f in findings)
    by_layer = Counter(f.get("layer", "tool") for f in findings)
    critical = [f for f in findings if f.get("severity") == "CRITICAL"]

    return {
        "total_findings": len(findings),
        "critical_count": len(critical),
        "by_root_cause": dict(by_cause),
        "by_layer": dict(by_layer),
        "top_root_causes": by_cause.most_common(5),
        "auto_recoverable": sum(
            1 for f in findings if f.get("mitigation") == "auto_recovery"
        ),
        "needs_manual": sum(
            1 for f in findings if f.get("mitigation") == "manual_intervention"
        ),
        "unrecoverable": sum(
            1 for f in findings if f.get("mitigation") == "unrecoverable"
        ),
    }
