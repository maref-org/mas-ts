from starlette.responses import JSONResponse

from api.security_headers import SECURITY_HEADERS, SecurityHeadersMiddleware


def test_security_headers_defined():
    assert "X-Content-Type-Options" in SECURITY_HEADERS
    assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in SECURITY_HEADERS
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert "X-XSS-Protection" in SECURITY_HEADERS
    assert "Referrer-Policy" in SECURITY_HEADERS
    assert "Permissions-Policy" in SECURITY_HEADERS


def test_middleware_applies_all_headers():

    from starlette.requests import Request

    mw = SecurityHeadersMiddleware(None)

    async def ok_response(request):
        return JSONResponse({"ok": True})

    import asyncio
    async def do_test():
        scope = {
            "type": "http",
            "path": "/health",
            "method": "GET",
            "client": ("127.0.0.1", 8000),
            "headers": [],
        }
        req = Request(scope)
        resp = await mw.dispatch(req, ok_response)
        for header, value in SECURITY_HEADERS.items():
            assert resp.headers.get(header) == value, f"missing header: {header}"

    asyncio.run(do_test())
