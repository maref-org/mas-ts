# Loop Engineering Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform MAS-TS from a linear single-pass evaluator into an iterative convergence engine — closing the "evaluate → analyze → refine → re-evaluate" loop with adaptive level gating and real Verifier governance.

**Architecture:** Add a `ConvergenceLoop` engine at the harness layer that wraps existing domain runners with iteration/convergence detection. Modify `mas_full_run.py` for conditional level escalation. Replace D5 `_mock_score()` with pluggable verifiers. Extend L4 with multi-epoch lifecycle.

**Tech Stack:** Python 3.12+, existing harness/domains/scoring structure, pytest for TDD.

**Status:** ✅ Engineered (P0), 🚧 In Progress (P1), 📝 Planned (P2)

---

### Task 1: ConvergenceLoop Engine

**Files:**
- Create: `mas_eval/harness/loop_engine.py`
- Test: `tests/test_loop_engine.py`

**Overview:** Reusable iterative evaluation loop that wraps any harness-level runner function with convergence detection, iteration tracking, and graceful termination.

```
ConvergenceLoop.run(card, runner_fn, max_iterations=5, convergence_delta=0.5)
  → [{iteration, score, findings, ...}, ...]  # history
  → {"final_score", "iterations", "converged", "score_trajectory", "findings"}
```

Convergence criteria (any triggers stop):
1. **Score delta**: last 3 iterations score change < `convergence_delta` (converged)
2. **Max iterations**: reached `max_iterations` (stopped)
3. **Timeout**: wall clock > `timeout_seconds` (timed out)
4. **Regression**: score drops by > `regression_threshold` between consecutive iterations (diverged)

**Step 1: Write the failing test — `ConvergenceLoop` init**

```python
"""Tests for Loop Engineering — ConvergenceLoop, Adaptive Escalation, Verifier."""
import pytest
from mas_eval.harness.loop_engine import ConvergenceLoop


SAMPLE_CARD = {
    "card_version": "1.2",
    "agent_id": "urn:agent:test:loop-001",
    "name": "LoopTest",
    "version": "1.0.0",
    "compliance": {"data_residency": "US", "data_classification": "internal"},
    "constitution": {"health_state": "HEALTHY", "heartbeat_interval_seconds": 30},
    "model_backend": {"provider": "test", "model": "claude-sonnet-4"},
    "capabilities": [{"skill_id": "bash", "description": "run commands", "input_schema": {}, "output_schema": {}, "examples": ["ls"], "business_rule_version": "2026-05-01"}],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
}


class TestConvergenceLoop:
    def test_init_defaults(self):
        loop = ConvergenceLoop()
        assert loop.max_iterations == 5
        assert loop.convergence_delta == 0.5
        assert loop.regression_threshold == -20.0
        assert loop.history == []

    def test_init_custom(self):
        loop = ConvergenceLoop(max_iterations=10, convergence_delta=0.2, regression_threshold=-10.0)
        assert loop.max_iterations == 10
        assert loop.convergence_delta == 0.2
        assert loop.regression_threshold == -10.0
```

Run: `pytest tests/test_loop_engine.py::TestConvergenceLoop::test_init_defaults -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'mas_eval.harness.loop_engine'"

**Step 2: Write minimal ConvergenceLoop class**

```python
class ConvergenceLoop:
    """Iterative evaluation loop with convergence detection.

    Wraps a harness runner and re-runs it until convergence criteria are met.
    Tracks full iteration history for analysis.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_delta: float = 0.5,
        regression_threshold: float = -20.0,
        timeout_seconds: float = 3600,
    ):
        self.max_iterations = max_iterations
        self.convergence_delta = convergence_delta
        self.regression_threshold = regression_threshold
        self.timeout_seconds = timeout_seconds
        self.history: list[dict] = []
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_loop_engine.py::TestConvergenceLoop::test_init_defaults -v`
Expected: PASS

**Step 4: Write failing test — `run` method returns history + summary**

```python
    def test_run_returns_summary(self):
        def stub_runner(card, **kw):
            return {"score": 75.0, "findings": [], "domain_scores": {"d1": 80.0}}

        loop = ConvergenceLoop(max_iterations=3, convergence_delta=5.0)
        result = loop.run(SAMPLE_CARD, stub_runner)
        assert "final_score" in result
        assert "iterations" in result
        assert "converged" in result
        assert "score_trajectory" in result
        assert "findings" in result
        assert result["iterations"] >= 1

    def test_run_converges_early(self):
        """Score stabilizes → stops before max_iterations."""
        called = [0]

        def converging_runner(card, **kw):
            called[0] += 1
            return {"score": 80.0, "findings": [], "domain_scores": {"d1": 80.0}}

        loop = ConvergenceLoop(max_iterations=10, convergence_delta=1.0)
        result = loop.run(SAMPLE_CARD, converging_runner)
        assert result["converged"] is True
        assert result["iterations"] < 10
        assert called[0] >= 2

    def test_run_stops_at_max(self):
        """Never converges → stops at max_iterations."""
        scores = iter([70.0, 72.0, 74.0, 76.0, 78.0, 80.0])

        def climbing_runner(card, **kw):
            return {"score": next(scores), "findings": [], "domain_scores": {}}

        loop = ConvergenceLoop(max_iterations=3, convergence_delta=0.1)
        result = loop.run(SAMPLE_CARD, climbing_runner)
        assert result["converged"] is False
        assert result["iterations"] == 3
        assert result["stop_reason"] == "max_iterations"

    def test_run_detects_regression(self):
        """Score drops by > threshold → diverged, stops early."""
        scores = iter([80.0, 75.0, 50.0])

        def regressing_runner(card, **kw):
            return {"score": next(scores), "findings": [{"severity": "HIGH", "category": "regression", "detail": "score dropped"}], "domain_scores": {}}

        loop = ConvergenceLoop(max_iterations=5, regression_threshold=-10.0)
        result = loop.run(SAMPLE_CARD, regressing_runner)
        assert result["converged"] is False
        assert result["stop_reason"] == "regression"
        assert result["iterations"] == 3
```

**Step 5: Implement `ConvergenceLoop.run`**

```python
import time
import logging

logger = logging.getLogger(__name__)


class ConvergenceLoop:
    """Iterative evaluation loop with convergence detection."""

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_delta: float = 0.5,
        regression_threshold: float = -20.0,
        timeout_seconds: float = 3600,
    ):
        self.max_iterations = max_iterations
        self.convergence_delta = convergence_delta
        self.regression_threshold = regression_threshold
        self.timeout_seconds = timeout_seconds
        self.history: list[dict] = []

    def run(self, card, runner_fn, **runner_kwargs):
        """Run evaluation in a convergence loop.

        Args:
            card: Agent card dict.
            runner_fn: Callable that accepts (card, **runner_kwargs) and returns
                       dict with at minimum {"score": float, "findings": list}.
            **runner_kwargs: Additional kwargs forwarded to runner_fn.

        Returns:
            Dict with keys: final_score, iterations, converged, stop_reason,
            score_trajectory, history, findings.
        """
        self.history = []
        start_time = time.time()
        stop_reason = "max_iterations"

        for iteration in range(1, self.max_iterations + 1):
            if time.time() - start_time > self.timeout_seconds:
                stop_reason = "timeout"
                logger.warning("ConvergenceLoop timed out after %d iterations", iteration - 1)
                break

            result = runner_fn(card, **runner_kwargs)
            score = result.get("score", 0.0)
            entry = {
                "iteration": iteration,
                "score": score,
                "findings": result.get("findings", []),
                "domain_scores": result.get("domain_scores", {}),
                "elapsed_seconds": round(time.time() - start_time, 1),
            }
            self.history.append(entry)
            logger.info("Iteration %d: score=%.1f", iteration, score)

            if iteration >= 3:
                prev_scores = [h["score"] for h in self.history[-3:]]
                deltas = [prev_scores[i] - prev_scores[i - 1] for i in range(1, len(prev_scores))]

                # Check regression
                if any(d < self.regression_threshold for d in deltas):
                    stop_reason = "regression"
                    logger.warning("Score regression detected at iteration %d", iteration)
                    break

                # Check convergence: all recent deltas below threshold
                if all(abs(d) < self.convergence_delta for d in deltas):
                    stop_reason = "converged"
                    logger.info("Converged at iteration %d (Δ=%.2f)", iteration, max(abs(d) for d in deltas))
                    break

        trajectory = [h["score"] for h in self.history]
        all_findings = []
        for h in self.history:
            all_findings.extend(h.get("findings", []))

        return {
            "final_score": round(sum(trajectory) / len(trajectory), 1) if trajectory else 0.0,
            "iterations": len(self.history),
            "converged": stop_reason == "converged",
            "stop_reason": stop_reason,
            "score_trajectory": trajectory,
            "history": self.history,
            "findings": all_findings,
        }
```

**Step 6: Run tests to verify they pass**

Run: `pytest tests/test_loop_engine.py::TestConvergenceLoop -v`
Expected: All 5 tests PASS

**Step 7: Add test — wraps real L3 runner**

```python
    def test_wraps_l3_runner(self):
        from mas_eval.harness.l3_comprehensive import run_l3_comprehensive
        loop = ConvergenceLoop(max_iterations=2, convergence_delta=50.0)
        result = loop.run(SAMPLE_CARD, run_l3_comprehensive)
        assert result["iterations"] == 2
        assert 0 <= result["final_score"] <= 100
        assert result["stop_reason"] == "converged"  # delta is huge, converges immediately
```

**Step 8: Verify L3 wrapping test passes**

Run: `pytest tests/test_loop_engine.py::TestConvergenceLoop::test_wraps_l3_runner -v`
Expected: PASS

**Step 9: Commit**

```bash
git add mas_eval/harness/loop_engine.py tests/test_loop_engine.py
git commit -m "feat: ConvergenceLoop engine — iterative evaluation with convergence detection"
```

---

### Task 2: Adaptive Level Escalation in mas_full_run.py

**Files:**
- Modify: `mas_full_run.py:442-468` (main loop)
- Modify: `mas_full_run.py:384-420` (argparse)
- Test: `tests/test_mas_full_run.py`

**Overview:** Add `--mode escalate` flag that runs levels conditionally: L0 PASS → L1, L1 PASS → L2, etc. Add `--converge` flag that wraps each level in ConvergenceLoop. Add `--convergence-delta` and `--max-iterations` CLI args.

**Step 1: Write failing test — escalate mode skips on fail**

```python
"""In tests/test_mas_full_run.py, add to existing TestMain class."""
from mas_full_run import LEVEL_RUNNERS, ESCALATION_THRESHOLDS

class TestAdaptiveEscalation:
    def test_escalation_thresholds_defined(self):
        assert "L0" in ESCALATION_THRESHOLDS
        assert "L1" in ESCALATION_THRESHOLDS
        assert "L2" in ESCALATION_THRESHOLDS
        assert "L3" in ESCALATION_THRESHOLDS
        assert ESCALATION_THRESHOLDS["L0"] >= 60  # L0 must pass at 60+
        assert ESCALATION_THRESHOLDS["L3"] >= 50  # L3 can escalate at 50+
```

Run: `pytest tests/test_mas_full_run.py::TestAdaptiveEscalation -v`
Expected: FAIL with "AttributeError: module 'mas_full_run' has no attribute 'ESCALATION_THRESHOLDS'"

**Step 2: Add ESCALATION_THRESHOLDS to mas_full_run.py**

After `LEVEL_RUNNERS` dict (line 63):

```python
# Minimum score per level to escalate to the next level
ESCALATION_THRESHOLDS = {
    "L0": 60,
    "L1": 60,
    "L2": 50,
    "L3": 50,
}
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_mas_full_run.py::TestAdaptiveEscalation -v`
Expected: PASS

**Step 4: Add escalation mode test**

```python
    def test_escalate_skips_on_low_score(self):
        """If L0 score < threshold, L1-L4 are skipped."""
        from mas_eval.harness.l0_fast_screen import run_l0_fast_screen
        from mas_eval.harness.l1_standard import run_l1_standard
        card = {"card_version": "1.2", "agent_id": "test", "name": "T", "version": "1.0"}
        # L0 will pass with sample card; we need to simulate
        # This tests the logic function directly
        from mas_full_run import _select_levels_escalate
        results = {"L0": {"score": 55.0}}
        selected = _select_levels_escalate(results)
        assert selected == []  # L0 below threshold, stop

    def test_escalate_proceeds_on_pass(self):
        from mas_full_run import _select_levels_escalate
        results = {"L0": {"score": 85.0}}
        selected = _select_levels_escalate(results)
        assert selected == ["L1"]

    def test_escalate_full_chain(self):
        from mas_full_run import _select_levels_escalate
        results = {"L0": {"score": 85.0}, "L1": {"score": 80.0}, "L2": {"score": 75.0}, "L3": {"score": 70.0}}
        selected = _select_levels_escalate(results)
        assert selected == ["L1", "L2", "L3", "L4"]
```

**Step 5: Implement escalation helper**

```python
def _select_levels_escalate(completed_results):
    """Given completed levels and their scores, return which levels to run next.

    Args:
        completed_results: dict mapping level → {"score": float} for already-run levels.

    Returns:
        List of level strings to run next.
    """
    ordered = ["L0", "L1", "L2", "L3", "L4"]
    next_levels = []
    for i, level in enumerate(ordered):
        if level in completed_results:
            score = completed_results[level].get("score", 0)
            if score < ESCALATION_THRESHOLDS.get(level, 50):
                return next_levels  # Gate fails, stop
        else:
            # Previous level must exist and pass
            if i == 0:
                continue  # L0 hasn't been run yet — this is the first to run
            prev = ordered[i - 1]
            if prev not in completed_results:
                return next_levels
            prev_score = completed_results[prev].get("score", 0)
            if prev_score >= ESCALATION_THRESHOLDS.get(prev, 50):
                next_levels.append(level)
            else:
                return next_levels
    return next_levels
```

**Step 6: Modify CLI args — add `--mode` and `--converge`**

```python
    parser.add_argument(
        "--mode",
        default="full",
        choices=["full", "escalate"],
        help="Execution mode: 'full' runs all selected levels, 'escalate' runs levels conditionally (default: full)",
    )
    parser.add_argument(
        "--converge",
        action="store_true",
        help="Enable convergence loop: runs each level up to --max-iterations times until score stabilizes",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum iterations per level when --converge is set (default: 5)",
    )
    parser.add_argument(
        "--convergence-delta",
        type=float,
        default=0.5,
        help="Score delta threshold for convergence (default: 0.5)",
    )
```

**Step 7: Modify main loop for escalate + converge**

Replace lines 442-459 with:

```python
    level_results = []
    completed_scores = {}

    selected_levels = (
        ["L0", "L1", "L2", "L3", "L4"] if args.level == "all" else [args.level]
    )

    if args.mode == "escalate":
        # Start with L0 only; _select_levels_escalate will gate the rest
        selected_levels = ["L0"]

    while selected_levels:
        level = selected_levels.pop(0)
        runner = LEVEL_RUNNERS[level]

        if args.converge and level != "L0":
            from mas_eval.harness.loop_engine import ConvergenceLoop

            loop = ConvergenceLoop(
                max_iterations=args.max_iterations,
                convergence_delta=args.convergence_delta,
            )

            def make_runner(level, runner):
                def wrapped(card, **kw):
                    if level == "L4":
                        return runner()
                    return runner(card, kw.get("tasks"))
                return wrapped

            conv_result = loop.run(card, make_runner(level, runner))
            result = {
                "level": level,
                "score": conv_result["final_score"],
                "convergence": conv_result,
                "findings": conv_result["findings"],
                "iterations": conv_result["iterations"],
                "converged": conv_result["converged"],
            }
        else:
            logger.info("[%s] Running %s...", level, runner.__name__)
            t0 = time.perf_counter()

            if level == "L4":
                result = runner()
            elif level == "L0":
                result = runner(card, tasks)
            else:
                result = runner(card, tasks)

            result["duration_ms"] = int((time.perf_counter() - t0) * 1000)

        result.setdefault("score", result.get("score", 0) or 0)
        level_results.append(result)
        completed_scores[level] = {"score": result.get("score", 0)}

        status = result.get("status") or (
            "PASS" if (result.get("score") or 0) >= 70 else "FAIL"
        )
        logger.info("  -> %s (score=%.1f)", status, result.get("score", 0))

        # If escalate mode, determine next levels after this one
        if args.mode == "escalate":
            next_levels = _select_levels_escalate(completed_scores)
            # Only add levels we haven't run yet
            for nl in next_levels:
                if nl not in [r["level"] for r in level_results]:
                    selected_levels.append(nl)
            # Deduplicate
            selected_levels = list(dict.fromkeys(selected_levels))
```

**Step 8: Run existing tests to verify no regression**

Run: `pytest tests/test_mas_full_run.py -v`
Expected: All existing tests PASS

**Step 9: Commit**

```bash
git add mas_full_run.py tests/test_mas_full_run.py
git commit -m "feat: adaptive level escalation + convergence loop CLI flags"
```

---

### Task 3: D5 Verifier Governance — Plugable Verifier Registry

**Files:**
- Modify: `mas_eval/domains/d5_robustness.py` (ConvergenceVerifier, `_score_convergence`)
- Create: `mas_eval/scoring/verifier.py`
- Test: `tests/test_verifier.py`

**Overview:** Replace `_mock_embedding()` in `ConvergenceVerifier` with a pluggable `VerifierRegistry` supporting multiple evaluation backends (LLM-as-judge, oracle, mock). Add cross-validation with consensus scoring.

**Step 1: Write failing test — VerifierRegistry**

```python
class TestVerifierRegistry:
    def test_register_verifier(self):
        from mas_eval.scoring.verifier import VerifierRegistry, Verifier
        registry = VerifierRegistry()
        v = Verifier(name="test-judge")
        registry.register(v)
        assert "test-judge" in registry.list()

    def test_evaluate_all(self):
        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=85))
        registry.register(MockVerifier(name="v2", score=90))
        results = registry.evaluate_all("task_1", ["response_a"])
        assert len(results) == 2
        assert all("score" in r for r in results)

    def test_consensus_score(self):
        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=85))
        registry.register(MockVerifier(name="v2", score=90))
        result = registry.consensus_evaluate("task_1", ["response_a"])
        assert "consensus_score" in result
        assert "individual_scores" in result
        assert "agreement" in result
```

Run: `pytest tests/test_verifier.py -v`
Expected: FAIL

**Step 2: Implement Verifier base + Registry**

```python
"""Pluggable verifier governance for MAS-TS-001 D5 + Loop Engineering.

Provides a registry of Verifier instances that can cross-validate evaluation
results, replacing mock-only scoring with real LLM-as-judge or oracle backends.
"""

import abc
import logging

logger = logging.getLogger(__name__)


class Verifier(abc.ABC):
    """Abstract base for an evaluation verifier."""

    def __init__(self, name: str):
        self.name = name
        self._eval_count = 0
        self._accuracy: float | None = None

    @abc.abstractmethod
    def evaluate(self, task_id: str, responses: list[str]) -> dict:
        """Evaluate response quality for a given task.

        Returns:
            Dict with at least {"score": float (0-100)}.
        """
        ...

    def record_accuracy(self, accuracy: float) -> None:
        self._accuracy = accuracy

    @property
    def eval_count(self) -> int:
        return self._eval_count

    @property
    def accuracy(self) -> float | None:
        return self._accuracy


class MockVerifier(Verifier):
    """Deterministic mock verifier for testing."""

    def __init__(self, name: str, score: float = 85.0):
        super().__init__(name)
        self._fixed_score = score

    def evaluate(self, task_id: str, responses: list[str]) -> dict:
        self._eval_count += 1
        return {"verifier": self.name, "task_id": task_id, "score": self._fixed_score, "response_count": len(responses)}


class VerifierRegistry:
    """Registry of verifiers for cross-validation."""

    def __init__(self):
        self._verifiers: dict[str, Verifier] = {}

    def register(self, verifier: Verifier) -> None:
        self._verifiers[verifier.name] = verifier
        logger.info("Registered verifier: %s", verifier.name)

    def unregister(self, name: str) -> None:
        self._verifiers.pop(name, None)

    def list(self) -> list[str]:
        return list(self._verifiers.keys())

    def get(self, name: str) -> Verifier | None:
        return self._verifiers.get(name)

    def evaluate_all(self, task_id: str, responses: list[str]) -> list[dict]:
        results = []
        for v in self._verifiers.values():
            try:
                r = v.evaluate(task_id, responses)
                results.append(r)
            except Exception as e:
                logger.error("Verifier %s failed: %s", v.name, e)
                results.append({"verifier": v.name, "task_id": task_id, "score": 0.0, "error": str(e)})
        return results

    def consensus_evaluate(self, task_id: str, responses: list[str]) -> dict:
        results = self.evaluate_all(task_id, responses)
        scores = [r["score"] for r in results if "error" not in r]

        if not scores:
            return {"consensus_score": 0.0, "individual_scores": results, "agreement": 0.0, "verifier_count": 0}

        avg = sum(scores) / len(scores)
        agreements = [s for s in scores if abs(s - avg) <= 15.0]
        agreement_pct = len(agreements) / len(scores) if scores else 0.0

        return {
            "consensus_score": round(avg, 1),
            "individual_scores": results,
            "agreement": round(agreement_pct, 2),
            "verifier_count": len(scores),
        }
```

**Step 3: Run tests — they should pass**

Run: `pytest tests/test_verifier.py -v`
Expected: All 3 PASS

**Step 4: Integrate VerifierRegistry into ConvergenceVerifier**

In `d5_robustness.py`, modify `ConvergenceVerifier` to optionally use a `VerifierRegistry`:

Add method:
```python
    def set_verifier_registry(self, registry):
        """Set a VerifierRegistry for cross-validated evaluation."""
        self._verifier_registry = registry
```

Modify `score_c1_consistency` and `score_c2_self_consistency` to use verifier scores when available:
```python
    def score_c1_consistency(self, task_id=None):
        if self._verifier_registry and task_id:
            responses = [r["text"] for r in self.responses.get(task_id, [])]
            if len(responses) >= 2:
                cons = self._verifier_registry.consensus_evaluate(task_id, responses)
                return round(cons["consensus_score"] / 100.0, 2)  # normalize to 0-1
        # Fallback to existing embedding-based scoring
        ...
```

**Step 5: Update `run_d5` to accept optional verifier registry**

Modify `run_d5` signature:
```python
def run_d5(ce=None, dd=None, card=None, seed=42, verifier_registry=None):
```

And pass it to `ConvergenceVerifier`:
```python
cv = ConvergenceVerifier()
if verifier_registry:
    cv.set_verifier_registry(verifier_registry)
```

**Step 6: Add test for verifier-integrated D5**

```python
    def test_run_d5_with_verifier_registry(self):
        from mas_eval.scoring.verifier import VerifierRegistry, MockVerifier
        from mas_eval.domains.d5_robustness import run_d5

        registry = VerifierRegistry()
        registry.register(MockVerifier(name="v1", score=88.0))
        registry.register(MockVerifier(name="v2", score=92.0))

        result = run_d5(verifier_registry=registry)
        assert result["domain"] == "D5"
        assert 0 <= result["score"] <= 100
```

**Step 7: Run D5 tests**

Run: `pytest tests/test_d5_robustness.py -v`
Expected: All existing + new tests PASS

**Step 8: Commit**

```bash
git add mas_eval/scoring/verifier.py mas_eval/domains/d5_robustness.py tests/test_verifier.py
git commit -m "feat: VerifierRegistry — pluggable cross-validation for D5 scoring"
```

---

### Task 4: L4 Evolution — Multi-Epoch Lifecycle

**Files:**
- Modify: `mas_eval/harness/l4_evolution.py`
- Create: `mas_eval/harness/epoch_state.py`
- Test: `tests/test_l4_evolution.py` (may need to extend existing)

**Overview:** Transform L4 from a single `run_d5()` call into a real multi-epoch lifecycle. Tracks epoch state, detects improvement/regression across epochs, and produces a trend report.

**Step 1: Write failing test — EpochState + multi-epoch run**

```python
class TestEpochState:
    def test_init(self):
        from mas_eval.harness.epoch_state import EpochState
        state = EpochState()
        assert state.epoch == 0
        assert state.history == []

    def test_record_epoch(self):
        state = EpochState()
        state.record(epoch=1, score=75.0, findings=[], summary="test")
        assert len(state.history) == 1
        assert state.history[0]["score"] == 75.0

    def test_trend_improving(self):
        state = EpochState()
        state.record(epoch=1, score=70.0, findings=[], summary="")
        state.record(epoch=2, score=80.0, findings=[], summary="")
        state.record(epoch=3, score=85.0, findings=[], summary="")
        assert state.trend() == "improving"

    def test_trend_regressing(self):
        state = EpochState()
        state.record(epoch=1, score=85.0, findings=[], summary="")
        state.record(epoch=2, score=75.0, findings=[], summary="")
        state.record(epoch=3, score=65.0, findings=[], summary="")
        assert state.trend() == "regressing"

    def test_trend_stable(self):
        state = EpochState()
        state.record(epoch=1, score=80.0, findings=[], summary="")
        state.record(epoch=2, score=81.0, findings=[], summary="")
        state.record(epoch=3, score=80.5, findings=[], summary="")
        assert state.trend() == "stable"

    def test_epoch_improvement_pct(self):
        state = EpochState()
        state.record(epoch=1, score=60.0, findings=[], summary="")
        state.record(epoch=2, score=80.0, findings=[], summary="")
        pct = state.improvement_pct()
        assert pct == 33.3  # (80-60)/60 * 100
```

Run: `pytest tests/test_l4_evolution.py -v`
Expected: FAIL

**Step 2: Implement EpochState**

```python
"""Epoch state tracking for L4 Evolution multi-epoch lifecycle."""

import logging

logger = logging.getLogger(__name__)


class EpochState:
    """Tracks epoch-level state across L4 multi-epoch runs.

    Records per-epoch scores, findings, and computes trends.
    """

    def __init__(self):
        self.epoch = 0
        self.history: list[dict] = []

    def record(self, epoch: int, score: float, findings: list, summary: str = ""):
        self.history.append({
            "epoch": epoch,
            "score": score,
            "findings": findings,
            "summary": summary,
        })
        self.epoch = epoch
        logger.info("Epoch %d: score=%.1f, %d findings", epoch, score, len(findings))

    def trend(self) -> str:
        """Determine trend: 'improving', 'regressing', or 'stable'."""
        if len(self.history) < 2:
            return "stable"
        recent = self.history[-3:] if len(self.history) >= 3 else self.history
        scores = [h["score"] for h in recent]
        diffs = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff > 2.0:
            return "improving"
        elif avg_diff < -2.0:
            return "regressing"
        return "stable"

    def improvement_pct(self) -> float:
        """Percentage improvement from first to last epoch."""
        if len(self.history) < 2:
            return 0.0
        first = self.history[0]["score"]
        last = self.history[-1]["score"]
        if first == 0:
            return 100.0 if last > 0 else 0.0
        return round((last - first) / first * 100, 1)

    @property
    def max_score(self) -> float:
        if not self.history:
            return 0.0
        return max(h["score"] for h in self.history)

    @property
    def min_score(self) -> float:
        if not self.history:
            return 0.0
        return min(h["score"] for h in self.history)

    @property
    def avg_score(self) -> float:
        if not self.history:
            return 0.0
        return sum(h["score"] for h in self.history) / len(self.history)

    def clear(self):
        self.history.clear()
        self.epoch = 0
```

**Step 3: Run tests to verify**

Run: `pytest tests/test_l4_evolution.py -v`
Expected: All PASS

**Step 4: Rewrite `run_l4_evolution` for multi-epoch**

```python
def run_l4_evolution(
    card=None,
    max_epochs=3,
    convergence_delta=2.0,
    epoch_state=None,
    verifier_registry=None,
):
    """Run L4 Evolution evaluation with multi-epoch lifecycle.

    Runs D5 multiple epochs, tracking score trajectory and convergence.
    Each epoch injects different chaos seeds for statistical robustness.

    Args:
        card: Optional agent card dict.
        max_epochs: Maximum number of epochs (default 3).
        convergence_delta: Score stability threshold (default 2.0).
        epoch_state: Optional EpochState for cross-session persistence.
        verifier_registry: Optional VerifierRegistry for cross-validation.

    Returns:
        Dict with keys: level, name, epochs, score, grade, verdict,
        domain_scores, domains, findings, epoch_history, trend.
    """
    from mas_eval.domains.d5_robustness import run_d5

    start = time.time()
    state = epoch_state or EpochState()
    seeds = [42, 137, 2048, 9999, 77777]

    all_findings = []
    epoch_results = []

    for epoch in range(1, max_epochs + 1):
        seed = seeds[(epoch - 1) % len(seeds)]
        d5 = run_d5(card=card, seed=seed, verifier_registry=verifier_registry)
        score = d5["score"]
        findings = d5.get("findings", [])

        state.record(
            epoch=epoch,
            score=score,
            findings=findings,
            summary=f"seed={seed}, chaos_score={d5['subscores'].get('chaos_engineering', 0):.1f}",
        )

        epoch_results.append({
            "epoch": epoch,
            "seed": seed,
            "score": score,
            "subscores": d5.get("subscores", {}),
            "findings_count": len(findings),
        })
        all_findings.extend(findings)

        # Early convergence check
        if epoch >= 3:
            recent = [h["score"] for h in state.history[-3:]]
            if max(recent) - min(recent) < convergence_delta:
                logger.info("L4 converged at epoch %d (Δ=%.2f)", epoch, max(recent) - min(recent))
                break

    trend = state.trend()
    improvement = state.improvement_pct()
    final_score = state.avg_score if trend == "stable" else state.max_score

    d5_score = score_domain(final_score, all_findings)

    score_value = d5_score if isinstance(d5_score, (int, float)) else d5_score

    return {
        "level": "L4",
        "name": "Evolution",
        "elapsed_seconds": round(time.time() - start, 1),
        "score": score_value,
        "grade": score_to_grade(score_value),
        "domain_scores": {"d5": score_value},
        "domains": {
            "d5_detail": {
                "epochs": epoch_results,
                "trend": trend,
                "improvement_pct": improvement,
            }
        },
        "findings": all_findings,
        "epoch_history": epoch_results,
        "epoch_count": len(epoch_results),
        "trend": trend,
        "improvement_pct": improvement,
    }
```

**Step 5: Update test for L4 evolution**

```python
class TestRunL4Evolution:
    def test_returns_dict(self):
        r = run_l4_evolution()
        assert isinstance(r, dict)

    def test_has_level(self):
        r = run_l4_evolution()
        assert r["level"] == "L4"

    def test_has_d5_score(self):
        r = run_l4_evolution()
        assert "d5" in r["domain_scores"]

    def test_score_in_range(self):
        r = run_l4_evolution()
        assert 0 <= r["score"] <= 100

    def test_multi_epoch(self):
        r = run_l4_evolution(max_epochs=3)
        assert r["epoch_count"] >= 2
        assert r["trend"] in ("improving", "regressing", "stable")
        assert isinstance(r["improvement_pct"], (int, float))

    def test_epoch_history_present(self):
        r = run_l4_evolution(max_epochs=2)
        assert len(r["epoch_history"]) >= 1
        for e in r["epoch_history"]:
            assert "epoch" in e
            assert "score" in e
            assert "seed" in e

    def test_early_convergence(self):
        r = run_l4_evolution(max_epochs=5, convergence_delta=50.0)
        # With huge delta, should converge quickly
        assert r["epoch_count"] == 3  # min 3 for convergence check
```

**Step 6: Run all L4 tests**

Run: `pytest tests/test_harness.py::TestRunL4Evolution -v`
Expected: All tests PASS (existing + new shape)

Run: `pytest tests/test_l4_evolution.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add mas_eval/harness/epoch_state.py mas_eval/harness/l4_evolution.py tests/test_l4_evolution.py
git commit -m "feat: L4 multi-epoch lifecycle — EpochState, trend detection, early convergence"
```

---

### Task 5: Resource Governance — TokenBudget + Circuit Breaker Integration

**Files:**
- Create: `mas_eval/harness/resource_governor.py`
- Modify: `mas_eval/harness/loop_engine.py` (integrate budget checks)
- Test: `tests/test_resource_governor.py`

**Overview:** Add `TokenBudget` and `ResourceGovernor` classes that set hard limits on evaluation resources. Integrate with D4's `CircuitBreaker` pattern. Graceful degradation on exhaustion.

**Step 1: Write failing tests**

```python
class TestTokenBudget:
    def test_init(self):
        from mas_eval.harness.resource_governor import TokenBudget
        budget = TokenBudget(max_tokens=100000, max_calls=500, max_elapsed=3600)
        assert budget.remaining_tokens == 100000
        assert budget.remaining_calls == 500

    def test_consume_tokens(self):
        budget = TokenBudget(max_tokens=1000)
        budget.consume(tokens=300)
        assert budget.remaining_tokens == 700

    def test_exceeded(self):
        budget = TokenBudget(max_tokens=100)
        budget.consume(tokens=101)
        assert budget.exceeded()

    def test_exceeded_calls(self):
        budget = TokenBudget(max_calls=3)
        budget.consume()
        budget.consume()
        budget.consume()
        assert budget.exceeded() is False
        budget.consume()
        assert budget.exceeded()

    def test_exceeded_elapsed(self):
        import time
        budget = TokenBudget(max_elapsed=0.01)
        time.sleep(0.02)
        assert budget.exceeded()
```

**Step 2: Implement TokenBudget**

```python
"""Resource governance for MAS-TS evaluation loops.

Provides token budgets, call limits, and time-based circuit breaking
for the ConvergenceLoop and harness runners.
"""

import logging
import time

logger = logging.getLogger(__name__)


class TokenBudget:
    """Hard resource limits for evaluation execution.

    Tracks token consumption, API call count, and elapsed time.
    When any limit is exceeded, the budget is 'exhausted'.
    """

    def __init__(
        self,
        max_tokens: float = float("inf"),
        max_calls: int = 10_000,
        max_elapsed: float = float("inf"),
    ):
        self.max_tokens = max_tokens
        self.max_calls = max_calls
        self.max_elapsed = max_elapsed
        self._tokens = 0.0
        self._calls = 0
        self._start = time.time()

    @property
    def remaining_tokens(self) -> float:
        return max(0, self.max_tokens - self._tokens)

    @property
    def remaining_calls(self) -> int:
        return max(0, self.max_calls - self._calls)

    @property
    def remaining_elapsed(self) -> float:
        return max(0, self.max_elapsed - (time.time() - self._start))

    def consume(self, tokens: float = 0, calls: int = 1) -> None:
        self._tokens += tokens
        self._calls += calls

    def exceeded(self) -> bool:
        if self._tokens >= self.max_tokens:
            return True
        if self._calls >= self.max_calls:
            return True
        if time.time() - self._start >= self.max_elapsed:
            return True
        return False

    def reset(self) -> None:
        self._tokens = 0.0
        self._calls = 0
        self._start = time.time()


class ResourceGovernor:
    """Manages TokenBudget and circuit breaker for evaluation lifecycle.

    Combines soft (budget) and hard (circuit breaker) limits.
    """

    def __init__(self, budget: TokenBudget | None = None):
        from mas_eval.domains.d4_governance_security import CircuitBreaker
        self.budget = budget or TokenBudget()
        self.circuit_breaker = CircuitBreaker()
        self._tripped = False

    def check(self) -> bool:
        """Check if execution should continue.

        Returns True if OK, False if resource-exhausted or circuit open.
        """
        if self._tripped:
            return False
        if self.budget.exceeded():
            self._tripped = True
            logger.warning("Resource budget exceeded: tokens=%.0f, calls=%d", self.budget._tokens, self.budget._calls)
            return False
        return True

    def record_failure(self) -> None:
        """Record a failure — may trip circuit breaker."""
        self.circuit_breaker.record_failure()
        if self.circuit_breaker.state == "OPEN":
            self._tripped = True
            logger.warning("Circuit breaker OPEN — halting evaluation")

    def record_success(self) -> None:
        self.circuit_breaker.record_success()
```

**Step 3: Run tests**

Run: `pytest tests/test_resource_governor.py -v`
Expected: All PASS

**Step 4: Integrate ResourceGovernor into ConvergenceLoop**

Add parameter to `ConvergenceLoop.__init__`:

```python
    def __init__(
        self,
        ...,
        resource_governor: ResourceGovernor | None = None,
    ):
        ...
        self.governor = resource_governor
```

Check in the run loop before each iteration:

```python
    for iteration in range(1, self.max_iterations + 1):
        if self.governor and not self.governor.check():
            stop_reason = "resource_exhausted"
            break
        ...
```

**Step 5: Add integration test**

```python
    def test_stops_on_resource_exhaustion(self):
        from mas_eval.harness.resource_governor import TokenBudget, ResourceGovernor

        budget = TokenBudget(max_calls=1)
        governor = ResourceGovernor(budget=budget)

        called = [0]
        def runner(card, **kw):
            called[0] += 1
            return {"score": 80.0, "findings": [], "domain_scores": {}}

        loop = ConvergenceLoop(max_iterations=10, resource_governor=governor)
        result = loop.run(SAMPLE_CARD, runner)
        assert result["stop_reason"] == "resource_exhausted"
        assert called[0] == 1  # Only ran once (budget allowed 1 call, loop consumed 1)
```

**Step 6: Run all loop engine tests**

Run: `pytest tests/test_loop_engine.py -v`
Expected: All 6+ tests PASS

**Step 7: Commit**

```bash
git add mas_eval/harness/resource_governor.py mas_eval/harness/loop_engine.py tests/test_resource_governor.py
git commit -m "feat: ResourceGovernor — TokenBudget + CircuitBreaker integration for evaluation loops"
```

---

### Summary: Execution Order & Dependencies

```
Task 1: ConvergenceLoop Engine ─────────────────────────────── no deps
Task 2: Adaptive Level Escalation ──────────────────────────── depends on Task 1 (optional --converge flag)
Task 3: D5 Verifier Registry ───────────────────────────────── no deps (wires into D5)
Task 4: L4 Multi-Epoch Lifecycle ───────────────────────────── depends on Task 3 (verifier_registry param)
Task 5: ResourceGovernor ───────────────────────────────────── depends on Task 1 (ConvergenceLoop integration)
```

**Parallel execution possible:** Tasks 1, 3, and 5 can be implemented independently.

**Recommended execution:**
1. Task 1 (foundation) + Task 3 (independent)
2. Task 5 (extends Task 1) + Task 2 (independent, light deps)
3. Task 4 (extends Task 3)

**Verification:** After all tasks complete:
```bash
pytest tests/ -v --durations=10
```
Expected: 1140+ tests passed, 0 failed, coverage maintained.
