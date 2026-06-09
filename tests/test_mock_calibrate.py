# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path

import pytest


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = load_module("mock_calibrate", Path(__file__).parent.parent / "mock_calibrate.py")


class TestExtractToolSignature:
    def test_tool_call_event(self):
        event = {
            "action": {
                "type": "tool_call",
                "tool_id": "read_file",
                "input": {"path": "/tmp"},
            }
        }
        assert mc.extract_tool_signature(event) == "read_file:path"

    def test_non_tool_call_event(self):
        assert mc.extract_tool_signature({"action": {"type": "task_start"}}) is None

    def test_multiple_params(self):
        event = {
            "action": {
                "type": "tool_call",
                "tool_id": "search_flight",
                "input": {"origin": "BJS", "dest": "SHA"},
            }
        }
        assert mc.extract_tool_signature(event) == "search_flight:dest,origin"

    def test_no_input(self):
        event = {"action": {"type": "tool_call", "tool_id": "noop", "input": {}}}
        assert mc.extract_tool_signature(event) == "noop:"


class TestCompareTrajectories:
    @pytest.fixture
    def golden(self):
        return [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "search_flight",
                    "input": {"origin": "BJS", "dest": "SHA"},
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "book_ticket",
                    "input": {"flight_no": "CA1234", "passenger": "Zhang"},
                }
            },
        ]

    @pytest.fixture
    def mock_identical(self):
        return [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "search_flight",
                    "input": {"origin": "BJS", "dest": "SHA"},
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "book_ticket",
                    "input": {"flight_no": "CA1234", "passenger": "Zhang"},
                }
            },
        ]

    def test_identical_trajectories_no_drift(self, golden, mock_identical):
        result = mc.compare_trajectories(golden, mock_identical)
        assert result["sequence_similarity"] == 1.0
        assert result["set_similarity"] == 1.0
        assert result["param_match_rate"] == 1.0
        assert not result["drift_detected"]

    def test_different_trajectories_drift_detected(self, golden):
        different = [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "get_profile",
                    "input": {"user_id": "1"},
                }
            },
        ]
        result = mc.compare_trajectories(golden, different)
        assert result["drift_detected"]

    def test_empty_golden(self):
        result = mc.compare_trajectories(
            [], [{"action": {"type": "tool_call", "tool_id": "x", "input": {}}}]
        )
        assert result["param_match_rate"] == 0.0

    def test_custom_thresholds(self):
        result = mc.compare_trajectories(
            [{"action": {"type": "tool_call", "tool_id": "a", "input": {}}}],
            [{"action": {"type": "tool_call", "tool_id": "b", "input": {}}}],
            thresholds={
                "sequence_similarity": 0.0,
                "set_similarity": 0.0,
                "param_match_rate": 0.0,
            },
        )
        assert not result["drift_detected"]

    def test_routing_decision_match(self):
        golden = [
            {
                "action": {"type": "tool_call", "tool_id": "a", "input": {}},
                "orchestration": {
                    "routing_decision": "auto",
                    "routing_reason": "match",
                },
            }
        ]
        mock = [
            {
                "action": {"type": "tool_call", "tool_id": "a", "input": {}},
                "orchestration": {
                    "routing_decision": "auto",
                    "routing_reason": "match",
                },
            }
        ]
        result = mc.compare_trajectories(golden, mock)
        assert result["route_match_rate"] == 1.0


class TestLoadTrajectory:
    def test_events_dict(self, tmp_path):
        p = tmp_path / "traj.json"
        data = {"events": [{"event_type": "task_start"}]}
        p.write_text(json.dumps(data))
        result = mc.load_trajectory(str(p))
        assert result == [{"event_type": "task_start"}]

    def test_trajectory_dict(self, tmp_path):
        p = tmp_path / "traj.json"
        data = {"trajectory": [{"event_type": "tool_call"}]}
        p.write_text(json.dumps(data))
        result = mc.load_trajectory(str(p))
        assert result == [{"event_type": "tool_call"}]

    def test_list_directly(self, tmp_path):
        p = tmp_path / "traj.json"
        data = [{"event_type": "task_start"}, {"event_type": "task_complete"}]
        p.write_text(json.dumps(data))
        result = mc.load_trajectory(str(p))
        assert len(result) == 2
