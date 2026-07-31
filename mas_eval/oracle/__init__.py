# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — Executable Oracle Framework.

Integrates dynamic golden trajectory generation with D2 task completion scoring.
"""

from mas_eval.oracle.env import (
    check_docker,
    check_playwright,
    check_stress_ng,
    get_environment_summary,
)
from mas_eval.oracle.oracle_base import (
    Oracle,
    OracleRegistry,
    OracleTask,
    run_d2_with_oracle,
)

__all__ = [
    "Oracle",
    "OracleRegistry",
    "OracleTask",
    "run_d2_with_oracle",
    "check_docker",
    "check_playwright",
    "check_stress_ng",
    "get_environment_summary",
]
