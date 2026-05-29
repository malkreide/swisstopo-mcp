# tests/test_http_app.py
"""Regression tests for SDK-004: CORS config on the Streamable-HTTP app."""
from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware

from swisstopo_mcp.server import build_http_app


def _cors_kwargs(app):
    for mw in app.user_middleware:
        if mw.cls is CORSMiddleware:
            # Starlette stores config in .kwargs (newer) or .options (older)
            return getattr(mw, "kwargs", None) or getattr(mw, "options", {})
    raise AssertionError("CORSMiddleware not configured on the HTTP app")


def test_http_app_has_cors_middleware():
    app = build_http_app(["https://client.example.com"])
    kwargs = _cors_kwargs(app)
    assert "Mcp-Session-Id" in kwargs["expose_headers"]
    assert "Mcp-Session-Id" in kwargs["allow_headers"]
    assert kwargs["allow_origins"] == ["https://client.example.com"]


def test_http_app_defaults_to_no_origins():
    # Safe default: no cross-origin access unless explicitly allowed.
    app = build_http_app()
    kwargs = _cors_kwargs(app)
    assert kwargs["allow_origins"] == []


def test_http_app_retains_lifespan():
    app = build_http_app(["https://client.example.com"])
    assert app.router.lifespan_context is not None
