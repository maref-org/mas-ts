# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for Athena Digital Constitution (ADC) alignment check."""

from mas_eval.scoring.adc import check_adc_alignment


def test_fully_aligned_card():
    card = {
        "constitution": {
            "envelope": {
                "version": "1.5",
                "constitution_ref": "Athena Digital Constitution v1.5",
            }
        }
    }
    result = check_adc_alignment(card)
    assert result["component"] == "adc_alignment"
    assert result["score"] == 100.0
    assert result["subscores"]["adc_reference"] == 1.0


def test_missing_constitution():
    result = check_adc_alignment({})
    assert result["subscores"]["constitution_declared"] == 0.0
    assert any(f["category"] == "adc_no_constitution" for f in result["findings"])


def test_missing_envelope():
    card = {"constitution": {"data_sanitizer": True}}
    result = check_adc_alignment(card)
    assert result["subscores"]["envelope_present"] == 0.0


def test_missing_reference():
    card = {"constitution": {"envelope": {"version": "1.5"}}}
    result = check_adc_alignment(card)
    assert result["subscores"]["adc_reference"] == 0.0


def test_low_version():
    card = {
        "constitution": {
            "envelope": {
                "version": "0.9",
                "constitution_ref": "Athena Digital Constitution v0.9",
            }
        }
    }
    result = check_adc_alignment(card)
    assert result["subscores"]["adc_version"] == 0.0


def test_partial_score_sum():
    card = {"constitution": {"envelope": {"version": "1.0"}}}
    result = check_adc_alignment(card)
    # constitution_declared + envelope_present + adc_version, but no reference
    assert result["score"] > 0.0
    assert result["score"] < 100.0
