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
    "steganography_backdoor",
    "declaration_inconsistency",
    "declaration_runtime_mismatch",
    "runtime_violation",
    "undeclared_steganography",
    "binary_pattern_match",
    "resource_exhaustion",
    "network_failure",
    "cascade_failure",
    "unknown",
)
REPRODUCIBILITY = ("deterministic", "stochastic", "environment_dependent")
MITIGATION = ("auto_recovery", "manual_intervention", "unrecoverable")

# Gold Standard §10 — domain-specific v2 attribution defaults. Findings from a
# given domain tend to share a layer/root_cause profile, so callers can pass
# ``domain="d3"`` to upgrade_findings_to_v2 instead of spelling out all four
# default_* kwargs. Explicit kwargs still override these when both are given.
DOMAIN_DEFAULTS: dict[str, dict[str, str]] = {
    "d1": {
        "layer": "safety",
        "root_cause": "permission_violation",
        "reproducibility": "deterministic",
        "mitigation": "manual_intervention",
    },
    "d2": {
        "layer": "tool",
        "root_cause": "tool_selection",
        "reproducibility": "stochastic",
        "mitigation": "auto_recovery",
    },
    "d3": {
        "layer": "coordination",
        "root_cause": "coordination_failure",
        "reproducibility": "stochastic",
        "mitigation": "auto_recovery",
    },
    "d4": {
        "layer": "safety",
        "root_cause": "permission_violation",
        "reproducibility": "deterministic",
        "mitigation": "manual_intervention",
    },
    "d5": {
        "layer": "model",
        "root_cause": "network_failure",
        "reproducibility": "stochastic",
        "mitigation": "auto_recovery",
    },
}


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


def upgrade_findings_to_v2(
    findings: list[dict[str, Any]],
    default_layer: str = "tool",
    default_root_cause: str = "unknown",
    default_reproducibility: str = "stochastic",
    default_mitigation: str = "auto_recovery",
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Augment a list of legacy findings with v2 attribution fields.

    Each finding dict is preserved as-is (including any domain-specific
    extras like ``check`` or ``subscore``); the four Gold Standard
    attribution fields (``layer``/``root_cause``/``reproducibility``/
    ``mitigation``) are added when missing. Pre-existing v2 fields are
    left untouched. This lets every domain produce v2-compliant findings
    without rewriting every ``findings.append(...)`` call site and without
    losing domain-specific extras that downstream tests rely on.

    Args:
        findings: List of legacy finding dicts (or v2 dicts to pass through).
        default_layer: Default ``layer`` value (one of :data:`LAYER_TYPES`).
        default_root_cause: Default ``root_cause`` value (one of
            :data:`ROOT_CAUSES`).
        default_reproducibility: Default ``reproducibility`` value.
        default_mitigation: Default ``mitigation`` value.
        domain: Optional domain key (``"d1"``-``"d5"``). When set, fills any
            ``default_*`` argument left at its function default from
            :data:`DOMAIN_DEFAULTS`, so callers can write
            ``upgrade_findings_to_v2(findings, domain="d3")``. Explicit
            ``default_*`` kwargs still take precedence.

    Returns:
        New list of finding dicts, each containing the full v2 schema plus
        any original extras.
    """
    # Apply domain-specific defaults for any default_* left at the function
    # default. Explicit kwargs (not equal to the function default) win.
    if domain and domain in DOMAIN_DEFAULTS:
        dd = DOMAIN_DEFAULTS[domain]
        if default_layer == "tool":
            default_layer = dd["layer"]
        if default_root_cause == "unknown":
            default_root_cause = dd["root_cause"]
        if default_reproducibility == "stochastic":
            default_reproducibility = dd["reproducibility"]
        if default_mitigation == "auto_recovery":
            default_mitigation = dd["mitigation"]

    upgraded: list[dict[str, Any]] = []
    for f in findings:
        # Validate v2 enum values via Finding (raises on invalid input), but
        # keep the original dict and only inject the four v2 fields so we
        # don't drop domain-specific extras like "check" / "subscore".
        normalized = dict(f)
        normalized.setdefault("layer", default_layer)
        normalized.setdefault("root_cause", default_root_cause)
        normalized.setdefault("reproducibility", default_reproducibility)
        normalized.setdefault("mitigation", default_mitigation)
        # Sanity-check the four v2 fields against the schema enums so bad
        # defaults surface immediately rather than silently producing invalid
        # findings downstream.
        Finding(
            severity=normalized.get("severity", "INFO"),
            category=normalized.get("category", "uncategorized"),
            detail=normalized.get("detail", ""),
            layer=normalized["layer"],
            root_cause=normalized["root_cause"],
            reproducibility=normalized["reproducibility"],
            mitigation=normalized["mitigation"],
        )
        upgraded.append(normalized)
    return upgraded
