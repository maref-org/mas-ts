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

cs_mod = load_module("compliance_sidecar", Path(__file__).parent.parent / "compliance_sidecar.py")


class TestResolveRegion:
    def test_exact_match(self, tmp_path):
        card = {"name": "t", "compliance": {"data_residency": "CN"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        assert sc._resolve_region("api.openai.com") == "US"
        assert sc._resolve_region("dashscope.aliyuncs.com") == "CN"

    def test_suffix_match(self, tmp_path):
        card = {"name": "t", "compliance": {"data_residency": "CN"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        assert sc._resolve_region("api.openai.com") == "US"

    def test_unknown_domain(self, tmp_path):
        card = {"name": "t", "compliance": {"data_residency": "CN"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        assert sc._resolve_region("unknown.example.com") == "UNKNOWN"

    def test_localhost(self, tmp_path):
        card = {"name": "t", "compliance": {"data_residency": "CN"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        assert sc._resolve_region("localhost") == "LOCAL"


class TestEUResidency:
    def test_eu_allows_eu(self, tmp_path):
        card = {"name": "eu", "compliance": {"data_residency": "EU"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        allowed, reason = sc.check_url("https://api.mistral.ai/v1")
        assert allowed

    def test_eu_blocks_us(self, tmp_path):
        card = {"name": "eu", "compliance": {"data_residency": "EU"}}
        p = tmp_path / "c.json"
        p.write_text(json.dumps(card))
        sc = cs_mod.ComplianceSidecar(str(p))
        allowed, reason = sc.check_url("https://api.openai.com/v1")
        assert not allowed


class TestInvalidCard:
    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json")
        with pytest.raises(SystemExit):
            cs_mod.ComplianceSidecar(str(p))
