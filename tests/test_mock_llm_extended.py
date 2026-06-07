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

ml = load_module("mock_llm", Path(__file__).parent.parent / "mock_llm.py")


class TestProcessTaskFile:
    def test_list_of_strings(self, tmp_path):
        tasks = ["query_order", "search_flight"]
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        results = ml.process_task_file(str(p))
        assert len(results) == 2

    def test_dict_with_tasks_key(self, tmp_path):
        tasks = {"tasks": ["query_order", "search_flight"]}
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        results = ml.process_task_file(str(p))
        assert len(results) == 2

    def test_task_objects(self, tmp_path):
        tasks = [{"description": "query_order"}, {"description": "search_flight"}]
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        results = ml.process_task_file(str(p))
        assert len(results) == 2

    def test_output_to_dir(self, tmp_path):
        tasks = ["query_order", "search_flight"]
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        out_dir = tmp_path / "outputs"
        results = ml.process_task_file(str(p), output_dir=str(out_dir))
        assert out_dir.exists()
        files = list(out_dir.glob("*.json"))
        assert len(files) == 2

    def test_with_policy(self, tmp_path):
        import yaml
        tasks = ["query_order"]
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(tasks))
        policy = tmp_path / "policy.yaml"
        policy.write_text(yaml.dump({"thresholds": {"seq": 0.8}}))
        results = ml.process_task_file(str(p), policy_path=str(policy))
        assert len(results) == 1


class TestGenerateMockTrajectoryExtended:
    def test_with_agent_card(self):
        card = {"agent_id": "test-agent", "compliance": {"data_residency": "CN"}}
        result = ml.generate_mock_trajectory("query_order", agent_card=card)
        assert result["events"][0]["agent"]["agent_id"] == "test-agent"
        assert result["events"][0]["agent"]["data_residency"] == "CN"

    def test_defaults_when_no_card(self):
        result = ml.generate_mock_trajectory("query_order")
        assert result["events"][0]["agent"]["data_residency"] == "LOCAL"

    def test_mock_trajectory_structure(self):
        result = ml.generate_mock_trajectory("query_order")
        events = result["events"]
        event_types = [e["event_type"] for e in events]
        assert "task_start" in event_types
        assert "agent_action" in event_types
