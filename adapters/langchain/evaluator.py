# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""LangChain Agent evaluator wrapper."""

from typing import Any, Dict, List, Optional

from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
from mas_eval.harness.l1_standard import run_l1_standard


class LangChainEvaluator:
    """Evaluator for LangChain agents using MAS-TS harness."""

    def __init__(self, agent: Any, agent_config: Optional[Dict] = None):
        """Initialize evaluator with LangChain agent instance.

        Args:
            agent: LangChain Agent instance.
            agent_config: Optional agent configuration dict.
        """
        from .adapter import LangChainAdapter

        self.adapter = LangChainAdapter(agent, agent_config)
        self.card = self.adapter.to_agent_card()

    def evaluate_l0(self, tasks: Optional[List[Dict]] = None) -> Dict:
        """Run L0 Fast-Screen evaluation.

        Args:
            tasks: Optional list of task dicts for mock task stage.

        Returns:
            L0 evaluation result dict.
        """
        return run_l0_fast_screen(self.card, tasks)

    def evaluate_l1(self, golden_trajectory: Optional[List[Dict]] = None) -> Dict:
        """Run L1 Standard evaluation.

        Args:
            golden_trajectory: Optional golden trajectory for comparison.

        Returns:
            L1 evaluation result dict.
        """
        return run_l1_standard(self.card, golden_trajectory)

    def evaluate(self, level: str = "L0", **kwargs) -> Dict:
        """Run evaluation at specified level.

        Args:
            level: Evaluation level (L0, L1, L2, L3, L4).
            **kwargs: Additional arguments for the specific level.

        Returns:
            Evaluation result dict.

        Raises:
            ValueError: If level is not supported.
        """
        if level == "L0":
            return self.evaluate_l0(kwargs.get("tasks"))
        elif level == "L1":
            return self.evaluate_l1(kwargs.get("golden_trajectory"))
        else:
            raise ValueError(f"Unsupported evaluation level: {level}")

    def get_agent_card(self) -> Dict:
        """Get the generated Agent Card.

        Returns:
            Agent card dict.
        """
        return self.card
