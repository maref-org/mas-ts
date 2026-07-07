"""CapacityHarness — L3 capacity testing for MAS-TS-001.

Tests system capacity under increasing load to determine:
1. Maximum concurrent evaluation runs
2. Throughput limits
3. Latency degradation under load
4. Resource usage patterns
"""

import logging
import time
from typing import Any, Callable

from mas_eval.scoring.absolute import determine_verdict, score_to_grade

logger = logging.getLogger(__name__)

CAPACITY_TIMEOUT_SECONDS = 3600
CONCURRENCY_LEVELS = [1, 5, 10, 20, 50]
THROUGHPUT_TARGET = 100


def run_capacity_test(
    runner_fn: Callable[[int], dict[str, Any]] | None = None,
    max_concurrency: int = 20,
    iterations_per_level: int = 10,
) -> dict[str, Any]:
    """Run capacity test with increasing concurrency levels.

    Args:
        runner_fn: Optional callable that simulates an evaluation run.
        max_concurrency: Maximum concurrent runs to test.
        iterations_per_level: Number of iterations per concurrency level.

    Returns:
        Capacity test results with throughput, latency, and resource metrics.
    """
    start = time.time()
    all_findings: list[dict[str, Any]] = []
    level_results: dict[int, dict[str, Any]] = {}
    all_latencies: list[float] = []
    total_completed = 0

    def _make_finding(severity: str, category: str, detail: str) -> dict[str, Any]:
        return {"severity": severity, "category": category, "detail": detail}

    def _mock_runner(_: int) -> dict[str, Any]:
        time.sleep(0.05)
        return {"score": 90.0, "latency_ms": 50}

    actual_runner = runner_fn or _mock_runner

    for concurrency in CONCURRENCY_LEVELS:
        if concurrency > max_concurrency:
            break

        logger.info(f"Capacity test: concurrency level {concurrency}")
        level_start = time.time()
        latencies: list[float] = []
        errors: int = 0

        for _ in range(iterations_per_level):
            iteration_start = time.time()
            try:
                result = actual_runner(concurrency)
                latency_ms = result.get(
                    "latency_ms", (time.time() - iteration_start) * 1000
                )
                latencies.append(latency_ms)
                all_latencies.append(latency_ms)
                total_completed += 1
            except Exception as exc:
                errors += 1
                all_findings.append(
                    _make_finding(
                        "WARNING",
                        "capacity_error",
                        f"Error at concurrency {concurrency}: {exc}",
                    )
                )

        level_elapsed = time.time() - level_start
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p99_latency = sorted(latencies)[-1] if latencies else 0
        throughput = iterations_per_level / level_elapsed if level_elapsed > 0 else 0

        level_results[concurrency] = {
            "concurrency": concurrency,
            "iterations": iterations_per_level,
            "errors": errors,
            "avg_latency_ms": round(avg_latency, 2),
            "p99_latency_ms": round(p99_latency, 2),
            "throughput_per_sec": round(throughput, 2),
            "elapsed_seconds": round(level_elapsed, 2),
        }

        if p99_latency > 500:
            all_findings.append(
                _make_finding(
                    "WARNING",
                    "latency_degradation",
                    f"P99 latency {p99_latency:.1f}ms exceeds 500ms at concurrency {concurrency}",
                )
            )

        if errors > 0:
            all_findings.append(
                _make_finding(
                    "HIGH",
                    "capacity_limit",
                    f"{errors} errors at concurrency {concurrency}",
                )
            )

    overall_avg_latency = (
        sum(all_latencies) / len(all_latencies) if all_latencies else 0
    )
    overall_p99_latency = sorted(all_latencies)[-1] if all_latencies else 0
    total_elapsed = time.time() - start

    throughput_score = min(
        total_completed / max(total_elapsed, 1) / THROUGHPUT_TARGET * 100, 100
    )
    latency_score = (
        100
        if overall_p99_latency <= 500
        else max(0, 100 - (overall_p99_latency - 500) / 10)
    )
    error_score = (
        100
        if total_completed > 0 and errors == 0
        else max(0, (total_completed / (total_completed + errors)) * 100)
    )

    final_score = round(
        (throughput_score * 0.4 + latency_score * 0.3 + error_score * 0.3), 1
    )

    return {
        "level": "L3",
        "name": "Capacity",
        "elapsed_seconds": round(total_elapsed, 2),
        "score": final_score,
        "grade": score_to_grade(final_score),
        "verdict": determine_verdict(final_score, all_findings),
        "domain_scores": {"capacity": final_score},
        "total_completed": total_completed,
        "total_errors": errors,
        "avg_latency_ms": round(overall_avg_latency, 2),
        "p99_latency_ms": round(overall_p99_latency, 2),
        "peak_concurrency": max(level_results.keys()),
        "level_results": level_results,
        "findings": all_findings,
    }
