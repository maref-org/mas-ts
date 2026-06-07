# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cs = load_module("compliance_scan", Path(__file__).parent.parent / "compliance_scan.py")


class TestResolveEndpointRegion:
    def test_openai_us(self):
        assert cs.resolve_endpoint_region("https://api.openai.com/v1/chat") == "US"

    def test_anthropic_us(self):
        assert cs.resolve_endpoint_region("https://api.anthropic.com/v1/messages") == "US"

    def test_dashscope_cn(self):
        assert cs.resolve_endpoint_region("https://dashscope.aliyuncs.com/compatible-mode/v1") == "CN"

    def test_deepseek_cn(self):
        assert cs.resolve_endpoint_region("https://api.deepseek.com/v1/chat") == "CN"

    def test_unknown_endpoint(self):
        assert cs.resolve_endpoint_region("https://custom.api.com/v1") == "UNKNOWN"

    def test_empty_endpoint(self):
        assert cs.resolve_endpoint_region("") == "UNKNOWN"

    def test_localhost(self):
        assert cs.resolve_endpoint_region("http://localhost:8000/v1") == "LOCAL"


class TestCheckEndpointLocation:
    def test_cn_overseas_detected(self):
        passed, risk, _ = cs.check_endpoint_location("https://api.openai.com/v1", "CN")
        assert not passed
        assert risk == "HIGH"

    def test_local_ok(self):
        passed, risk, _ = cs.check_endpoint_location("http://localhost:8000", "LOCAL")
        assert passed
        assert risk == "LOW"

    def test_cn_domestic_ok(self):
        passed, risk, _ = cs.check_endpoint_location("https://dashscope.aliyuncs.com", "CN")
        assert passed

    def test_local_non_local_warning(self):
        passed, risk, _ = cs.check_endpoint_location("https://api.openai.com", "LOCAL")
        assert not passed
        assert risk == "MEDIUM"

    def test_empty_endpoint(self):
        passed, risk, _ = cs.check_endpoint_location("", "CN")
        assert not passed
        assert risk == "CRITICAL"

    def test_local_localhost_ok(self):
        passed, risk, _ = cs.check_endpoint_location("http://127.0.0.1:8000", "LOCAL")
        assert passed


class TestCheckPromptRot:
    def test_no_brv_issues_warning(self, monkeypatch):
        monkeypatch.setattr(cs, "PROMPT_ROT_MAX_DAYS", 90)
        card = {"capabilities": [{"skill_id": "test_skill"}]}
        issues = cs.check_prompt_rot(card)
        assert len(issues) == 1
        assert "missing business_rule_version" in issues[0]["msg"]

    def test_recent_brv_no_issue(self, monkeypatch):
        monkeypatch.setattr(cs, "PROMPT_ROT_MAX_DAYS", 90)
        card = {"capabilities": [{"skill_id": "test_skill", "business_rule_version": "2026-05-01"}]}
        issues = cs.check_prompt_rot(card)
        assert len(issues) == 0

    def test_expired_brv_warning(self, monkeypatch):
        old_date = "1999-01-01"
        monkeypatch.setattr(cs, "PROMPT_ROT_MAX_DAYS", 90)
        card = {"capabilities": [{"skill_id": "test_skill", "business_rule_version": old_date}]}
        issues = cs.check_prompt_rot(card)
        assert len(issues) == 1
        assert "prompt rot risk" in issues[0]["msg"].lower()

    def test_invalid_format(self):
        card = {"capabilities": [{"skill_id": "test_skill", "business_rule_version": "not-a-date"}]}
        issues = cs.check_prompt_rot(card)
        assert len(issues) == 1
        assert "not YYYY-MM-DD" in issues[0]["msg"]
