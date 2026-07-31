# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = load_module("mock_calibrate", Path(__file__).parent.parent / "mock_calibrate.py")


class TestCalibratePair:
    def test_identical_files(self, tmp_path):
        traj = [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}]
        golden = tmp_path / "golden.json"
        mock = tmp_path / "mock.json"
        golden.write_text(json.dumps(traj))
        mock.write_text(json.dumps(traj))
        result = mc.calibrate_pair(str(golden), str(mock))
        assert not result["drift_detected"]

    def test_different_files(self, tmp_path):
        golden_data = [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}]
        mock_data = [{"action": {"type": "tool_call", "tool_id": "b", "input": {}}}]
        golden = tmp_path / "golden.json"
        mock = tmp_path / "mock.json"
        golden.write_text(json.dumps(golden_data))
        mock.write_text(json.dumps(mock_data))
        result = mc.calibrate_pair(str(golden), str(mock))
        assert result["drift_detected"]

    def test_files_with_names(self, tmp_path):
        golden_data = [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}]
        mock_data = [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}]
        golden = tmp_path / "golden.json"
        mock = tmp_path / "mock.json"
        golden.write_text(json.dumps(golden_data))
        mock.write_text(json.dumps(mock_data))
        result = mc.calibrate_pair(str(golden), str(mock))
        assert str(golden) in result["golden_file"]
        assert str(mock) in result["mock_file"]


class TestCalibrateDirectory:
    def test_skip_missing(self, tmp_path):
        golden = tmp_path / "only_golden.json"
        golden.write_text(
            json.dumps([{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}])
        )
        results = mc.calibrate_directory(
            str(tmp_path), str(tmp_path), skip_missing=True
        )
        assert len(results) == 1  # only the matched pair, no MISSING_MOCK

    def test_no_skip_missing(self, tmp_path):
        golden_dir = tmp_path / "golden"
        mock_dir = tmp_path / "mock"
        golden_dir.mkdir()
        mock_dir.mkdir()
        (golden_dir / "only_golden.json").write_text(
            json.dumps([{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}])
        )
        results = mc.calibrate_directory(
            str(golden_dir), str(mock_dir), skip_missing=False
        )
        assert any(r.get("status") == "MISSING_MOCK" for r in results)

    def test_perfect_match(self, tmp_path):
        data = [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}]
        (tmp_path / "task.json").write_text(json.dumps(data))
        (tmp_path / "mock" / "task.json").parent.mkdir()
        (tmp_path / "mock" / "task.json").write_text(json.dumps(data))
        results = mc.calibrate_directory(str(tmp_path), str(tmp_path / "mock"))
        assert any(r["status"] == "OK" for r in results)


class TestExtractRoutingDecision:
    def test_routing_decision_present(self):
        event = {
            "orchestration": {"routing_decision": "auto", "routing_reason": "match"}
        }
        assert mc.extract_routing_decision(event) == "match"

    def test_routing_decision_missing(self):
        event = {"orchestration": {}}
        assert mc.extract_routing_decision(event) is None

    def test_no_orchestration(self):
        event = {}
        assert mc.extract_routing_decision(event) is None
