# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Sidecar Runtime Security Bridge (Phase 2 v0.8.2).

15 tests covering all 5 public functions in mas_eval/harness/sidecar_bridge.py:
  - ingest_audit_chain: chain unwrap, flat-list passthrough, edge cases
  - verify_chain_integrity: valid chain, tamper detection, empty, missing secret
  - load_sidecar_log: list input, type rejection
  - run_runtime_injection_detection: clean/CRITICAL/HIGH scoring, prefix filter
  - evaluate_runtime_security: fusion weights, subscores, summary structure

Valid HMAC chains are generated via compliance_sidecar_v2.HMACAuditChain so the
test fixtures stay in lock-step with the production chain constructor.
"""

import importlib.util
from pathlib import Path

import pytest

from mas_eval.harness.sidecar_bridge import (
    evaluate_runtime_security,
    ingest_audit_chain,
    load_sidecar_log,
    run_runtime_injection_detection,
    verify_chain_integrity,
)


def _load_csv2():
    spec = importlib.util.spec_from_file_location(
        "compliance_sidecar_v2",
        Path(__file__).parent.parent / "compliance_sidecar_v2.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


csv2 = _load_csv2()

_SECRET = "test-bridge-secret"


def _make_chain(decisions: list[dict]) -> list[dict]:
    """Build a valid HMACAuditChain export from a list of decision dicts."""
    chain = csv2.HMACAuditChain(secret=_SECRET)
    for d in decisions:
        chain.add_entry(d)
    return chain.export()


def _decision(url: str, allowed: bool = True, findings: list | None = None) -> dict:
    """Minimal sidecar check_request-shaped decision dict."""
    return {
        "url": url,
        "domain_allowed": allowed,
        "findings": findings or [],
        "content_score": 100.0,
        "region": "US",
        "allowed": allowed,
    }


# ═══════════════════════════════════════════════════════════════
# ingest_audit_chain — 4 tests
# ═══════════════════════════════════════════════════════════════


class TestIngestAuditChain:
    def test_chain_shaped_unwraps_decision(self):
        """Chain export entries (with 'decision' wrapper) are unwrapped."""
        chain = _make_chain([_decision("https://a.com/v1"), _decision("https://b.com/v1")])
        events = ingest_audit_chain(chain)
        assert len(events) == 2
        assert events[0]["url"] == "https://a.com/v1"
        assert events[1]["url"] == "https://b.com/v1"
        # Unwrapped decisions must NOT carry chain fields
        assert "previous_hash" not in events[0]
        assert "hash" not in events[0]

    def test_flat_list_passthrough(self):
        """A flat list of decision dicts (no 'decision' wrapper) passes through."""
        flat = [_decision("https://a.com/v1"), _decision("https://b.com/v1")]
        events = ingest_audit_chain(flat)
        assert events == flat

    def test_empty_list(self):
        assert ingest_audit_chain([]) == []

    def test_non_dict_elements_skipped(self):
        """Non-dict elements and non-list input are handled gracefully."""
        assert ingest_audit_chain([{"url": "x"}, 42, "str", None]) == [{"url": "x"}]
        assert ingest_audit_chain("not-a-list") == []  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════
# verify_chain_integrity — 4 tests
# ═══════════════════════════════════════════════════════════════


class TestVerifyChainIntegrity:
    def test_valid_chain_passes(self):
        chain = _make_chain([_decision("https://a.com/v1"), _decision("https://b.com/v1")])
        assert verify_chain_integrity(chain, _SECRET) is True

    def test_tampered_chain_fails(self):
        chain = _make_chain([_decision("https://a.com/v1")])
        chain[0]["decision"]["url"] = "https://tampered.com/v1"  # mutate after signing
        assert verify_chain_integrity(chain, _SECRET) is False

    def test_empty_chain_passes(self):
        assert verify_chain_integrity([], _SECRET) is True

    def test_missing_secret_returns_false(self):
        chain = _make_chain([_decision("https://a.com/v1")])
        assert verify_chain_integrity(chain, "") is False
        assert verify_chain_integrity(chain, None) is False  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════
# load_sidecar_log — 2 tests
# ═══════════════════════════════════════════════════════════════


class TestLoadSidecarLog:
    def test_list_input_returns_ingested(self):
        flat = [_decision("https://a.com/v1")]
        assert load_sidecar_log(flat) == flat

    def test_unsupported_source_type_raises(self):
        with pytest.raises(TypeError, match="Unsupported sidecar log source type"):
            load_sidecar_log(123)  # type: ignore[arg-type]

    def test_chain_with_secret_verifies_then_ingests(self, tmp_path):
        """Chain-shaped input + secret → verify then ingest; tamper raises."""
        chain = _make_chain([_decision("https://a.com/v1")])
        # Valid chain ingests cleanly
        events = load_sidecar_log(chain, secret=_SECRET)
        assert len(events) == 1
        assert events[0]["url"] == "https://a.com/v1"
        # Tampered chain raises ValueError
        chain[0]["decision"]["url"] = "https://tampered.com/v1"
        with pytest.raises(ValueError, match="integrity check failed"):
            load_sidecar_log(chain, secret=_SECRET)


# ═══════════════════════════════════════════════════════════════
# run_runtime_injection_detection — 4 tests
# ═══════════════════════════════════════════════════════════════


def _inj_finding(severity: str, category: str) -> dict:
    return {"severity": severity, "category": category, "detail": "test"}


class TestRunRuntimeInjectionDetection:
    def test_clean_log_score_100(self):
        """Log with no runtime_injection_* findings → score 100."""
        log = [_decision("https://a.com/v1", findings=[])]
        result = run_runtime_injection_detection(log)
        assert result["score"] == 100.0
        assert result["findings"] == []
        assert result["summary"]["critical_count"] == 0
        assert result["summary"]["high_count"] == 0

    def test_one_critical_scores_85(self):
        """1 CRITICAL runtime_injection finding → 100 - 15 = 85."""
        log = [
            _decision(
                "https://a.com/v1",
                findings=[_inj_finding("CRITICAL", "runtime_injection_direct")],
            )
        ]
        result = run_runtime_injection_detection(log)
        assert result["score"] == 85.0
        assert result["summary"]["critical_count"] == 1
        assert result["summary"]["high_count"] == 0

    def test_one_high_scores_95(self):
        """1 HIGH runtime_injection finding → 100 - 5 = 95."""
        log = [
            _decision(
                "https://a.com/v1",
                findings=[_inj_finding("HIGH", "runtime_injection_indirect")],
            )
        ]
        result = run_runtime_injection_detection(log)
        assert result["score"] == 95.0
        assert result["summary"]["high_count"] == 1

    def test_non_runtime_findings_ignored(self):
        """Findings whose category does NOT start with runtime_injection_ are ignored."""
        log = [
            _decision(
                "https://a.com/v1",
                findings=[
                    _inj_finding("CRITICAL", "body_today_slash_date"),
                    _inj_finding("CRITICAL", "cross_border_violation"),
                ],
            )
        ]
        result = run_runtime_injection_detection(log)
        assert result["score"] == 100.0  # no runtime_injection_* findings counted
        assert result["findings"] == []


# ═══════════════════════════════════════════════════════════════
# evaluate_runtime_security — 3 tests
# ═══════════════════════════════════════════════════════════════


class TestEvaluateRuntimeSecurity:
    def _card(self) -> dict:
        return {
            "name": "test-agent",
            "endpoints": {"a2a": "https://api.anthropic.com/v1/agents"},
            "compliance": {"data_residency": "US"},
        }

    def test_clean_runtime_score_100(self):
        """Clean runtime log (declared endpoint, no findings) → fused score 100."""
        log = [_decision("https://api.anthropic.com/v1/agents", findings=[])]
        result = evaluate_runtime_security(self._card(), log)
        assert result["score"] == 100.0
        assert result["subscores"]["runtime_consistency"] == 100.0
        assert result["subscores"]["runtime_injection"] == 100.0
        assert result["summary"]["runtime_consistency_critical_count"] == 0
        assert result["summary"]["runtime_injection_critical_count"] == 0
        assert result["summary"]["total_findings"] == 0

    def test_fusion_weights(self):
        """Fusion = consistency*0.6 + injection*0.4.

        Cross-border violation (CRITICAL) → consistency score drops; one
        CRITICAL injection finding → injection score 85. Verify the fused
        score equals the weighted sum.
        """
        log = [
            _decision(
                "https://api.anthropic.com/v1/agents",
                allowed=False,  # triggers cross-border CRITICAL
                findings=[_inj_finding("CRITICAL", "runtime_injection_direct")],
            )
        ]
        result = evaluate_runtime_security(self._card(), log)
        c = result["subscores"]["runtime_consistency"]
        i = result["subscores"]["runtime_injection"]
        expected = round(c * 0.6 + i * 0.4, 1)
        assert result["score"] == expected
        assert result["summary"]["runtime_consistency_critical_count"] == 1
        assert result["summary"]["runtime_injection_critical_count"] == 1

    def test_result_structure(self):
        """Result has the expected top-level keys and component name."""
        log = [_decision("https://api.anthropic.com/v1/agents")]
        result = evaluate_runtime_security(self._card(), log)
        assert result["domain"] == "D4"
        assert result["component"] == "runtime_security"
        assert result["name"] == "runtime_security_evaluation"
        assert "subscores" in result
        assert "findings" in result
        assert "summary" in result
        # Summary carries all four count keys
        for key in (
            "runtime_consistency_critical_count",
            "runtime_consistency_high_count",
            "runtime_injection_critical_count",
            "runtime_injection_high_count",
            "total_findings",
        ):
            assert key in result["summary"]
