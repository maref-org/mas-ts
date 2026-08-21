ERR_MAP: dict[str, dict[str, str | int]] = {
    "invalid_level": {
        "http_status": 400,
        "message": "Invalid evaluation level. Must be L0-L4.",
    },
    "task_not_found": {
        "http_status": 404,
        "message": "HITL task not found.",
    },
    "evaluation_failed": {
        "http_status": 500,
        "message": "Evaluation execution failed.",
    },
    "rate_limit_exceeded": {
        "http_status": 429,
        "message": "Too many requests. Retry with exponential backoff.",
    },
    "metrics_auth_required": {
        "http_status": 401,
        "message": "Metrics endpoint requires authentication.",
    },
    "card_validation_failed": {
        "http_status": 422,
        "message": "Agent card validation failed.",
    },
    "invalid_parameter": {
        "http_status": 422,
        "message": "Invalid request parameter.",
    },
    "internal_error": {
        "http_status": 500,
        "message": "Internal server error.",
    },
}

HITL_STATE_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["confirmed", "cancelled", "paused"],
    "confirmed": ["cancelled", "paused"],
    "cancelled": [],
    "paused": ["confirmed", "cancelled"],
}


def build_error_response(code: str, detail: str | None = None) -> dict[str, object]:
    entry = ERR_MAP.get(code, ERR_MAP["internal_error"])
    resp: dict[str, object] = {
        "error": code,
        "message": str(entry["message"]),
    }
    if detail:
        resp["detail"] = detail
    return resp
