# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 MCP core package."""

from mas_eval.mcp.envelope import (
    VALID_FAIL_MODES,
    CROSS_BOUNDARY_FIELDS,
    CROSS_BOUNDARY_FAIL_MODE,
    API_VERSION_FIELD,
    JSONRPC_REQUIRED_FIELDS,
    check_mcp_compliance,
    validate_mcp_envelope,
)

__all__ = [
    "VALID_FAIL_MODES",
    "CROSS_BOUNDARY_FIELDS",
    "CROSS_BOUNDARY_FAIL_MODE",
    "API_VERSION_FIELD",
    "JSONRPC_REQUIRED_FIELDS",
    "check_mcp_compliance",
    "validate_mcp_envelope",
]
