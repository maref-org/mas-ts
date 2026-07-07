# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v0.6.0: Regression Baseline Comparison Tool.

R8 P0 (Audit Report §9) — Gold Standard requires regression test suite
to detect score drift between releases. This module provides:

- ``load_baseline``: Load a JSON baseline snapshot from disk.
- ``compare_with_tolerance``: Compare actual vs baseline with 5% relative
  tolerance (matches ``loop_engine.regression_threshold``).
- ``validate_schema``: Validate a data dict against a JSON Schema file.

Usage:
    from mas_eval.scoring.regression import (
        load_baseline,
        compare_with_tolerance,
        validate_schema,
    )

    baseline = load_baseline("mas_eval/data/baselines/v0.6.0_baseline.json")
    result = compare_with_tolerance(actual, baseline, tolerance=0.05)
    if not result.passed:
        for diff in result.diffs:
            print(f"{diff['path']}: {diff['expected']} -> {diff['actual']}")

The 5% tolerance is consistent with ``loop_engine.regression_threshold``
to avoid dual standards across the codebase.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

# R8 P0 — relative tolerance for regression comparison. Matches
# loop_engine.regression_threshold (no dual standards).
DEFAULT_TOLERANCE = 0.05

# Severity thresholds: >tolerance*2 = HIGH, >tolerance = WARNING.
# These map to findings.Severity levels for cross-module consistency.
HIGH_SEVERITY_MULTIPLIER = 2.0

PathLike = Union[str, Path]


@dataclass
class RegressionResult:
    """Result of a regression baseline comparison.

    Attributes:
        passed: True if no diffs and no schema errors.
        diffs: List of per-field differences, each with keys:
            ``path`` (dotted key path), ``expected``, ``actual``,
            ``delta_pct`` (relative diff as fraction), ``severity``
            (``"WARNING"`` or ``"HIGH"``).
        schema_errors: List of JSON Schema validation error messages
            (empty if ``validate_schema`` not invoked or no errors).
    """

    passed: bool
    diffs: list[dict[str, Any]] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)


def load_baseline(path: PathLike) -> dict[str, Any]:
    """Load a baseline JSON snapshot from disk.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        Parsed baseline as a dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If the parsed JSON is not a dict (object).
    """
    import json

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Baseline file not found: {path}")
    text = p.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(
            f"Baseline must be a JSON object, got {type(data).__name__}: {path}"
        )
    return data


def compare_with_tolerance(
    actual: dict[str, Any],
    baseline: dict[str, Any],
    tolerance: float = DEFAULT_TOLERANCE,
) -> RegressionResult:
    """Compare actual vs baseline with relative tolerance.

    Comparison rules:
    - Numeric values (int/float, excluding bool): PASS if
      ``|actual - expected| / max(|expected|, 1e-9) <= tolerance``.
      For ``expected == 0``, uses absolute diff ``<= tolerance``.
    - Non-numeric values (str/list/dict/None/bool): strict equality.
    - Nested dicts: recursive walk, path tracked as dotted key.
    - Missing key in actual: recorded as diff with ``actual = None``.
    - Extra key in actual: recorded as diff with ``expected = None``.

    Args:
        actual: The actual measurement dict.
        baseline: The baseline dict to compare against.
        tolerance: Relative tolerance fraction (default 0.05 = 5%).

    Returns:
        RegressionResult with ``passed`` flag and per-field diffs.
    """
    diffs: list[dict[str, Any]] = []
    _walk_compare(actual, baseline, "", tolerance, diffs)
    return RegressionResult(passed=not diffs, diffs=diffs)


def _walk_compare(
    actual: Any,
    expected: Any,
    path: str,
    tolerance: float,
    diffs: list[dict[str, Any]],
) -> None:
    """Recursively walk actual vs expected, appending diffs."""
    # Both dicts: recurse over union of keys.
    if isinstance(actual, dict) and isinstance(expected, dict):
        keys = set(actual.keys()) | set(expected.keys())
        for key in sorted(keys):
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                diffs.append(_make_diff(child_path, expected[key], None, tolerance))
            elif key not in expected:
                diffs.append(_make_diff(child_path, None, actual[key], tolerance))
            else:
                _walk_compare(actual[key], expected[key], child_path, tolerance, diffs)
        return

    # Both lists: compare element-wise (strict length then per-index).
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            diffs.append(_make_diff(path, expected, actual, tolerance))
            return
        for i, (a, e) in enumerate(zip(actual, expected)):
            child_path = f"{path}[{i}]"
            _walk_compare(a, e, child_path, tolerance, diffs)
        return

    # Type mismatch or non-numeric: strict equality.
    if (
        isinstance(actual, (int, float))
        and isinstance(expected, (int, float))
        and not isinstance(actual, bool)
        and not isinstance(expected, bool)
    ):
        delta_pct = _relative_delta(actual, expected)
        if delta_pct > tolerance:
            diffs.append(_make_diff(path, expected, actual, tolerance, delta_pct))
        return

    # Non-numeric strict equality.
    if actual != expected:
        diffs.append(_make_diff(path, expected, actual, tolerance))


def _relative_delta(actual: float, expected: float) -> float:
    """Compute relative delta; uses absolute diff when expected is 0."""
    denom = max(abs(expected), 1e-9)
    return abs(actual - expected) / denom


def _make_diff(
    path: str,
    expected: Any,
    actual: Any,
    tolerance: float,
    delta_pct: float | None = None,
) -> dict[str, Any]:
    """Build a diff record with severity grading."""
    if delta_pct is None:
        # Non-numeric diff: severity HIGH for structural mismatch
        # (missing/extra key or type change), WARNING for same-type
        # value change (e.g., "A" -> "B").
        if type(expected) is not type(actual):
            delta_pct = 1.0  # type change → HIGH
            severity = "HIGH"
        else:
            delta_pct = tolerance + 0.01  # just over tolerance → WARNING
            severity = "WARNING"
        return {
            "path": path,
            "expected": expected,
            "actual": actual,
            "delta_pct": delta_pct,
            "severity": severity,
        }
    if delta_pct > tolerance * HIGH_SEVERITY_MULTIPLIER:
        severity = "HIGH"
    else:
        severity = "WARNING"
    return {
        "path": path,
        "expected": expected,
        "actual": actual,
        "delta_pct": delta_pct,
        "severity": severity,
    }


def validate_schema(
    data: dict[str, Any],
    schema_path: PathLike,
) -> list[str]:
    """Validate data against a JSON Schema file.

    Args:
        data: The data dict to validate.
        schema_path: Path to the JSON Schema file.

    Returns:
        List of error message strings (empty if valid).

    Raises:
        FileNotFoundError: If schema file does not exist.
    """
    import json

    p = Path(schema_path)
    if not p.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    schema = json.loads(p.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        # jsonschema is a project dependency; if missing, fall back to
        # a minimal structural check so the function still works.
        return _minimal_validate(data, schema)
    validator = jsonschema.Draft7Validator(schema)
    return [err.message for err in validator.iter_errors(data)]


def _minimal_validate(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Minimal schema validation fallback when jsonschema is unavailable.

    Only checks ``type`` and ``required`` keywords. Real validation should
    use ``jsonschema``; this fallback exists for resilience only.
    """
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(data, dict):
        errors.append(f"Expected object, got {type(data).__name__}")
        return errors
    if expected_type == "array" and not isinstance(data, list):
        errors.append(f"Expected array, got {type(data).__name__}")
        return errors
    required = schema.get("required", [])
    for key in required:
        if key not in data:
            errors.append(f"'{key}' is a required property")
    return errors
