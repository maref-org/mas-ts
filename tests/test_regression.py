# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.scoring.regression (R8 P0 — Audit Report §9).

Verifies RegressionResult dataclass, load_baseline, compare_with_tolerance
(5% relative tolerance), and validate_schema. The 5% tolerance is consistent
with loop_engine.regression_threshold.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.scoring.regression import (
    RegressionResult,
    compare_with_tolerance,
    load_baseline,
    validate_schema,
)

# Module-level marker: `pytest -m regression` selects this file.
pytestmark = pytest.mark.regression

BASELINE_PATH = (
    Path(__file__).parent.parent
    / "mas_eval"
    / "data"
    / "baselines"
    / "v0.7.0_baseline.json"
)


# ═══════════════════════════════════════════════════════════════
# TestRegressionResult — dataclass structure (6 tests)
# ═══════════════════════════════════════════════════════════════


class TestRegressionResult:
    def test_dataclass_fields(self):
        result = RegressionResult(passed=True)
        assert hasattr(result, "passed")
        assert hasattr(result, "diffs")
        assert hasattr(result, "schema_errors")

    def test_passed_true_when_no_diffs(self):
        result = RegressionResult(passed=True, diffs=[])
        assert result.passed is True
        assert result.diffs == []

    def test_passed_false_when_diffs_exist(self):
        diff = {
            "path": "x",
            "expected": 1,
            "actual": 2,
            "delta_pct": 1.0,
            "severity": "HIGH",
        }
        result = RegressionResult(passed=False, diffs=[diff])
        assert result.passed is False
        assert len(result.diffs) == 1

    def test_diffs_structure(self):
        diff = {
            "path": "a.b",
            "expected": 10,
            "actual": 12,
            "delta_pct": 0.2,
            "severity": "HIGH",
        }
        result = RegressionResult(passed=False, diffs=[diff])
        d = result.diffs[0]
        assert set(d.keys()) == {"path", "expected", "actual", "delta_pct", "severity"}

    def test_schema_errors_default_empty(self):
        result = RegressionResult(passed=True)
        assert result.schema_errors == []

    def test_dataclass_immutable_via_init(self):
        """`passed` is a required field with no default."""
        with pytest.raises(TypeError):
            RegressionResult()


# ═══════════════════════════════════════════════════════════════
# TestLoadBaseline (6 tests)
# ═══════════════════════════════════════════════════════════════


class TestLoadBaseline:
    def test_load_valid_baseline(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "0.6.0", "anchors": {}}')
            f.flush()
            data = load_baseline(f.name)
        assert data["version"] == "0.6.0"

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_baseline("/nonexistent/path/baseline.json")

    def test_load_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            f.flush()
            with pytest.raises(json.JSONDecodeError):
                load_baseline(f.name)

    def test_load_non_object_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[1, 2, 3]")
            f.flush()
            with pytest.raises(ValueError, match="JSON object"):
                load_baseline(f.name)

    def test_load_baseline_returns_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()
            data = load_baseline(f.name)
        assert isinstance(data, dict)

    def test_load_baseline_has_anchors_key(self):
        """The real v0.6.0 baseline file must have an `anchors` key."""
        if not BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not yet created: {BASELINE_PATH}")
        data = load_baseline(BASELINE_PATH)
        assert "anchors" in data
        assert "version" in data


# ═══════════════════════════════════════════════════════════════
# TestCompareWithTolerance (10 tests)
# ═══════════════════════════════════════════════════════════════


class TestCompareWithTolerance:
    def test_identical_dicts_pass(self):
        d = {"a": 1, "b": "x"}
        result = compare_with_tolerance(d, dict(d))
        assert result.passed is True
        assert result.diffs == []

    def test_numeric_within_tolerance_pass(self):
        actual = {"score": 100.0}
        baseline = {"score": 103.0}  # 3% diff
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is True

    def test_numeric_outside_tolerance_fail(self):
        actual = {"score": 100.0}
        baseline = {"score": 110.0}  # 10% diff
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0]["path"] == "score"

    def test_zero_expected_uses_absolute_diff(self):
        """When expected=0, |actual-0|/max(0,1e-9) = |actual|/1e-9, very large → fails unless actual=0."""
        actual = {"count": 0.0}
        baseline = {"count": 0.0}
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is True

    def test_negative_values_compared_correctly(self):
        actual = {"delta": -100.0}
        baseline = {"delta": -103.0}  # 3% relative diff
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is True

    def test_nested_dict_recursive_walk(self):
        actual = {"outer": {"inner": 50.0}}
        baseline = {"outer": {"inner": 60.0}}  # 16.6% diff
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is False
        assert result.diffs[0]["path"] == "outer.inner"

    def test_non_numeric_strict_equality(self):
        actual = {"grade": "B"}
        baseline = {"grade": "A"}
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is False
        assert result.diffs[0]["expected"] == "A"
        assert result.diffs[0]["actual"] == "B"

    def test_missing_key_in_actual_fails(self):
        actual = {"a": 1}
        baseline = {"a": 1, "b": 2}
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is False
        paths = [d["path"] for d in result.diffs]
        assert "b" in paths

    def test_extra_key_in_actual_fails(self):
        actual = {"a": 1, "extra": 99}
        baseline = {"a": 1}
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is False
        paths = [d["path"] for d in result.diffs]
        assert "extra" in paths

    def test_tolerance_boundary_exactly_5pct(self):
        """At exactly 5% delta, comparison should PASS (uses > not >=)."""
        actual = {"score": 105.0}
        baseline = {"score": 100.0}  # exactly 5%
        result = compare_with_tolerance(actual, baseline, tolerance=0.05)
        assert result.passed is True
        # Just over the boundary fails
        actual2 = {"score": 105.1}
        result2 = compare_with_tolerance(actual2, baseline, tolerance=0.05)
        assert result2.passed is False


# ═══════════════════════════════════════════════════════════════
# TestValidateSchema (5 tests)
# ═══════════════════════════════════════════════════════════════


class TestValidateSchema:
    def _write_schema(self, schema: dict) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps(schema))
            f.flush()
            return f.name

    def test_valid_data_no_errors(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        path = self._write_schema(schema)
        errors = validate_schema({"name": "agent-001"}, path)
        assert errors == []

    def test_invalid_data_returns_errors(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        path = self._write_schema(schema)
        errors = validate_schema({}, path)
        assert len(errors) > 0

    def test_missing_required_field_error(self):
        schema = {
            "type": "object",
            "required": ["agent_id", "version"],
            "properties": {
                "agent_id": {"type": "string"},
                "version": {"type": "string"},
            },
        }
        path = self._write_schema(schema)
        errors = validate_schema({"agent_id": "x"}, path)
        assert any("version" in e for e in errors)

    def test_wrong_type_error(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "number"}},
        }
        path = self._write_schema(schema)
        errors = validate_schema({"count": "not-a-number"}, path)
        assert len(errors) > 0

    def test_schema_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            validate_schema({}, "/nonexistent/schema.json")


# ═══════════════════════════════════════════════════════════════
# TestBaselineAnchors — verify the real v0.6.0 baseline (3 tests)
# ═══════════════════════════════════════════════════════════════


class TestBaselineAnchors:
    """Verify the real v0.7.0 baseline file has the three required anchors."""

    def test_baseline_has_d1_d5_pipeline_anchor(self):
        if not BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not yet created: {BASELINE_PATH}")
        data = load_baseline(BASELINE_PATH)
        assert "d1_d5_pipeline" in data["anchors"]
        assert "cards" in data["anchors"]["d1_d5_pipeline"]

    def test_baseline_has_federation_scan_anchor(self):
        if not BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not yet created: {BASELINE_PATH}")
        data = load_baseline(BASELINE_PATH)
        assert "federation_scan" in data["anchors"]
        fed = data["anchors"]["federation_scan"]
        assert fed["vendor_count"] == 5
        assert "vendors" in fed

    def test_baseline_has_gold_trajectories_anchor(self):
        if not BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not yet created: {BASELINE_PATH}")
        data = load_baseline(BASELINE_PATH)
        assert "gold_trajectories" in data["anchors"]
        traj = data["anchors"]["gold_trajectories"]
        assert traj["trajectory_count"] == 10
        assert len(traj["trajectories"]) == 10
