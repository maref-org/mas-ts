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


SAMPLE_CARD = {
    "agent_id": "test-agent-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "schema_version": "v1.2",
    "card_version": "1.2",
    "provider": "test",
    "model": "gpt-4",
    "model_backend": {"endpoint": "https://api.example.com/v1", "model": "gpt-4"},
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run commands",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "file_write",
            "description": "write files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["write"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "glob",
            "description": "glob",
            "input_schema": {},
            "output_schema": {},
            "examples": ["glob"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "grep",
            "description": "grep",
            "input_schema": {},
            "output_schema": {},
            "examples": ["grep"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_search",
            "description": "search",
            "input_schema": {},
            "output_schema": {},
            "examples": ["search"],
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["fetch"],
            "business_rule_version": "2026-05-01",
        },
    ],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
    "compliance": {
        "data_residency": "US",
        "cross_border_transfer": False,
        "audit_trail_required": True,
        "end_user_identification": True,
        "model_backend_location": "US",
    },
    "constitution": {
        "envelope": {"version": "1.0", "jurisdiction": "US-CA"},
        "health_state": "healthy",
        "heartbeat_interval_seconds": 15,
    },
    "endpoints": {"a2a": "https://a2a.example.com", "mcp": "https://mcp.example.com"},
    "dependencies": ["git", "nodejs"],
    "orchestration_hints": {
        "agent_count": 3,
        "parallel_execution": True,
        "parallel_safe": True,
        "stateful": True,
        "preferred_role": "worker",
    },
    "message_format": {"protocol": "json-rpc-2.0", "transport": "stdio"},
}


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


class TestGenerateReport:
    def test_report_has_correct_keys(self):
        report = mfr.generate_report(SAMPLE_CARD, [])
        assert report["standard"] == "MAS-TS-001"
        assert report["version"] == "v3.0"
        assert report["mode"] == "full-run"
        assert "overall" in report
        assert "levels" in report
        assert "findings_summary" in report
        assert "target_agent" in report

    def test_target_agent_from_card(self):
        report = mfr.generate_report(SAMPLE_CARD, [])
        assert report["target_agent"]["agent_id"] == "test-agent-001"
        assert report["target_agent"]["name"] == "TestAgent"

    def test_levels_included(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {"level": "L0", "status": "PASS", "findings": []},
                {"level": "L1", "score": 85, "findings": []},
            ],
        )
        assert len(report["levels"]) == 2

    def test_findings_summary_empty(self):
        report = mfr.generate_report(SAMPLE_CARD, [])
        assert report["findings_summary"]["total"] == 0

    def test_findings_summary_counts(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {
                    "level": "L1",
                    "score": 50,
                    "findings": [
                        {"severity": "CRITICAL", "category": "test", "detail": "bad"},
                        {"severity": "HIGH", "category": "test", "detail": "high"},
                        {"severity": "WARNING", "category": "test", "detail": "warn"},
                    ],
                }
            ],
        )
        assert report["findings_summary"]["critical"] == 1
        assert report["findings_summary"]["high"] == 1
        assert report["findings_summary"]["warning"] == 1

    def test_verdict_approved(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {
                    "level": "L3",
                    "score": 85,
                    "findings": [],
                    "domain_scores": {"d1": 90, "d2": 85, "d3": 80, "d4": 85, "d5": 85},
                }
            ],
        )
        assert report["overall"]["verdict"] == "APPROVED"

    def test_verdict_blocked_with_critical(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {
                    "level": "L1",
                    "score": 50,
                    "findings": [
                        {
                            "severity": "CRITICAL",
                            "category": "test",
                            "detail": "blocker",
                        }
                    ],
                    "domain_scores": {"d1": 50},
                }
            ],
        )
        assert report["overall"]["verdict"] == "BLOCKED"

    def test_verdict_conditional(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {
                    "level": "L1",
                    "score": 60,
                    "findings": [],
                    "domain_scores": {"d1": 60, "d2": 60},
                }
            ],
        )
        assert report["overall"]["verdict"] == "CONDITIONAL"

    def test_domain_scores_aggregated(self):
        report = mfr.generate_report(
            SAMPLE_CARD,
            [
                {
                    "level": "L1",
                    "score": 80,
                    "findings": [],
                    "domain_scores": {"d1": 90, "d2": 85, "d3": 80},
                },
                {
                    "level": "L2",
                    "score": 80,
                    "findings": [],
                    "domain_scores": {"d4": 75},
                },
            ],
        )
        assert "d1" in report["levels"][0].get("domain_scores", {})

    def test_source_dir_in_report(self):
        report = mfr.generate_report(SAMPLE_CARD, [], source_dir="/tmp/src")
        assert report["target_agent"]["source_dir"] == "/tmp/src"


class TestPrintReport:
    def test_print_approved(self, capsys):
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "full-run",
            "evaluated_at": "2026-06-09T00:00:00.000Z",
            "target_agent": {
                "agent_id": "test-001",
                "name": "Test",
                "version": "1.0",
                "source_dir": None,
            },
            "overall": {
                "score": 85,
                "grade": "B",
                "emoji": "🟢",
                "verdict": "APPROVED",
            },
            "levels": [
                {
                    "level": "L1",
                    "name": "Standard",
                    "score": 85,
                    "grade": "B",
                    "findings": [],
                }
            ],
            "findings_summary": {
                "critical": 0,
                "high": 0,
                "warning": 0,
                "info": 0,
                "total": 0,
            },
        }
        mfr.print_report(report)
        captured = capsys.readouterr()
        assert "APPROVED" in captured.out
        assert "MAS-TS-001" in captured.out

    def test_print_blocked(self, capsys):
        report = {
            "standard": "MAS-TS-001",
            "version": "v3.0",
            "mode": "full-run",
            "evaluated_at": "2026-06-09T00:00:00.000Z",
            "target_agent": {
                "agent_id": "test-001",
                "name": "Test",
                "version": "1.0",
                "source_dir": None,
            },
            "overall": {
                "score": 40,
                "grade": "F",
                "emoji": "🔴",
                "verdict": "BLOCKED",
            },
            "levels": [
                {
                    "level": "L1",
                    "name": "Standard",
                    "score": 40,
                    "grade": "F",
                    "findings": [],
                }
            ],
            "findings_summary": {
                "critical": 2,
                "high": 0,
                "warning": 0,
                "info": 0,
                "total": 2,
            },
        }
        mfr.print_report(report)
        captured = capsys.readouterr()
        assert "BLOCKED" in captured.out
