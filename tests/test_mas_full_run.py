import importlib.util
import json
from pathlib import Path

import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mfr = load_module("mas_full_run", Path(__file__).parent.parent / "mas_full_run.py")


class TestScoreToGrade:
    def test_a_grade(self):
        assert mfr.score_to_grade(95) == "A"
        assert mfr.score_to_grade(100) == "A"
        assert mfr.score_to_grade(90) == "A"

    def test_b_grade(self):
        assert mfr.score_to_grade(85) == "B"
        assert mfr.score_to_grade(80) == "B"

    def test_c_grade(self):
        assert mfr.score_to_grade(75) == "C"
        assert mfr.score_to_grade(70) == "C"

    def test_d_grade(self):
        assert mfr.score_to_grade(65) == "D"
        assert mfr.score_to_grade(60) == "D"

    def test_f_grade(self):
        assert mfr.score_to_grade(59) == "F"
        assert mfr.score_to_grade(0) == "F"


class TestGradeToEmoji:
    def test_green_for_good(self):
        assert mfr.grade_to_emoji("A") == "🟢"
        assert mfr.grade_to_emoji("B") == "🟢"

    def test_yellow_orange_red(self):
        assert mfr.grade_to_emoji("C") == "🟡"
        assert mfr.grade_to_emoji("D") == "🟠"
        assert mfr.grade_to_emoji("F") == "🔴"

    def test_default(self):
        assert mfr.grade_to_emoji("X") == "⚪"


class TestComputeOverallScore:
    def test_single_layer(self):
        layers = [{"layer": 1, "score": 100}]
        assert mfr.compute_overall_score(layers) == 15.0

    def test_all_perfect(self):
        layers = [
            {"layer": 1, "score": 100},
            {"layer": 2, "score": 100},
            {"layer": 3, "score": 100},
            {"layer": 4, "score": 100},
            {"layer": 5, "score": 100},
        ]
        assert mfr.compute_overall_score(layers) == 100.0

    def test_all_zero(self):
        layers = [
            {"layer": 1, "score": 0},
            {"layer": 2, "score": 0},
            {"layer": 3, "score": 0},
            {"layer": 4, "score": 0},
            {"layer": 5, "score": 0},
        ]
        assert mfr.compute_overall_score(layers) == 0.0


class TestGenerateRecommendations:
    def test_critical_finding(self):
        card = {"compliance": {}, "orchestration_hints": {}}
        layers = [{
            "layer": 1, "score": 50, "findings": [
                {"severity": "CRITICAL", "category": "test", "detail": "critical issue"}
            ]
        }]
        recs = mfr.generate_recommendations(layers, card)
        assert any(r["priority"] == "P0" for r in recs)

    def test_high_finding(self):
        card = {"compliance": {}, "orchestration_hints": {}}
        layers = [{
            "layer": 1, "score": 50, "findings": [
                {"severity": "HIGH", "category": "test", "detail": "high issue"}
            ]
        }]
        recs = mfr.generate_recommendations(layers, card)
        assert any(r["priority"] == "P1" for r in recs)

    def test_no_critical_high(self):
        card = {"compliance": {}, "orchestration_hints": {}}
        layers = [{
            "layer": 1, "score": 100, "findings": [
                {"severity": "INFO", "category": "test", "detail": "info"}
            ]
        }]
        recs = mfr.generate_recommendations(layers, card)
        critical_or_high = [r for r in recs if r["priority"] in ("P0", "P1")]
        assert len(critical_or_high) == 0

    def test_cross_border_recommendation(self):
        card = {"compliance": {"cross_border": True}, "orchestration_hints": {}}
        recs = mfr.generate_recommendations([], card)
        assert any("cross_border" in r["category"] for r in recs)

    def test_parallel_safety_recommendation(self):
        card = {"compliance": {}, "orchestration_hints": {"parallel_safe": False}}
        recs = mfr.generate_recommendations([], card)
        assert any("parallel_safety" in r["category"] for r in recs)


class TestLoadCard:
    def test_load_valid_card(self, tmp_path):
        card = {"name": "test"}
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        result = mfr.load_card(str(p))
        assert result["name"] == "test"

    def test_load_missing_card(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            mfr.load_card(str(tmp_path / "nonexistent.json"))

    def test_load_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json")
        with pytest.raises(SystemExit):
            mfr.load_card(str(p))


class TestLoadTasks:
    def test_nonexistent_returns_none(self, tmp_path):
        assert mfr.load_tasks(str(tmp_path / "nonexistent.json")) is None

    def test_valid_tasks(self, tmp_path):
        tasks = {"tasks": ["task1"]}
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        result = mfr.load_tasks(str(p))
        assert result["tasks"] == ["task1"]
