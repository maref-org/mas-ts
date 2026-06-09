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


cs_mod = load_module(
    "compliance_sidecar", Path(__file__).parent.parent / "compliance_sidecar.py"
)


@pytest.fixture
def cn_sidecar(tmp_path):
    card_data = {"name": "test-agent", "compliance": {"data_residency": "CN"}}
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card_data))
    return cs_mod.ComplianceSidecar(str(p))


@pytest.fixture
def us_sidecar(tmp_path):
    card_data = {"name": "us-agent", "compliance": {"data_residency": "US"}}
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card_data))
    return cs_mod.ComplianceSidecar(str(p))


class TestComplianceSidecar:
    def test_cn_blocked_openai(self, cn_sidecar):
        allowed, reason = cn_sidecar.check_url("https://api.openai.com/v1/chat")
        assert not allowed
        assert "BLOCKED" in reason

    def test_cn_allowed_dashscope(self, cn_sidecar):
        allowed, reason = cn_sidecar.check_url("https://dashscope.aliyuncs.com/v1")
        assert allowed
        assert "ALLOWED" in reason

    def test_localhost_allowed(self, cn_sidecar):
        allowed, reason = cn_sidecar.check_url("http://localhost:8000")
        assert allowed

    def test_us_allowed_openai(self, us_sidecar):
        allowed, reason = us_sidecar.check_url("https://api.openai.com/v1")
        assert allowed
        assert "ALLOWED" in reason

    def test_unknown_domain_allowed_with_warning(self, cn_sidecar):
        allowed, reason = cn_sidecar.check_url("https://custom-unknown-api.com/v1")
        assert allowed
        assert "UNKNOWN" in reason

    def test_cn_blocked_anthropic(self, cn_sidecar):
        allowed, reason = cn_sidecar.check_url("https://api.anthropic.com/v1/messages")
        assert not allowed

    def test_sidecar_loads_agent_name(self, tmp_path):
        card_data = {"name": "my-agent", "compliance": {"data_residency": "US"}}
        p = tmp_path / "card.json"
        p.write_text(json.dumps(card_data))
        sc = cs_mod.ComplianceSidecar(str(p))
        assert sc.agent_name == "my-agent"
