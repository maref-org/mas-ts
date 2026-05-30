import importlib.util
import json
from pathlib import Path

import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cs = load_module("compliance_scan", Path(__file__).parent.parent / "compliance_scan.py")


class TestScanAgentCard:
    def test_missing_data_residency(self, tmp_path):
        card = {"name": "test", "compliance": {}}
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        assert any("Missing data_residency" in i["msg"] for i in issues)

    def test_missing_capabilities(self, tmp_path):
        card = {"name": "test", "compliance": {"data_residency": "CN", "model_backend_location": "CN"}}
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        assert any("No capabilities declared" in i["msg"] for i in issues)

    def test_fraudulent_cross_border(self, tmp_path):
        card = {
            "name": "test",
            "compliance": {"data_residency": "CN", "model_backend_location": "US", "cross_border": False},
            "capabilities": []
        }
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        assert any("fraudulent" in i["msg"].lower() for i in issues)

    def test_invalid_json_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json")
        issues = cs.scan_agent_card(str(p))
        assert any("not valid JSON" in i["msg"] for i in issues)

    def test_compliant_card(self, tmp_path):
        card = {
            "name": "compliant",
            "model_backend": {"endpoint": "https://dashscope.aliyuncs.com/v1"},
            "compliance": {"data_residency": "CN", "model_backend_location": "CN"},
            "capabilities": [{"skill_id": "bash", "business_rule_version": "2026-05-01"}]
        }
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        critical_high = [i for i in issues if i["level"] in ("CRITICAL", "HIGH")]
        assert len(critical_high) == 0

    def test_endpoint_mismatch(self, tmp_path):
        card = {
            "name": "test", "model_backend": {"endpoint": "https://api.openai.com/v1"},
            "compliance": {"data_residency": "CN", "model_backend_location": "CN"},
            "capabilities": [{"skill_id": "bash"}]
        }
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        assert any("overseas" in i["msg"].lower() for i in issues)

    def test_residency_backend_mismatch(self, tmp_path):
        card = {
            "name": "test",
            "compliance": {"data_residency": "CN", "model_backend_location": "US"},
            "capabilities": [{"skill_id": "bash"}]
        }
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card))
        issues = cs.scan_agent_card(str(p))
        assert any("cross-border risk" in i["msg"].lower() for i in issues)


class TestScanDirectory:
    def test_empty_directory(self, tmp_path):
        results = cs.scan_directory(str(tmp_path))
        assert len(results) == 0

    def test_mixed_results(self, tmp_path):
        good = {"name": "good", "model_backend": {"endpoint": "https://dashscope.aliyuncs.com/v1"}, "capabilities": [{"skill_id": "bash", "business_rule_version": "2026-05-01"}], "compliance": {"data_residency": "CN", "model_backend_location": "CN"}}
        bad = {"name": "bad"}
        (tmp_path / "good.json").write_text(json.dumps(good))
        (tmp_path / "bad.json").write_text(json.dumps(bad))
        results = cs.scan_directory(str(tmp_path))
        assert len(results) == 2
        passed = [r for r in results if r["passed"]]
        failed = [r for r in results if not r["passed"]]
        assert len(passed) == 1
        assert len(failed) >= 1


class TestValidateSchema:
    def test_no_jsonschema(self, monkeypatch):
        monkeypatch.setattr(cs, "HAS_JSONSCHEMA", False)
        issues = cs.validate_schema({}, None)
        assert any("jsonschema library not installed" in i["msg"] for i in issues)

    def test_schema_not_found(self):
        issues = cs.validate_schema({}, "/nonexistent/schema.json")
        assert any("Schema file not found" in i["msg"] for i in issues)


class TestCheckEndpointLocationExtended:
    def test_cn_overseas_azure_detected(self):
        passed, risk, _ = cs.check_endpoint_location("https://mycompany.azure.com/v1", "CN")
        assert not passed
        assert risk == "HIGH"

    def test_local_us_blocked(self):
        passed, risk, _ = cs.check_endpoint_location("http://127.0.0.1:8000/v1", "US")
        assert not passed
        assert risk in ("HIGH", "MEDIUM")
