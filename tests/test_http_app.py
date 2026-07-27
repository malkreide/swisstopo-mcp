# tests/test_http_app.py
"""Regression tests for SDK-004: CORS config on the Streamable-HTTP app."""
from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

from swisstopo_mcp.config import Settings
from swisstopo_mcp.server import build_http_app, mcp


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


def test_http_app_exposes_healthz_route():
    # Container/orchestrator liveness probe target (SEC-007 deployment).
    app = build_http_app()
    paths = {getattr(r, "path", None) for r in app.router.routes}
    assert "/healthz" in paths


# ---------------------------------------------------------------------------
# Transport security (audit SDK-004 / SCALE-001)
#
# The kwargs assertions above only prove CORS is *configured*. They passed while
# every real request was rejected one layer earlier by the SDK's
# TransportSecurityMiddleware, which had never been told the deployment's hosts
# and origins. These tests drive the actual ASGI app instead.
# ---------------------------------------------------------------------------

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _probe_app():
    """A throwaway FastMCP carrying the *same* transport-security settings as the
    real server, so each test gets a fresh session manager.

    `build_http_app()` reuses the module-level `mcp`, whose session manager
    refuses to `.run()` twice — sharing one lifespan across tests instead trips
    an anyio cancel-scope error on teardown.
    """
    probe = FastMCP(
        "swisstopo_mcp_probe",
        transport_security=mcp.settings.transport_security,
    )
    return probe.streamable_http_app()


async def _post_mcp(extra_headers: dict[str, str]) -> int:
    """POST an initialize request through the real ASGI stack, return the status."""
    app = _probe_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            response = await client.post(
                "/mcp", json=_INIT, headers={**_HEADERS, **extra_headers}
            )
            return response.status_code


class TestTransportSecurityIsWired:
    def test_fastmcp_got_transport_security(self):
        """Guards the fix itself: without this the SDK falls back to its
        localhost-only default and every proxied request fails."""
        assert mcp.settings.transport_security is not None

    def test_dns_rebinding_protection_stays_on(self):
        """SEC-005 depends on it — the fix is to feed the middleware the right
        lists, never to switch it off."""
        assert mcp.settings.transport_security.enable_dns_rebinding_protection is True

    def test_deployment_host_reaches_the_middleware(self):
        assert "127.0.0.1:*" in mcp.settings.transport_security.allowed_hosts


class TestTransportSecuritySettings:
    def test_loopback_hosts_use_wildcard_ports(self):
        """`--port` overrides the configured port at runtime, so fixed-port
        entries would lock a developer out of their own server."""
        hosts = Settings().allowed_hosts_list
        assert "127.0.0.1:*" in hosts
        assert "localhost:*" in hosts

    def test_deployment_host_is_appended(self):
        s = Settings(allowed_hosts="swisstopo-mcp.example.com")
        assert "swisstopo-mcp.example.com" in s.allowed_hosts_list
        assert "127.0.0.1:*" in s.allowed_hosts_list  # loopback still works

    def test_transport_origins_include_loopback_and_configured(self):
        s = Settings(allowed_origins="https://client.example.com")
        origins = s.transport_origins_list
        assert "https://client.example.com" in origins
        assert "http://localhost:*" in origins

    def test_cors_origins_stay_exactly_as_configured(self):
        """CORS must not silently inherit the loopback defaults the middleware
        needs — the two lists serve different layers."""
        s = Settings(allowed_origins="https://client.example.com")
        assert s.origins_list == ["https://client.example.com"]

    def test_no_origins_configured_means_no_cors(self):
        assert Settings().origins_list == []


class TestTransportSecurityRequests:
    async def test_loopback_request_is_accepted(self):
        """Regression: this returned 421 while the port-derived entries were
        pinned to the configured port instead of a wildcard."""
        assert await _post_mcp({}) not in (403, 421)

    async def test_unconfigured_origin_is_rejected(self):
        assert await _post_mcp({"Origin": "https://evil.example.com"}) == 403

    async def test_unconfigured_host_is_rejected(self):
        assert await _post_mcp({"Host": "evil.example.com"}) == 421

    async def test_healthz_ignores_transport_security(self):
        """The probe answering while MCP requests fail is what masked this bug
        in Kubernetes; assert the asymmetry is deliberate and still true."""
        app = build_http_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as c:
            response = await c.get("/healthz", headers={"Host": "evil.example.com"})
        assert response.status_code == 200
