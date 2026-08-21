import logging
import uuid
from typing import Any, Awaitable, Callable, Mapping, MutableMapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

TRACE_ID_HEADER = "X-Trace-ID"
_logger = logging.getLogger("mas_eval.tracing")


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4().hex[:16])
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "no-trace")


def inject_trace_id(log_data: dict[str, object], trace_id: str) -> dict[str, object]:
    log_data["trace_id"] = trace_id
    return log_data


class TraceAdapter(logging.LoggerAdapter[Any]):
    def process(
        self, msg: object, kwargs: MutableMapping[str, Any]
    ) -> tuple[object, MutableMapping[str, Any]]:
        extra: Mapping[str, object] = self.extra if self.extra else {}
        trace_id = kwargs.pop("trace_id", extra.get("trace_id", "no-trace"))
        return f"[{trace_id}] {msg}", kwargs
