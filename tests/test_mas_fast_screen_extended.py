import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mfs_path = Path(__file__).parent.parent / "mas_fast_screen.py"
mfs = load_module("mas_fast_screen", mfs_path)


class TestRunStage:
    def test_success_with_overall_passed_true(self):
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"overall_passed": True})
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "ok"])
        assert result["status"] == "PASS"
        assert result["stage"] == "test"

    def test_fail_with_overall_passed_false(self):
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"overall_passed": False})
        mock_proc.stderr = ""
        mock_proc.returncode = 1
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "fail"])
        assert result["status"] == "FAIL"
        assert "overall_passed=false" in result["error"]

    def test_json_no_overall_passed_returncode_zero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"some_key": "value"})
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "ok"])
        assert result["status"] == "PASS"

    def test_json_no_overall_passed_returncode_nonzero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"some_key": "value"})
        mock_proc.stderr = "error occurred"
        mock_proc.returncode = 1
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "fail"])
        assert result["status"] == "FAIL"

    def test_non_json_stdout_returncode_zero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "plain text output"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "ok"])
        assert result["status"] == "PASS"
        assert result["output"] == "plain text output"

    def test_non_json_stdout_returncode_nonzero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "plain text output"
        mock_proc.stderr = "error details"
        mock_proc.returncode = 1
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "fail"])
        assert result["status"] == "FAIL"
        assert result["error"] == "error details"

    def test_no_stdout_returncode_zero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "ok"])
        assert result["status"] == "PASS"

    def test_no_stdout_returncode_nonzero(self):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = "fatal"
        mock_proc.returncode = 2
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("test", ["echo", "fail"])
        assert result["status"] == "FAIL"

    def test_timeout_expired(self):
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=10)):
            result = mfs.run_stage("test", ["sleep", "100"])
        assert result["status"] == "TIMEOUT"

    def test_generic_exception(self):
        with patch.object(subprocess, "run", side_effect=RuntimeError("unexpected")):
            result = mfs.run_stage("test", ["bad"])
        assert result["status"] == "ERROR"
        assert "unexpected" in result["error"]

    def test_stage_name_and_command_in_result(self):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_proc):
            result = mfs.run_stage("My Stage", ["python3", "-c", "print('hi')"])
        assert result["stage"] == "My Stage"
        assert "python3" in result["command"]


class TestRunComplianceScan:
    def test_basic(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            result = mfs.run_compliance_scan("/tmp/cards")
        assert result["status"] == "PASS"
        mock_rs.assert_called_once()
        args = mock_rs.call_args[0]
        assert "compliance_scan.py" in args[1]
        assert "--dir" in args[1]
        assert "/tmp/cards" in args[1]

    def test_with_schema(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_compliance_scan("/tmp/cards", schema_path="/tmp/schema.json")
        args = mock_rs.call_args[0]
        assert "--schema" in args[1]
        assert "/tmp/schema.json" in args[1]

    def test_with_block(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_compliance_scan("/tmp/cards", block=True)
        args = mock_rs.call_args[0]
        assert "--block" in args[1]


class TestRunMockLlmTest:
    def test_basic(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_mock_llm_test("/tmp/tasks.json")
        args = mock_rs.call_args[0]
        assert "mock_llm.py" in args[1]
        assert "--task-file" in args[1]
        assert "/tmp/tasks.json" in args[1]

    def test_with_policy(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_mock_llm_test("/tmp/tasks.json", policy_path="/tmp/policy.yaml")
        args = mock_rs.call_args[0]
        assert "--policy" in args[1]
        assert "/tmp/policy.yaml" in args[1]


class TestRunMockCalibration:
    def test_basic(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_mock_calibration("/tmp/golden", "/tmp/mock")
        args = mock_rs.call_args[0]
        assert "mock_calibrate.py" in args[1]
        assert "--golden-dir" in args[1]
        assert "--mock-dir" in args[1]

    def test_with_all_thresholds(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_mock_calibration("/tmp/a", "/tmp/b", thresholds={
                "sequence_similarity": 0.8,
                "set_similarity": 0.7,
                "param_match_rate": 0.9,
            })
        args = mock_rs.call_args[0][1]
        assert "--threshold-seq" in args
        assert "0.8" in args
        assert "--threshold-set" in args
        assert "0.7" in args
        assert "--threshold-param" in args
        assert "0.9" in args

    def test_with_partial_thresholds(self):
        with patch.object(mfs, "run_stage", return_value={"status": "PASS"}) as mock_rs:
            mfs.run_mock_calibration("/tmp/a", "/tmp/b", thresholds={"sequence_similarity": 0.9})
        args = mock_rs.call_args[0][1]
        assert "--threshold-seq" in args
        assert "--threshold-set" not in args
        assert "--threshold-param" not in args


class TestPrintSummary:
    def _make_report(self, overall_status="PASS", stage_status="PASS", error=None):
        stage = {"stage": "Layer 1", "status": stage_status, "duration_ms": 100}
        if error:
            stage["error"] = error
        return {
            "standard": "MAS-TS-001",
            "version": "v2.1",
            "mode": "fast-screen",
            "started_at": "2026-01-01T00:00:00.000Z",
            "total_duration_ms": 100,
            "overall_status": overall_status,
            "stages": [stage],
        }

    def test_pass_logs_info(self, caplog):
        caplog.set_level(logging.INFO)
        with patch.object(mfs, "console") as mock_console:
            mfs.print_summary(self._make_report("PASS", "PASS"))
        assert "passed" in caplog.text

    def test_fail_logs_error(self, caplog):
        caplog.set_level(logging.ERROR)
        with patch.object(mfs, "console") as mock_console:
            mfs.print_summary(self._make_report("FAIL", "FAIL"))
        assert "FAILED" in caplog.text

    def test_warning_logs_warning(self, caplog):
        caplog.set_level(logging.WARNING)
        with patch.object(mfs, "console") as mock_console:
            mfs.print_summary(self._make_report("WARNING", "PASS"))
        assert "warnings" in caplog.text

    def test_stage_with_error_shown(self):
        with patch.object(mfs, "console") as mock_console:
            mfs.print_summary(self._make_report("FAIL", "FAIL", error="something broke"))
        assert mock_console.print.called


class TestMainFunction:
    def test_main_with_minimal_args(self):
        test_args = ["mas_fast_screen.py", "--cards-dir", "/tmp/cards"]
        with patch.object(sys, "argv", test_args), \
             patch.object(mfs, "run_stage", return_value={"status": "PASS", "duration_ms": 10, "stage": "Layer 1: Compliance Scan", "command": "test", "output": None, "error": None}), \
             patch.object(mfs, "console"), \
             patch.object(Path, "exists", return_value=True), \
             patch("builtins.open"), \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "parent"):
            with pytest.raises(SystemExit) as exc:
                mfs.main()
            assert exc.value.code == 0

    def test_main_with_task_file(self):
        test_args = ["mas_fast_screen.py", "--cards-dir", "/tmp/cards", "--task-file", "/tmp/tasks.json"]
        with patch.object(sys, "argv", test_args), \
             patch.object(mfs, "run_stage", return_value={"status": "PASS", "duration_ms": 10, "stage": "test", "command": "test", "output": None, "error": None}), \
             patch.object(mfs, "console"), \
             patch.object(Path, "exists", return_value=True), \
             patch("builtins.open"), \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "parent"):
            with pytest.raises(SystemExit):
                mfs.main()

    def test_main_with_output(self):
        test_args = ["mas_fast_screen.py", "--cards-dir", "/tmp/cards", "--output", "/tmp/report.json"]
        with patch.object(sys, "argv", test_args), \
             patch.object(mfs, "run_stage", return_value={"status": "PASS", "duration_ms": 10, "stage": "test", "command": "test", "output": None, "error": None}), \
             patch.object(mfs, "console"), \
             patch.object(Path, "exists", return_value=True), \
             patch("builtins.open") as mock_open, \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "parent"):
            with pytest.raises(SystemExit):
                mfs.main()
            mock_open.assert_called()

    def test_main_with_golden_and_mock(self):
        test_args = ["mas_fast_screen.py", "--cards-dir", "/tmp/cards", "--golden-dir", "/tmp/golden", "--mock-dir", "/tmp/mock"]
        with patch.object(sys, "argv", test_args), \
             patch.object(mfs, "run_stage", return_value={"status": "PASS", "duration_ms": 10, "stage": "test", "command": "test", "output": None, "error": None}), \
             patch.object(mfs, "console"), \
             patch.object(Path, "exists", return_value=True), \
             patch("builtins.open"), \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "parent"):
            with pytest.raises(SystemExit):
                mfs.main()

    def test_main_with_timeout_arg(self):
        test_args = ["mas_fast_screen.py", "--cards-dir", "/tmp/cards", "--timeout", "600"]
        with patch.object(sys, "argv", test_args), \
             patch.object(mfs, "run_stage", return_value={"status": "PASS", "duration_ms": 10, "stage": "test", "command": "test", "output": None, "error": None}), \
             patch.object(mfs, "console"), \
             patch.object(Path, "exists", return_value=True), \
             patch("builtins.open"), \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "parent"):
            with pytest.raises(SystemExit):
                mfs.main()
