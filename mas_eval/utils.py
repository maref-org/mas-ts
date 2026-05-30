"""Shared utilities for MAS-TS-001 domain evaluators."""

from collections.abc import Mapping, Sequence


def safe_get(card, key, default=None, of_type=None):
    """Type-safe get from a card dict.

    Returns `default` if key is missing or value is not the expected type.
    If `of_type` is a tuple, any type in the tuple is accepted.

    Usage:
        safe_get(card, "compliance", {}, dict)
        safe_get(card, "capabilities", [], list)
        safe_get(card, "dependencies", [], (list, type(None)))
    """
    if key not in card:
        return default
    val = card[key]
    if val is None:
        return default
    if of_type is not None and not isinstance(val, of_type):
        return default
    return val


def safe_get_in(card, *keys, default=None, of_type=None):
    """Type-safe chained get for nested dict access.

    Usage:
        safe_get_in(card, "model_backend", "model", default="unknown", of_type=str)
    """
    current = card
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        if key not in current:
            return default
        current = current[key]
    if current is None:
        return default
    if of_type is not None and not isinstance(current, of_type):
        return default
    return current


def safe_get_list(card, key, default=None, item_type=None):
    """Type-safe get that ensures a list return value.

    If the value is a list, returns it.
    If the value is a single item, wraps it in a list.
    Otherwise returns default.

    Usage:
        safe_get_list(card, "dependencies", default=[], item_type=(str, dict))
    """
    val = safe_get(card, key, default=None)
    if val is None:
        return default if default is not None else []
    if isinstance(val, list):
        if item_type is not None:
            return [v for v in val if isinstance(v, item_type)]
        return val
    if isinstance(val, str) and item_type is not None and isinstance(val, item_type):
        return [val]
    return default if default is not None else []


def safe_get_endpoints(card, key="endpoints"):
    """Get endpoints dict, handling both dict and list formats."""
    val = safe_get(card, key, default={})
    if isinstance(val, dict):
        return val
    if isinstance(val, list):
        result = {}
        for ep in val:
            if isinstance(ep, dict):
                path = ep.get("path", "")
                method = ep.get("method", "GET")
                if path:
                    name = path.strip("/").replace("/", "_") or "endpoint"
                    result[name] = {"path": path, "method": method}
        return result
    return {}
