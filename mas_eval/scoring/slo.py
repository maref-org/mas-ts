from typing import Any

from prometheus_client import Gauge

from mas_eval.scoring.gold_thresholds import (
    GOLD_THRESHOLD_MATRIX,
    LOWER_IS_BETTER_METRICS,
)

SLO_BUDGET_GAUGE = Gauge(
    "mas_eval_slo_budget_remaining",
    "SLO error budget remaining (fraction 0.0-1.0)",
    ["level", "metric"],
)
SLO_VIOLATION_GAUGE = Gauge(
    "mas_eval_slo_violations",
    "SLO violation count since process start",
    ["level", "metric"],
)
SLO_BURN_RATE_GAUGE = Gauge(
    "mas_eval_slo_burn_rate",
    "SLO error budget burn rate (violations/hour)",
    ["level", "metric"],
)

_violation_counts: dict[tuple[str, str], int] = {}
_budget_remaining: dict[tuple[str, str], float] = {}


def check_slo(
    metrics: dict[str, Any],
    level: str = "L3",
    budget_window_hours: float = 720.0,
    error_budget_fraction: float = 0.10,
) -> dict[str, Any]:
    if level not in GOLD_THRESHOLD_MATRIX:
        return {"level": level, "error": f"unknown level {level}"}

    thresholds = GOLD_THRESHOLD_MATRIX[level]
    results: dict[str, Any] = {
        "level": level,
        "metrics": {},
        "violations": [],
        "budget_exhausted": False,
        "overall_pass": True,
    }

    for metric_name, threshold_value in thresholds.items():
        if metric_name in ("level", "time_budget_minutes", "overall_score"):
            continue
        if metric_name not in metrics:
            continue

        actual = metrics[metric_name]
        if metric_name in LOWER_IS_BETTER_METRICS:
            passed = actual <= threshold_value
        else:
            passed = actual >= threshold_value

        key = (level, metric_name)
        _violation_counts.setdefault(key, 0)
        if not passed:
            _violation_counts[key] += 1

        violations = _violation_counts[key]
        budget = max(0.0, 1.0 - violations * error_budget_fraction)
        _budget_remaining[key] = budget
        exhausted = budget <= 0.0

        SLO_VIOLATION_GAUGE.labels(level=level, metric=metric_name).set(violations)
        SLO_BUDGET_GAUGE.labels(level=level, metric=metric_name).set(budget)
        burn_rate = violations / max(budget_window_hours, 1)
        SLO_BURN_RATE_GAUGE.labels(level=level, metric=metric_name).set(burn_rate)

        results["metrics"][metric_name] = {
            "value": actual,
            "threshold": threshold_value,
            "passed": passed,
            "violations_since_start": violations,
            "budget_remaining": round(budget, 4),
            "budget_exhausted": exhausted,
        }
        if exhausted:
            results["budget_exhausted"] = True
        if not passed:
            results["violations"].append({
                "metric": metric_name,
                "value": actual,
                "threshold": threshold_value,
            })

    results["overall_pass"] = len(results["violations"]) == 0 and not results["budget_exhausted"]
    results["total_checks"] = len(results["metrics"])
    results["passed_checks"] = sum(
        1 for m in results["metrics"].values() if m["passed"]
    )
    return results


def reset_slo_state() -> None:
    _violation_counts.clear()
    _budget_remaining.clear()
    for metric in SLO_VIOLATION_GAUGE.collect():
        for sample in metric.samples:
            SLO_VIOLATION_GAUGE.labels(
                level=sample.labels["level"],
                metric=sample.labels["metric"],
            ).set(0)
    for metric in SLO_BUDGET_GAUGE.collect():
        for sample in metric.samples:
            SLO_BUDGET_GAUGE.labels(
                level=sample.labels["level"],
                metric=sample.labels["metric"],
            ).set(1.0)
    for metric in SLO_BURN_RATE_GAUGE.collect():
        for sample in metric.samples:
            SLO_BURN_RATE_GAUGE.labels(
                level=sample.labels["level"],
                metric=sample.labels["metric"],
            ).set(0.0)


def get_level_slo_summary(level: str = "L3") -> dict[str, Any]:
    summary: dict[str, Any] = {
        "level": level,
        "metrics": {},
        "total_violations": 0,
        "total_budgets_exhausted": 0,
    }
    for (lvl, metric_name), count in _violation_counts.items():
        if lvl != level:
            continue
        budget = _budget_remaining.get((lvl, metric_name), 1.0)
        summary["metrics"][metric_name] = {
            "violations": count,
            "budget_remaining": round(budget, 4),
            "exhausted": budget <= 0.0,
        }
        summary["total_violations"] += count
        if budget <= 0.0:
            summary["total_budgets_exhausted"] += 1
    return summary
