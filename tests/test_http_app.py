# tests/test_http_app.py
"""Regression tests for SDK-004: CORS config on the Streamable-HTTP app."""
from __future__ import annotations

import httpx
from mcp.server.mcpserver import MCPServer
from starlette.middleware.cors import CORSMiddleware

from swisstopo_mcp.config import Settings
from swisstopo_mcp.server import _transport_security, build_http_app, mcp


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
    """A throwaway MCPServer carrying the *same* transport-security settings as the
    real server, so each test gets a fresh session manager.

    `build_http_app()` reuses the module-level `mcp`, whose session manager
    refuses to `.run()` twice — sharing one lifespan across tests instead trips
    an anyio cancel-scope error on teardown.

    mcp 2.x: `transport_security` moved off the constructor onto the app, so
    the probe passes it to `streamable_http_app()` instead.
    """
    probe = MCPServer("swisstopo_mcp_probe")
    return probe.streamable_http_app(transport_security=_transport_security())


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
    """mcp 2.x: the allow-list is an app kwarg, so these read the builder.

    In 1.x the same facts were asserted against ``mcp.settings.transport_security``.
    That field no longer exists — and a stale read would raise ``AttributeError``
    rather than quietly pass, so nothing here can silently stop checking.
    """

    def test_server_got_transport_security(self):
        """Guards the fix itself: without this the SDK falls back to its
        localhost-only default and every proxied request fails."""
        assert _transport_security() is not None

    def test_dns_rebinding_protection_stays_on(self):
        """SEC-005 depends on it — the fix is to feed the middleware the right
        lists, never to switch it off."""
        assert _transport_security().enable_dns_rebinding_protection is True

    def test_deployment_host_reaches_the_middleware(self):
        assert "127.0.0.1:*" in _transport_security().allowed_hosts

    def test_settings_no_longer_carries_transport_security(self):
        """Pins why the assertions above moved off ``mcp.settings``."""
        assert not hasattr(mcp.settings, "transport_security")


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


# ---------------------------------------------------------------------------
# Session idle timeout (audit SEC-009)
#
# The SDK's default is `session_idle_timeout=None`: a session lives until the
# process restarts. Every client that disconnects without sending `DELETE /mcp`
# — a crash, a closed laptop, a killed container — therefore leaks one for the
# lifetime of the pod. Not a confidentiality problem here (all tools are
# stateless reads over public data), but unbounded growth is still unbounded.
# ---------------------------------------------------------------------------


class TestSessionIdleTimeout:
    """mcp 2.x changed how this mitigation gets installed.

    1.x built the session manager lazily (`if self._session_manager is None`),
    so pre-populating the attribute before `streamable_http_app()` was enough.
    2.x builds one *unconditionally*, overwrites the attribute, hands that
    object to the route's ASGI app and closes the app lifespan over the same
    local variable. Pre-populating is a plain no-op there — the timeout would
    have vanished silently.

    So these tests read the manager that actually serves requests, off the
    route, instead of trusting a private attribute to still be the live one.
    """

    @staticmethod
    def _serving_manager(app):
        """The manager the route will actually dispatch to."""
        from mcp.server.streamable_http_manager import StreamableHTTPASGIApp

        for route in app.routes:
            endpoint = getattr(route, "endpoint", None)
            if isinstance(endpoint, StreamableHTTPASGIApp):
                return endpoint.session_manager
        raise AssertionError("no StreamableHTTPASGIApp route on the built app")

    def test_timeout_is_set_explicitly(self):
        """The criterion is an *explicit* TTL, not whatever the SDK defaults to."""
        manager = self._serving_manager(build_http_app([]))
        assert manager.session_idle_timeout == 1800.0

    def test_timeout_comes_from_settings(self, monkeypatch):
        from swisstopo_mcp.config import settings

        monkeypatch.setattr(settings, "session_idle_timeout", 900.0)
        assert self._serving_manager(build_http_app([])).session_idle_timeout == 900.0

    def test_zero_restores_the_sdk_default(self, monkeypatch):
        """An operator who wants the old unbounded behaviour can have it, but
        has to ask for it. Then no custom manager is installed at all and the
        SDK's own (unbounded) one stays in place."""
        from swisstopo_mcp.config import settings

        monkeypatch.setattr(settings, "session_idle_timeout", 0.0)
        assert self._serving_manager(build_http_app([])).session_idle_timeout is None

    def test_transport_security_survives_the_custom_manager(self):
        """Building the manager ourselves must not drop the DNS-rebinding
        protection the SDK would have wired up (SDK-004 / SEC-005)."""
        manager = self._serving_manager(build_http_app([]))
        assert manager.security_settings is not None
        assert manager.security_settings.enable_dns_rebinding_protection is True

    async def test_the_lifespan_starts_our_manager_not_the_sdks(self):
        """The load-bearing case for the 2.x rewrite.

        The SDK sets `lifespan=lambda app: session_manager.run()` over the
        manager *it* built. Re-pointing only the route would leave requests
        served by our manager while the lifespan started the SDK's — so the
        reaper would never run on the sessions actually being served, and every
        other assertion in this class would still pass.

        `run()` is what flips `_has_started`, so entering the real lifespan and
        checking that flag on the *serving* manager is the only assertion that
        distinguishes the two. Verified by mutation: dropping the lifespan
        re-point makes this test — and only this test — fail.
        """
        from swisstopo_mcp import server

        app = build_http_app([])
        served = self._serving_manager(app)
        assert served is server.mcp._lowlevel_server._session_manager
        assert served._has_started is False
        async with app.router.lifespan_context(app):
            assert served._has_started is True, (
                "the app lifespan started a different session manager than the "
                "one serving requests — the idle-session reaper (SEC-009) would "
                "never run on the live sessions"
            )
