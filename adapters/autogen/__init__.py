# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS AutoGen Adapter v0.1.0.

Converts AutoGen Agents to MAS-TS Agent Card format for evaluation.
"""

from .adapter import AutoGenAdapter
from .evaluator import AutoGenEvaluator

__all__ = ["AutoGenAdapter", "AutoGenEvaluator"]
__version__ = "0.1.0"
