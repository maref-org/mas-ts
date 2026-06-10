# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 shared utilities (utils.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.utils import safe_get, safe_get_endpoints, safe_get_in, safe_get_list


class TestSafeGet:
    def test_key_exists(self):
        card = {"name": "test-agent"}
        assert safe_get(card, "name") == "test-agent"

    def test_key_missing(self):
        card = {"name": "test"}
        assert safe_get(card, "version", default="0.1.0") == "0.1.0"

    def test_none_value(self):
        card = {"name": None}
        assert safe_get(card, "name", default="fallback") == "fallback"

    def test_with_type_check_pass(self):
        card = {"count": 42}
        assert safe_get(card, "count", of_type=int) == 42

    def test_with_type_check_fail(self):
        card = {"count": "42"}
        assert safe_get(card, "count", of_type=int) is None

    def test_with_tuple_type_pass(self):
        card = {"val": "hello"}
        assert safe_get(card, "val", of_type=(str, list)) == "hello"

    def test_with_tuple_type_fail(self):
        card = {"val": 42}
        assert safe_get(card, "val", of_type=(str, list)) is None

    def test_default_returned_for_wrong_type(self):
        card = {"count": "not-a-number"}
        assert safe_get(card, "count", default=0, of_type=int) == 0

    def test_empty_dict_returns_default(self):
        card = {}
        assert safe_get(card, "anything", default="x") == "x"

    def test_none_with_of_type(self):
        card = {"key": None}
        assert safe_get(card, "key", of_type=str) is None


class TestSafeGetIn:
    def test_single_key(self):
        card = {"a": 1}
        assert safe_get_in(card, "a") == 1

    def test_nested_keys(self):
        card = {"a": {"b": {"c": 42}}}
        assert safe_get_in(card, "a", "b", "c") == 42

    def test_missing_intermediate(self):
        card = {"a": {"b": 1}}
        assert safe_get_in(card, "a", "x", "y") is None

    def test_none_intermediate(self):
        card = {"a": None}
        assert safe_get_in(card, "a", "b") is None

    def test_with_default(self):
        card = {}
        assert safe_get_in(card, "a", "b", default="fallback") == "fallback"

    def test_with_type_check_pass(self):
        card = {"name": "hello"}
        assert safe_get_in(card, "name", of_type=str) == "hello"

    def test_with_type_check_fail(self):
        card = {"name": 42}
        assert safe_get_in(card, "name", of_type=str) is None

    def test_non_mapping_intermediate(self):
        card = {"a": 1, "b": 2}
        assert safe_get_in(card, "a", "nested") is None

    def test_typical_card_model_name(self):
        card = {"model_backend": {"model": "claude-sonnet-4"}}
        assert (
            safe_get_in(card, "model_backend", "model", default="unknown", of_type=str)
            == "claude-sonnet-4"
        )

    def test_typical_card_missing_model(self):
        card = {}
        assert (
            safe_get_in(card, "model_backend", "model", default="unknown", of_type=str)
            == "unknown"
        )


class TestSafeGetList:
    def test_list_value(self):
        card = {"tools": ["bash", "grep"]}
        assert safe_get_list(card, "tools") == ["bash", "grep"]

    def test_none_value_returns_default(self):
        card = {"tools": None}
        assert safe_get_list(card, "tools", default=["default"]) == ["default"]

    def test_missing_key_returns_default(self):
        card = {}
        assert safe_get_list(card, "missing", default=["x"]) == ["x"]

    def test_missing_key_returns_empty(self):
        card = {}
        assert safe_get_list(card, "missing") == []

    def test_single_str_wrapped(self):
        card = {"item": "hello"}
        result = safe_get_list(card, "item", item_type=str)
        assert result == ["hello"]

    def test_single_str_not_wrapped_without_item_type(self):
        card = {"item": "hello"}
        result = safe_get_list(card, "item")
        assert result == []

    def test_item_type_filter(self):
        card = {"nums": [1, "two", 3, "four"]}
        assert safe_get_list(card, "nums", item_type=int) == [1, 3]

    def test_wrong_type_fallback(self):
        card = {"val": 42}
        assert safe_get_list(card, "val", default=["fallback"]) == ["fallback"]

    def test_empty_list_preserved(self):
        card = {"items": []}
        assert safe_get_list(card, "items") == []


class TestSafeGetEndpoints:
    def test_dict_format(self):
        card = {"endpoints": {"api": {"path": "/v1/api", "method": "POST"}}}
        result = safe_get_endpoints(card)
        assert result["api"]["path"] == "/v1/api"

    def test_list_format(self):
        card = {
            "endpoints": [
                {"path": "/v1/chat", "method": "POST"},
                {"path": "/v1/health", "method": "GET"},
            ]
        }
        result = safe_get_endpoints(card)
        assert "v1_chat" in result
        assert result["v1_chat"]["path"] == "/v1/chat"
        assert "v1_health" in result

    def test_missing_key(self):
        card = {}
        assert safe_get_endpoints(card) == {}

    def test_none_value(self):
        card = {"endpoints": None}
        assert safe_get_endpoints(card) == {}

    def test_empty_list(self):
        card = {"endpoints": []}
        assert safe_get_endpoints(card) == {}

    def test_list_without_path(self):
        card = {"endpoints": [{"method": "GET"}]}
        result = safe_get_endpoints(card)
        assert result == {}

    def test_wrong_type_returns_empty(self):
        card = {"endpoints": "not-a-dict-or-list"}
        assert safe_get_endpoints(card) == {}

    def test_list_multiple_endpoints(self):
        card = {
            "endpoints": [
                {"path": "/api/login", "method": "POST"},
                {"path": "/api/logout", "method": "GET"},
            ]
        }
        result = safe_get_endpoints(card)
        assert len(result) == 2
