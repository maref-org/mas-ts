from starlette.requests import Request
from starlette.responses import JSONResponse

from api.ratelimit import RateLimitMiddleware, TokenBucket


def test_token_bucket_allows_initial_burst():
    bucket = TokenBucket(rate=10, burst=5)
    for _ in range(5):
        assert bucket.consume() is True


def test_token_bucket_replenishes():
    bucket = TokenBucket(rate=100, burst=5)
    for _ in range(5):
        bucket.consume()
    assert bucket.consume() is False
    bucket.last_refill -= 0.05
    assert bucket.consume() is True


def test_token_bucket_denies_when_empty():
    bucket = TokenBucket(rate=1, burst=2)
    for _ in range(2):
        bucket.consume()
    assert bucket.consume() is False


def test_rate_limit_middleware_excludes_paths():
    middleware = RateLimitMiddleware(
        None, rate=100, burst=5, exclude_paths={"/health", "/metrics"}
    )
    assert "/health" in middleware.exclude_paths
    assert "/metrics" in middleware.exclude_paths
    assert "/evaluate" not in middleware.exclude_paths


def test_middleware_responds_429():
    import json

    bucket = TokenBucket(rate=1, burst=1)
    bucket.consume()
    mw = RateLimitMiddleware(None, rate=1, burst=1)
    client_ip = "127.0.0.1"
    mw._buckets[client_ip] = bucket

    async def noop_call_next(request):
        return JSONResponse({"ok": True})

    import asyncio
    async def do_test():
        scope = {
            "type": "http",
            "path": "/evaluate",
            "method": "POST",
            "client": ("127.0.0.1", 8000),
            "headers": [],
        }
        req = Request(scope)
        resp = await mw.dispatch(req, noop_call_next)
        assert resp.status_code == 429
        body = json.loads(resp.body)
        assert body["error"] == "rate_limit_exceeded"

    asyncio.run(do_test())
