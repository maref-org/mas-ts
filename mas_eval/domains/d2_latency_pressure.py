# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""D2 latency pressure sub-domain (R4 — Handbook §4.4.2 TTFT P99≤500ms).

Evaluates first-token latency (TTFT) against the Gold Standard P99 threshold.
Lower TTFT is better; scores decay linearly once the threshold is exceeded.

Scoring tiers:
    - Gold   (≤ 200ms):  100.0
    - Silver (≤ 350ms):   85.0
    - Bronze (≤ 500ms):   70.0
    - Over threshold (500-1000ms): linear decay 70 → 0
    - Critical (> 1000ms): 0.0

Returns the standard sub-domain tuple: (score, findings, subscore_dict).
"""

import math
from typing import Any

# Gold Standard §4.4.2 — TTFT thresholds (milliseconds)
TTFT_THRESHOLD_MS = 500.0  # Bronze / pass threshold (P99 ≤ 500ms)
TTFT_GOLD_MS = 200.0  # Gold tier
TTFT_SILVER_MS = 350.0  # Silver tier


def run_latency_pressure(
    trajectory: list[dict[str, Any]] | None,
    threshold_ms: float = TTFT_THRESHOLD_MS,
) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    """Evaluate first-token latency (TTFT) against P99 threshold.

    Args:
        trajectory: List of action dicts; each action may carry ``ttft_ms``
            or ``latency_ms``. Non-dict entries and missing/invalid values
            are skipped.
        threshold_ms: P99 TTFT threshold in milliseconds (default 500ms per
            Handbook §4.4.2). Only affects the Bronze tier and decay range;
            Gold (200ms) and Silver (350ms) are fixed reference tiers that
            do not scale with threshold_ms. This lets callers tighten the
            pass threshold without inflating Gold/Silver ratings.

    Returns:
        Tuple of ``(score 0-100, findings list, subscore dict)``.
        Returns ``(0.0, [], subscore)`` when trajectory is empty or contains
        no valid TTFT samples.
    """
    findings: list[dict[str, Any]] = []

    if not trajectory:
        return (
            0.0,
            [],
            {
                "p99_ttft_ms": 0.0,
                "threshold_ms": threshold_ms,
                "sample_count": 0,
            },
        )

    # Extract TTFT samples from actions (accept ttft_ms or latency_ms)
    ttft_samples: list[float] = []
    for action in trajectory:
        if not isinstance(action, dict):
            continue
        ttft = action.get("ttft_ms")
        if ttft is None:
            ttft = action.get("latency_ms")
        if ttft is None:
            continue
        if isinstance(ttft, (int, float)) and ttft > 0:
            ttft_samples.append(float(ttft))

    if not ttft_samples:
        return (
            0.0,
            [
                {
                    "severity": "WARNING",
                    "category": "latency",
                    "detail": (
                        "No TTFT samples found in trajectory; "
                        "cannot evaluate latency pressure."
                    ),
                }
            ],
            {
                "p99_ttft_ms": 0.0,
                "threshold_ms": threshold_ms,
                "sample_count": 0,
            },
        )

    # Calculate P99 via nearest-rank method (no numpy dependency).
    # ceil(n*0.99)-1 gives the 0-indexed position of the 99th percentile:
    #   n=1 → 0, n=2 → 1 (larger value, not smaller), n=100 → 98.
    # Clamp to [0, n-1] for safety on small samples.
    sorted_samples = sorted(ttft_samples)
    n = len(sorted_samples)
    p99_idx = min(n - 1, max(0, math.ceil(n * 0.99) - 1))
    p99_ttft = sorted_samples[p99_idx]

    subscore: dict[str, Any] = {
        "p99_ttft_ms": p99_ttft,
        "threshold_ms": threshold_ms,
        "sample_count": n,
    }

    # Scoring tiers (Gold/Silver/Bronze/decay/critical)
    if p99_ttft <= TTFT_GOLD_MS:
        score = 100.0
        severity = "INFO"
        detail = f"P99 TTFT {p99_ttft:.1f}ms ≤ Gold {TTFT_GOLD_MS}ms"
    elif p99_ttft <= TTFT_SILVER_MS:
        score = 85.0
        severity = "INFO"
        detail = f"P99 TTFT {p99_ttft:.1f}ms ≤ Silver {TTFT_SILVER_MS}ms"
    elif p99_ttft <= threshold_ms:
        score = 70.0
        severity = "WARNING"
        detail = (
            f"P99 TTFT {p99_ttft:.1f}ms exceeds Silver but ≤ threshold {threshold_ms}ms"
        )
    elif p99_ttft <= threshold_ms * 2:
        # Linear decay from 70 to 0 across [threshold, 2*threshold]
        score = 70.0 * (1 - (p99_ttft - threshold_ms) / threshold_ms)
        severity = "HIGH"
        detail = f"P99 TTFT {p99_ttft:.1f}ms exceeds threshold {threshold_ms}ms"
    else:
        score = 0.0
        severity = "CRITICAL"
        detail = f"P99 TTFT {p99_ttft:.1f}ms > 2x threshold {threshold_ms}ms"

    findings.append(
        {
            "severity": severity,
            "category": "latency",
            "detail": detail,
        }
    )
    return max(0.0, min(100.0, score)), findings, subscore
