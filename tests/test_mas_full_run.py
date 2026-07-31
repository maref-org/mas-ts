# SPDX-FileCopyrightText: 2026 maref-org
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
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_write",
            "description": "write files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["write"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "glob",
            "description": "glob",
            "input_schema": {},
            "output_schema": {},
            "examples": ["glob"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "grep",
            "description": "grep",
            "input_schema": {},
            "output_schema": {},
            "examples": ["grep"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_search",
            "description": "search",
            "input_schema": {},
            "output_schema": {},
            "examples": ["search"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["fetch"],
            "business_rule_version": "2026-07-15",
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


class TestEscalationThresholds:
    def test_thresholds_defined(self):
        from mas_full_run import ESCALATION_THRESHOLDS

        assert ESCALATION_THRESHOLDS == {"L0": 60, "L1": 60, "L2": 50, "L3": 50}


class TestSelectLevelsEscalate:
    def test_skips_on_low_score(self):
        from mas_full_run import _select_levels_escalate

        results = {"L0": {"score": 55.0}}
        selected = _select_levels_escalate(results)
        assert selected == []

    def test_proceeds_on_pass(self):
        from mas_full_run import _select_levels_escalate

        results = {"L0": {"score": 85.0}}
        selected = _select_levels_escalate(results)
        assert selected == ["L1"]

    def test_full_chain(self):
        from mas_full_run import _select_levels_escalate

        results = {
            "L0": {"score": 85.0},
            "L1": {"score": 80.0},
            "L2": {"score": 75.0},
            "L3": {"score": 70.0},
        }
        selected = _select_levels_escalate(results)
        assert selected == ["L1", "L2", "L3", "L4"]

    def test_gate_fails_at_l2(self):
        from mas_full_run import _select_levels_escalate

        results = {
            "L0": {"score": 85.0},
            "L1": {"score": 80.0},
            "L2": {"score": 45.0},
        }
        selected = _select_levels_escalate(results)
        assert selected == []  # L2 below threshold, stop

    def test_empty_results(self):
        from mas_full_run import _select_levels_escalate

        selected = _select_levels_escalate({})
        assert selected == []


class TestCLIFlags:
    def test_default_mode(self):
        from mas_full_run import _setup_parser

        parser = _setup_parser()
        args = parser.parse_args(["--card", "dummy.json"])
        assert args.mode == "full"
        assert args.converge is False
        assert args.max_iterations == 5
        assert args.convergence_delta == 0.5


class TestConvergeMode:
    def test_converge_preserves_domain_scores_for_report(self, monkeypatch, tmp_path):
        output = tmp_path / "report.json"

        def runner(card, tasks=None):
            return {
                "level": "L1",
                "name": "Stub",
                "score": 80.0,
                "grade": "B-",
                "verdict": "APPROVED",
                "domain_scores": {"d1": 80.0},
                "domains": {},
                "findings": [],
            }

        monkeypatch.setattr(mfr, "load_card", lambda path: SAMPLE_CARD)
        monkeypatch.setattr(mfr, "load_tasks", lambda path: None)
        monkeypatch.setattr(mfr, "print_report", lambda report: None)
        monkeypatch.setitem(mfr.LEVEL_RUNNERS, "L1", runner)
        monkeypatch.setattr(
            "sys.argv",
            [
                "mas_full_run.py",
                "--card",
                "dummy.json",
                "--level",
                "L1",
                "--converge",
                "--max-iterations",
                "3",
                "--output",
                str(output),
            ],
        )

        mfr.main()
        report = json.loads(output.read_text())
        assert report["overall"]["score"] == 80.0
        assert report["levels"][0]["domain_scores"] == {"d1": 80.0}

    def test_l4_converge_passes_card_to_runner(self, monkeypatch, tmp_path):
        output = tmp_path / "report.json"
        received_cards = []

        def runner(card=None):
            received_cards.append(card)
            return {
                "level": "L4",
                "name": "Evolution",
                "score": 80.0,
                "grade": "B-",
                "domain_scores": {"d5": 80.0},
                "domains": {},
                "findings": [],
            }

        monkeypatch.setattr(mfr, "load_card", lambda path: SAMPLE_CARD)
        monkeypatch.setattr(mfr, "load_tasks", lambda path: None)
        monkeypatch.setattr(mfr, "print_report", lambda report: None)
        monkeypatch.setitem(mfr.LEVEL_RUNNERS, "L4", runner)
        monkeypatch.setattr(
            "sys.argv",
            [
                "mas_full_run.py",
                "--card",
                "dummy.json",
                "--level",
                "L4",
                "--converge",
                "--max-iterations",
                "3",
                "--output",
                str(output),
            ],
        )

        mfr.main()
        report = json.loads(output.read_text())
        assert received_cards == [SAMPLE_CARD, SAMPLE_CARD, SAMPLE_CARD]
        assert report["levels"][0]["domain_scores"] == {"d5": 80.0}
