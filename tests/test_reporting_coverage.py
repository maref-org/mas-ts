# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for mas_eval.reporting.coverage_report module."""

import json
import os
import tempfile

import pytest

from mas_eval.reporting.coverage_report import (
    generate_module_coverage,
    save_coverage_report,
)


def _make_coverage_json(tmpdir: str, files: dict[str, dict]) -> str:
    """Create a temporary coverage.json and return its path."""
    data = {"files": files, "meta": {}}
    path = os.path.join(tmpdir, "coverage.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestGenerateModuleCoverage:
    def test_missing_file_returns_error(self):
        result = generate_module_coverage("/nonexistent/coverage.json")
        assert "error" in result

    def test_invalid_json_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            with open(path, "w") as f:
                f.write("not json")
            result = generate_module_coverage(path)
            assert "error" in result

    def test_empty_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(tmpdir, {})
            result = generate_module_coverage(path)
            assert result["modules"] == []
            assert result["overall_coverage"] == 0.0
            assert result["passed_modules"] == 0
            assert result["failed_modules"] == 0

    def test_single_module_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 0.95,
                        "total_lines": 100,
                    },
                },
            )
            result = generate_module_coverage(path)
            assert len(result["modules"]) == 1
            assert result["modules"][0]["module"] == "domains"
            assert result["modules"][0]["coverage_pct"] == 95.0
            assert result["modules"][0]["passed"] is True

    def test_multiple_modules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 0.90,
                        "total_lines": 100,
                    },
                    "mas_eval/scoring/absolute.py": {
                        "line_rate": 0.75,
                        "total_lines": 200,
                    },
                    "mas_eval/harness/l0_fast_screen.py": {
                        "line_rate": 0.85,
                        "total_lines": 150,
                    },
                },
            )
            result = generate_module_coverage(path, min_threshold=80.0)
            modules = {m["module"]: m for m in result["modules"]}
            assert "domains" in modules
            assert "scoring" in modules
            assert "harness" in modules
            assert modules["domains"]["coverage_pct"] == 90.0
            assert modules["scoring"]["coverage_pct"] == 75.0
            assert modules["harness"]["coverage_pct"] == pytest.approx(85.0, abs=1.0)
            assert result["passed_modules"] == 2
            assert result["failed_modules"] == 1

    def test_non_mas_eval_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 0.95,
                        "total_lines": 100,
                    },
                    "tests/test_foo.py": {
                        "line_rate": 0.50,
                        "total_lines": 50,
                    },
                    "setup.py": {
                        "line_rate": 0.10,
                        "total_lines": 10,
                    },
                },
            )
            result = generate_module_coverage(path)
            assert len(result["modules"]) == 1
            assert result["modules"][0]["module"] == "domains"

    def test_ascii_table_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 0.95,
                        "total_lines": 100,
                    },
                },
            )
            result = generate_module_coverage(path)
            assert "ascii_table" in result
            table = result["ascii_table"]
            assert "MAS-TS-001" in table
            assert "Module Coverage" in table
            assert "domains" in table

    def test_overall_coverage_calculation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 1.0,
                        "total_lines": 100,
                    },
                    "mas_eval/scoring/absolute.py": {
                        "line_rate": 0.5,
                        "total_lines": 100,
                    },
                },
            )
            result = generate_module_coverage(path)
            assert result["overall_coverage"] == 75.0  # (100*1.0 + 100*0.5) / 200

    def test_reporting_module_itself(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/reporting/gold_report.py": {
                        "line_rate": 0.88,
                        "total_lines": 120,
                    },
                },
            )
            result = generate_module_coverage(path)
            assert len(result["modules"]) == 1
            assert result["modules"][0]["module"] == "reporting"

    def test_save_coverage_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_path = _make_coverage_json(
                tmpdir,
                {
                    "mas_eval/domains/d1_compliance.py": {
                        "line_rate": 0.90,
                        "total_lines": 100,
                    },
                },
            )
            report = generate_module_coverage(cov_path)
            out_path = os.path.join(tmpdir, "out.json")
            saved = save_coverage_report(report, out_path)
            assert os.path.exists(saved)
            with open(saved) as f:
                data = json.load(f)
            assert "modules" in data
            assert data["modules"][0]["module"] == "domains"
