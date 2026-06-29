# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS LangChain Adapter v0.1.0.

Converts LangChain Agents to MAS-TS Agent Card format for evaluation.
"""

from .adapter import LangChainAdapter
from .evaluator import LangChainEvaluator

__all__ = ["LangChainAdapter", "LangChainEvaluator"]
__version__ = "0.1.0"
