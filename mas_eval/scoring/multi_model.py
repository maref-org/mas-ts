"""Multi-Model Comparison Matrix for MAS-TS-001 v3.0.

Runs the same evaluation across multiple model configurations and
outputs a comparison matrix showing which model × architecture
combination performs best across D2/D3 dimensions.

Usage:
    mm = MultiModelRunner(card)
    mm.add_model("claude-sonnet-4", {"provider": "anthropic", "tier": "premium"})
    mm.add_model("gpt-4o", {"provider": "openai", "tier": "premium"})
    result = mm.run()
    mm.print_matrix(result)
"""

import copy
import logging

from mas_eval.domains.d2_single_agent import run_d2
from mas_eval.domains.d3_multi_agent import run_d3
from mas_eval.oracle.oracle_base import run_d2_with_oracle

logger = logging.getLogger(__name__)


class MultiModelRunner:
    """Run multi-model evaluations across domains.

    Manages a set of model configurations, executes domain evaluations
    for each model, and aggregates results into a comparison matrix.
    """

    def __init__(self, base_card, tasks=None):
        self.base_card = base_card
        self.tasks = tasks or []
        self.models = []

    def add_model(self, model_name, config=None):
        """Add a single model configuration.

        Args:
        model_name: Model identifier (e.g. "claude-sonnet-4").
        config: Optional dict with provider, deployment, etc.
        """
        self.models.append(
            {
                "name": model_name,
                "config": config or {},
            }
        )

    def add_models(self, model_list):
        """Add multiple model configurations from a list.

        Each entry in the list may be a string (model name) or a dict
        with "name" and optional "config" keys.

        Args:
        model_list: List of model specifications.
        """
        for model in model_list:
            if isinstance(model, str):
                self.add_model(model)
            else:
                self.add_model(model["name"], model.get("config", {}))

    def _make_card(self, model_name, model_config):
        card = copy.deepcopy(self.base_card)
        card["model_backend"] = {
            "model": model_name,
            "provider": model_config.get("provider", "unknown"),
            "deployment": model_config.get("deployment", "cloud"),
            "endpoint": model_config.get(
                "endpoint", f"https://api.{model_config.get('provider', 'example')}.com"
            ),
        }
        card["model"] = model_name
        card["provider"] = model_config.get("provider", "unknown")
        if "tier" in model_config:
            if "compliance" not in card:
                card["compliance"] = {}
            card["compliance"]["tier"] = model_config["tier"]
        return card

    def run(self, domains=None):
        """Run evaluations for all registered models.

        Args:
        domains: Optional list of domain names to evaluate (default all).

        Returns:
        List of result dicts, one per model, each containing the
        domain evaluation results.
        """
        domains = domains or ["d2", "d3"]
        results = []

        for model in self.models:
            name = model["name"]
            config = model["config"]
            card = self._make_card(name, config)
            entry = {"model": name, "config": config}

            if "d2" in domains:
                d2 = run_d2(card, [])
                entry["d2"] = {
                    "score": d2["score"],
                    "subscores": d2.get("subscores", {}),
                    "model_quality": d2.get("subscores", {}).get("model_quality"),
                    "tool_coverage": d2.get("subscores", {}).get("tool_coverage"),
                    "task_completion": d2.get("subscores", {}).get("task_completion"),
                    "e2e_scenarios": d2.get("subscores", {}).get("e2e_scenarios"),
                }

            if "d3" in domains:
                d3 = run_d3(card, self.tasks)
                entry["d3"] = {
                    "score": d3["score"],
                    "subscores": d3.get("subscores", {}),
                }

            results.append(entry)

        return {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "multi-model",
            "model_count": len(self.models),
            "domains_evaluated": domains,
            "results": results,
        }

    def oracle_run(self, oracle_name, task_id=None, domains=None, mock_trajectory=None):
        """Run multi-model comparison using an oracle for golden trajectories.

        Args:
            oracle_name: Registered oracle name.
            task_id: Specific task ID (uses first task if None).
            domains: List of domains to evaluate (default ["d2"]).
            mock_trajectory: Agent trajectory data for task completion scoring.

        Returns:
            Result dict with per-model oracle-enriched D2 scores.
        """
        domains = domains or ["d2"]
        results = []

        for model in self.models:
            name = model["name"]
            config = model["config"]
            card = self._make_card(name, config)
            entry = {"model": name, "config": config}

            if "d2" in domains:
                d2 = run_d2_with_oracle(card, oracle_name, task_id, mock_trajectory)
                entry["d2"] = {
                    "score": d2["score"],
                    "subscores": d2.get("subscores", {}),
                    "model_quality": d2.get("subscores", {}).get("model_quality"),
                    "tool_coverage": d2.get("subscores", {}).get("tool_coverage"),
                    "task_completion": d2.get("subscores", {}).get("task_completion"),
                    "e2e_scenarios": d2.get("subscores", {}).get("e2e_scenarios"),
                    "oracle_score": d2.get("subscores", {}).get("oracle_score"),
                }

            results.append(entry)

        return {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "multi-model-oracle",
            "oracle_name": oracle_name,
            "model_count": len(self.models),
            "domains_evaluated": domains,
            "results": results,
        }

    @staticmethod
    def print_matrix(result):
        """Print a formatted comparison matrix of all model results.

        Args:
        result: The result list returned by run().
        """
        domains = result["domains_evaluated"]

        header = f"{'Model':<25}"
        for d in domains:
            header += f"  {d.upper():>8}"
            if d == "d2":
                for sub in ["quality", "tools", "tasks", "e2e"]:
                    header += f"  {sub:>7}"
            if d == "d3":
                for sub in ["spawn", "proto", "orch", "isol", "conf", "pers"]:
                    header += f"  {sub:>5}"
        is_oracle = result.get("mode") == "multi-model-oracle"
        title = (
            "Multi-Model Oracle Comparison"
            if is_oracle
            else "Multi-Model Comparison Matrix"
        )

        print("\n" + "=" * len(header))
        print(f"  {title}")
        if is_oracle:
            print(f"  Oracle: {result.get('oracle_name', '?')}")
        print("=" * len(header))
        print(header)
        print("-" * len(header))

        for r in result["results"]:
            row = f"{r['model']:<25}"
            for d in domains:
                data = r.get(d, {})
                score = data.get("score", 0)
                row += f"  {score:>7.1f} "
                if d == "d2":
                    subs = data.get("subscores", {})
                    row += f"  {subs.get('model_quality', 0):>6.1f} "
                    row += f"  {subs.get('tool_coverage', 0):>6.1f} "
                    row += f"  {subs.get('task_completion', 0):>6.1f} "
                    row += f"  {subs.get('e2e_scenarios', 0):>6.1f} "
                    if is_oracle:
                        row += f"  {subs.get('oracle_score', 0):>7.1f} "
                if d == "d3":
                    subs = data.get("subscores", {})
                    row += f"  {subs.get('spawn', 0):>4.0f} "
                    row += f"  {subs.get('protocol', 0):>4.0f} "
                    row += f"  {subs.get('orchestration', 0):>4.0f} "
                    row += f"  {subs.get('isolation', 0):>4.0f} "
                    row += f"  {subs.get('conflict', 0):>4.0f} "
                    row += f"  {subs.get('persistence', 0):>4.0f} "
            print(row)
        print("-" * len(header))

        if is_oracle and "d2" in domains:
            best_d2 = max(
                result["results"], key=lambda r: r.get("d2", {}).get("oracle_score", 0)
            )
            print(
                f"\nBest Oracle: {best_d2['model']} (oracle_score={best_d2['d2']['oracle_score']:.1f})"
            )
        else:
            if "d2" in domains:
                best_d2 = max(
                    result["results"], key=lambda r: r.get("d2", {}).get("score", 0)
                )
                print(f"\nBest D2: {best_d2['model']} ({best_d2['d2']['score']:.1f})")
            if "d3" in domains:
                best_d3 = max(
                    result["results"], key=lambda r: r.get("d3", {}).get("score", 0)
                )
                print(f"Best D3: {best_d3['model']} ({best_d3['d3']['score']:.1f})")
        print("=" * len(header) + "\n")
