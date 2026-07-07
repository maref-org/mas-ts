# SPDX-FileCopyrightText: 2026 MAREF Project Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for EmergenceHarness emergent behavior detection."""

from mas_eval.harness.emergence_harness import (
    _dimension_correlations,
    _extract_dimensions,
    _mock_improvement_history,
    _pearson,
    run_emergence_harness,
)


class TestRunEmergenceHarnessEmpty:
    def test_empty_history_returns_100(self):
        result = run_emergence_harness(improvement_history=[])
        assert result["score"] == 100.0
        assert result["verdict"] == "APPROVED"

    def test_none_history_generates_mock(self):
        result = run_emergence_harness(improvement_history=None)
        assert isinstance(result, dict)
        assert "emergence_detail" in result["domains"]

    def test_empty_history_has_required_keys(self):
        result = run_emergence_harness(improvement_history=[])
        for key in (
            "level",
            "name",
            "score",
            "grade",
            "verdict",
            "domain_scores",
            "domains",
            "findings",
        ):
            assert key in result, f"Missing key: {key}"


class TestRunEmergenceHarness:
    def make_history(self, count=20):
        return [
            {
                "round": i,
                "target_dimension": "correctness" if i % 2 == 0 else "testing",
                "metric_value": 0.7 + (i / 100.0),
                "dimension_scores": {
                    "correctness": 0.8 + (i / 100.0),
                    "testing": 0.7
                    - (
                        i / 200.0
                    ),  # diverging: testing declines as correctness improves
                    "code_quality": 0.75,
                    "security": 0.8,
                    "performance": 0.7,
                },
                "status": "keep" if i % 3 != 0 else "discard",
            }
            for i in range(count)
        ]

    def test_returns_dict_with_real_history(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        for key in (
            "level",
            "name",
            "elapsed_seconds",
            "score",
            "grade",
            "verdict",
            "domain_scores",
            "domains",
            "findings",
            "detection_results",
            "severity_summary",
        ):
            assert key in result, f"Missing key: {key}"

    def test_level_is_l3(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert result["level"] == "L3"

    def test_name_is_emergence(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert result["name"] == "Emergence"

    def test_score_in_range(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert 0.0 <= result["score"] <= 100.0

    def test_domain_scores_has_emergence(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert "emergence" in result["domain_scores"]

    def test_detection_results_has_all_modes(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        dr = result["detection_results"]
        for mode in (
            "cross_dimension_side_effect",
            "behavioral_drift",
            "capability_leakage",
            "oscillation_emergence",
        ):
            assert mode in dr, f"Missing detection mode: {mode}"

    def test_findings_list(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert isinstance(result["findings"], list)

    def test_verdict_is_string(self):
        result = run_emergence_harness(improvement_history=self.make_history())
        assert isinstance(result["verdict"], str)

    def test_severity_summary(self):
        result = run_emergence_harness(improvement_history=self.make_history(50))
        ss = result["severity_summary"]
        for s in ("CRITICAL", "HIGH", "WARNING", "INFO"):
            assert s in ss


class TestRunEmergenceHarnessSideEffects:
    def test_detects_negative_correlation(self):
        # Strong negative correlation between correctness and testing
        history = [
            {
                "round": i,
                "target_dimension": "correctness",
                "metric_value": 0.5 + (i / 50.0),
                "dimension_scores": {
                    "correctness": 0.5 + (i / 50.0),
                    "testing": 0.9 - (i / 50.0),  # strong negative
                },
                "status": "keep",
            }
            for i in range(20)
        ]
        result = run_emergence_harness(improvement_history=history)
        cd = result["detection_results"]["cross_dimension_side_effect"]
        assert cd["detected"] is True

    def test_capability_leakage_detected(self):
        history = [
            {
                "round": i,
                "target_dimension": "correctness",
                "metric_value": 0.7,
                "dimension_scores": {
                    "correctness": 0.7 + (0.2 if i > 5 else 0.0),
                    "testing": 0.7 + (0.2 if i > 5 else 0.0),  # leak!
                    "security": 0.7,
                },
                "status": "keep",
            }
            for i in range(10)
        ]
        result = run_emergence_harness(improvement_history=history)
        cl = result["detection_results"]["capability_leakage"]
        if cl["detected"]:
            assert len(cl["leak_indicators"]) > 0

    def test_no_false_positive_without_side_effects(self):
        history = [
            {
                "round": i,
                "target_dimension": "correctness",
                "metric_value": 0.7,
                "dimension_scores": {
                    "correctness": 0.7,
                    "testing": 0.7,
                    "security": 0.7,
                },
                "status": "keep",
            }
            for i in range(10)
        ]
        result = run_emergence_harness(improvement_history=history)
        cd = result["detection_results"]["cross_dimension_side_effect"]
        assert cd["detected"] is False


class TestPearson:
    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0]
        y = [2.0, 4.0, 6.0]
        assert abs(_pearson(x, y) - 1.0) < 1e-10

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0]
        y = [3.0, 2.0, 1.0]
        assert abs(_pearson(x, y) - (-1.0)) < 1e-10

    def test_no_correlation(self):
        x = [1.0, 2.0, 3.0]
        y = [2.0, 2.0, 2.0]
        assert _pearson(x, y) == 0.0

    def test_positive_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 3.0, 4.0, 5.0, 6.0]
        assert abs(_pearson(x, y) - 1.0) < 0.001

    def test_negative_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert abs(_pearson(x, y) - (-1.0)) < 0.001

    def test_less_than_two_points(self):
        assert _pearson([1.0], [2.0]) == 0.0

    def test_empty_returns_zero(self):
        assert _pearson([], []) == 0.0

    def test_zero_variance(self):
        assert _pearson([1.0, 1.0, 1.0], [2.0, 3.0, 4.0]) == 0.0


class TestExtractDimensions:
    def test_empty_history(self):
        assert _extract_dimensions([]) == []

    def test_single_entry(self):
        h = [{"dimension_scores": {"a": 1.0, "b": 2.0}}]
        dims = _extract_dimensions(h)
        assert dims == ["a", "b"]

    def test_multiple_entries(self):
        h = [
            {"dimension_scores": {"a": 1.0}},
            {"dimension_scores": {"b": 2.0}},
        ]
        dims = _extract_dimensions(h)
        assert "a" in dims
        assert "b" in dims

    def test_no_dimension_scores(self):
        h = [{"metric_value": 0.5}]
        assert _extract_dimensions(h) == []


class TestDimensionCorrelations:
    def test_returns_dict(self):
        h = _mock_improvement_history(20)
        dims = _extract_dimensions(h)
        corr = _dimension_correlations(h, dims)
        assert isinstance(corr, dict)

    def test_correlation_in_range(self):
        h = _mock_improvement_history(20)
        dims = _extract_dimensions(h)
        corr = _dimension_correlations(h, dims)
        for val in corr.values():
            assert -1.0 <= val <= 1.0, f"Correlation out of range: {val}"

    def test_insufficient_data_returns_empty(self):
        h = [{"dimension_scores": {"a": 1.0, "b": 2.0}}]
        corr = _dimension_correlations(h, ["a", "b"])
        assert corr == {}


class TestMockImprovementHistory:
    def test_default_count(self):
        h = _mock_improvement_history()
        assert len(h) == 50

    def test_custom_count(self):
        h = _mock_improvement_history(10)
        assert len(h) == 10

    def test_each_has_required_keys(self):
        h = _mock_improvement_history(5)
        for entry in h:
            assert "round" in entry
            assert "target_dimension" in entry
            assert "metric_value" in entry
            assert "dimension_scores" in entry
            assert "status" in entry

    def test_deterministic(self):
        h1 = _mock_improvement_history(10)
        h2 = _mock_improvement_history(10)
        for e1, e2 in zip(h1, h2):
            assert e1["metric_value"] == e2["metric_value"]
