# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 MCP core — Model Context Protocol envelope & governance validation.

Implements the cross-boundary governance contract referenced by the MAS-TS
Constitution articles enforced in CI (check-api-version.yml / check-mcp-envelope.yml
/ check-fail-mode.yml):

  * Article 15   — every MCP tool declares ``api_version``
  * Article 15-A — cross-boundary MCP messages carry ``trace_id`` / ``timestamp``
                    / ``source_agent`` for auditability
  * Article 7    — cross-boundary MCP calls declare a ``FAIL_MODE`` degradation
                    strategy

This module is the reusable validation core so the same rules verified in CI
can be exercised programmatically by the evaluation harness and by consumers.
"""

from typing import Any

from mas_eval.scoring.findings import upgrade_findings_to_v2

# JSON-RPC 2.0 baseline envelope (MCP transport).
JSONRPC_REQUIRED_FIELDS = ("jsonrpc", "id", "method")

# Governance fields enforced on every MCP message.
API_VERSION_FIELD = "api_version"

# Cross-boundary fields (agent → agent, or agent → external MCP server).
CROSS_BOUNDARY_FIELDS = ("trace_id", "timestamp", "source_agent")
CROSS_BOUNDARY_FAIL_MODE = "FAIL_MODE"

VALID_FAIL_MODES = ("closed", "open", "degraded", "manual")


def validate_mcp_envelope(
    message: dict[str, Any],
    cross_boundary: bool = False,
) -> dict[str, Any]:
    """Validate a single MCP message envelope against the governance contract.

    Args:
        message: MCP message dict (JSON-RPC 2.0 shaped).
        cross_boundary: True when the message crosses an agent/trust boundary,
            which additionally requires trace_id / timestamp / source_agent and
            a FAIL_MODE degradation strategy.

    Returns:
        Dict with ``valid`` (bool), ``missing`` (list[str]), ``findings`` (list).
    """
    findings: list[dict[str, Any]] = []
    missing: list[str] = []

    if not isinstance(message, dict):
        findings.append(
            {
                "severity": "CRITICAL",
                "category": "mcp_envelope_type",
                "detail": "MCP message must be a JSON object",
                "layer": "safety",
                "root_cause": "parameter_error",
            }
        )
        return {"valid": False, "missing": ["<message>"], "findings": findings}

    # JSON-RPC 2.0 baseline.
    for field in JSONRPC_REQUIRED_FIELDS:
        if field not in message:
            missing.append(field)
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "mcp_envelope_missing",
                    "detail": f"Missing JSON-RPC field '{field}'",
                    "layer": "safety",
                    "root_cause": "parameter_error",
                }
            )

    # Article 15 — api_version on every MCP tool/message.
    if API_VERSION_FIELD not in message:
        missing.append(API_VERSION_FIELD)
        findings.append(
            {
                "severity": "HIGH",
                "category": "mcp_api_version_missing",
                "detail": "MCP message lacks api_version (Constitution Article 15)",
                "layer": "safety",
                "root_cause": "parameter_error",
            }
        )

    # Article 15-A / Article 7 — cross-boundary extras.
    if cross_boundary:
        for field in CROSS_BOUNDARY_FIELDS:
            if field not in message:
                missing.append(field)
                findings.append(
                    {
                        "severity": "HIGH",
                        "category": "mcp_cross_boundary_missing",
                        "detail": (
                            f"Cross-boundary MCP message missing '{field}' "
                            f"(Constitution Article 15-A)"
                        ),
                        "layer": "safety",
                        "root_cause": "parameter_error",
                    }
                )
        fail_mode = message.get(CROSS_BOUNDARY_FAIL_MODE)
        if fail_mode is None:
            missing.append(CROSS_BOUNDARY_FAIL_MODE)
            findings.append(
                {
                    "severity": "CRITICAL",
                    "category": "mcp_fail_mode_missing",
                    "detail": (
                        "Cross-boundary MCP call lacks FAIL_MODE degradation "
                        f"(Constitution Article 7; valid={VALID_FAIL_MODES})"
                    ),
                    "layer": "safety",
                    "root_cause": "permission_violation",
                }
            )
        elif fail_mode not in VALID_FAIL_MODES:
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "mcp_fail_mode_invalid",
                    "detail": (
                        f"FAIL_MODE '{fail_mode}' not in valid set {VALID_FAIL_MODES}"
                    ),
                    "layer": "safety",
                    "root_cause": "parameter_error",
                }
            )

    valid = len(missing) == 0
    if valid:
        findings.append(
            {
                "severity": "INFO",
                "category": "mcp_envelope_ok",
                "detail": "MCP envelope satisfies governance contract"
                + (" (cross-boundary)" if cross_boundary else ""),
            }
        )

    findings = upgrade_findings_to_v2(findings, default_layer="safety")
    return {"valid": valid, "missing": missing, "findings": findings}


def check_mcp_compliance(card: dict[str, Any]) -> dict[str, Any]:
    """Check an Agent Card's declared MCP configuration for governance compliance.

    Verifies the MCP protocol block declares a version (Article 15) and, when MCP
    is enabled for federation, a compatible version. Returns a Gold-shaped
    component result.

    Args:
        card: Agent Card dict (v1.2 / v2.0).

    Returns:
        Dict with domain, component, score, subscores, findings.
    """
    findings: list[dict[str, Any]] = []
    mcp = (
        (card.get("federation_protocols") or {}).get("mcp")
        or card.get("endpoints", {}).get("mcp")
        or {}
    )
    enabled = bool(mcp.get("enabled", False)) if isinstance(mcp, dict) else False

    subscores: dict[str, float] = {}
    if not enabled:
        subscores["mcp_declared"] = 0.0
        findings.append(
            {
                "severity": "INFO",
                "category": "mcp_not_enabled",
                "detail": "Agent card does not enable MCP — governance checks N/A",
            }
        )
    else:
        version = mcp.get("version", "")
        if version:
            subscores["mcp_declared"] = 1.0
            if version >= "2024-10-01":
                findings.append(
                    {
                        "severity": "INFO",
                        "category": "mcp_version_ok",
                        "detail": f"MCP v{version} compatible with federation topology",
                    }
                )
            else:
                findings.append(
                    {
                        "severity": "WARNING",
                        "category": "mcp_version_outdated",
                        "detail": f"MCP v{version} outdated — federation topology risk",
                    }
                )
        else:
            subscores["mcp_declared"] = 0.0
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "mcp_version_missing",
                    "detail": "MCP enabled but no version declared (Constitution Article 15)",
                    "layer": "safety",
                    "root_cause": "parameter_error",
                }
            )

    score = round(sum(subscores.values()) / max(len(subscores), 1) * 100, 1)
    findings = upgrade_findings_to_v2(findings, default_layer="safety")
    return {
        "domain": "D3",
        "component": "mcp_compliance",
        "name": "MCP Core Governance Compliance",
        "score": score,
        "subscores": subscores,
        "findings": findings,
    }
