# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0-GA: Findings Schema v2 — Extended Attribution.

Gold Standard requires findings to include layer, root_cause,
reproducibility, and mitigation information for bad case attribution.

Usage:
    f = Finding(severity="HIGH", category="step_efficiency_poor",
                detail="Optimality ratio 0.25", layer="tool",
                root_cause="plan_quality")
"""

from dataclasses import dataclass
from typing import Any

SEVERITY_LEVELS = ("CRITICAL", "HIGH", "WARNING", "INFO")
LAYER_TYPES = ("tool", "reasoning", "model", "coordination", "safety")
ROOT_CAUSES = (
    "tool_selection",
    "parameter_error",
    "hallucination",
    "plan_quality",
    "coordination_failure",
    "permission_violation",
    "data_leakage",
    "resource_exhaustion",
    "network_failure",
    "cascade_failure",
    "unknown",
)
REPRODUCIBILITY = ("deterministic", "stochastic", "environment_dependent")
MITIGATION = ("auto_recovery", "manual_intervention", "unrecoverable")


@dataclass
class Finding:
    """Gold Standard Finding with full attribution fields."""

    severity: str
    category: str
    detail: str
    layer: str = "tool"
    root_cause: str = "unknown"
    reproducibility: str = "stochastic"
    mitigation: str = "auto_recovery"

    def __post_init__(self) -> None:
        assert self.severity in SEVERITY_LEVELS, (
            f"Invalid severity: {self.severity}. Must be one of {SEVERITY_LEVELS}"
        )
        assert self.layer in LAYER_TYPES, (
            f"Invalid layer: {self.layer}. Must be one of {LAYER_TYPES}"
        )
        assert self.root_cause in ROOT_CAUSES, (
            f"Invalid root_cause: {self.root_cause}. Must be one of {ROOT_CAUSES}"
        )
        assert self.reproducibility in REPRODUCIBILITY
        assert self.mitigation in MITIGATION

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict (backward-compatible with v3.0 findings)."""
        return {
            "severity": self.severity,
            "category": self.category,
            "detail": self.detail,
            "layer": self.layer,
            "root_cause": self.root_cause,
            "reproducibility": self.reproducibility,
            "mitigation": self.mitigation,
        }


def legacy_to_v2(old_finding: dict[str, Any]) -> Finding:
    """Upgrade a v3.0 finding to v2 schema with defaults for missing fields."""
    return Finding(
        severity=old_finding.get("severity", "INFO"),
        category=old_finding.get("category", "uncategorized"),
        detail=old_finding.get("detail", ""),
        layer=old_finding.get("layer", "tool"),
        root_cause=old_finding.get("root_cause", "unknown"),
        reproducibility=old_finding.get("reproducibility", "stochastic"),
        mitigation=old_finding.get("mitigation", "auto_recovery"),
    )
