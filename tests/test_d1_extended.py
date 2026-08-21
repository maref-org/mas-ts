# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for D1 extended compliance checks (11-15)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.domains.d1_compliance import check_license_compatibility


class TestLicenseCheck:
    def test_no_dependencies(self):
        findings = check_license_compatibility({})
        assert len(findings) == 1
        assert findings[0]["severity"] == "INFO"

    def test_clean_dependencies(self):
        card = {"dependencies": [{"name": "requests", "license": "Apache-2.0"}]}
        findings = check_license_compatibility(card)
        assert len(findings) == 1
        assert findings[0]["severity"] == "INFO"

    def test_restrictive_license_warning(self):
        card = {
            "dependencies": [
                {"name": "some-lib", "license": "AGPL-3.0-only"},
            ]
        }
        findings = check_license_compatibility(card)
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARNING"
        assert "AGPL" in findings[0]["detail"]

    def test_mixed_licenses(self):
        card = {
            "dependencies": [
                {"name": "safe-lib", "license": "MIT"},
                {"name": "risky-lib", "license": "SSPL-1.0"},
            ]
        }
        findings = check_license_compatibility(card)
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARNING"
        assert "SSPL" in findings[0]["detail"]

    def test_check_id_is_1_15(self):
        findings = check_license_compatibility(
            {"dependencies": [{"name": "test", "license": "MIT"}]}
        )
        assert findings[0]["check"] == "1.15"
