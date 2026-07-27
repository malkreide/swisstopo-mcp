# tests/test_dns_pinning.py
"""DNS-pinning transport (audit SEC-005).

`assert_resolved_ip_public` vets the address a host resolves to, but the
connection resolves it again — a rebinding window between check and connect.
`PinnedTransport` closes it by connecting to the vetted address while keeping
SNI and the Host header on the hostname, so certificate validation is unchanged.

These tests cover the *mechanics*. End-to-end TLS against a real endpoint could
not be verified in the development sandbox, which forces all HTTPS through a
forward proxy — see the finding for what remains.
"""
from __future__ import annotations

import httpx
import pytest

from swisstopo_mcp import api_client
from swisstopo_mcp.api_client import PinnedTransport, _is_ip_literal, _pinning_enabled


async def _capture(monkeypatch, request: httpx.Request) -> httpx.Request:
    """Run the transport but stub the network hop, returning the request as the
    parent transport would have received it."""
    seen: dict[str, httpx.Request] = {}

    async def _stub(self, req):
        seen["request"] = req
        return httpx.Response(200, request=req)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _stub)
    await PinnedTransport().handle_async_request(request)
    return seen["request"]


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch):
    for var in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)


def _request(url="https://api3.geo.admin.ch/rest/services/height"):
    return httpx.Request("GET", url)


class TestEnablement:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("SWISSTOPO_PIN_DNS", raising=False)
        assert _pinning_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_explicit_opt_in(self, monkeypatch, value):
        monkeypatch.setenv("SWISSTOPO_PIN_DNS", value)
        assert _pinning_enabled() is True

    def test_disabled_behind_a_forward_proxy(self, monkeypatch):
        """A proxy resolves the name itself, so client-side pinning cannot
        apply — enabling it anyway would only break CONNECT."""
        monkeypatch.setenv("SWISSTOPO_PIN_DNS", "true")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
        assert _pinning_enabled() is False


class TestIpLiteralDetection:
    @pytest.mark.parametrize("host", ["127.0.0.1", "10.1.2.3", "::1", "2001:db8::1"])
    def test_literals(self, host):
        assert _is_ip_literal(host) is True

    @pytest.mark.parametrize("host", ["api3.geo.admin.ch", "localhost", "example.com"])
    def test_names(self, host):
        assert _is_ip_literal(host) is False


class TestRewriting:
    """The load-bearing property: the connection target changes, the identity
    the certificate is checked against does not."""

    async def test_url_host_becomes_the_resolved_ip(self, monkeypatch):
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        seen = await _capture(monkeypatch, _request())
        assert seen.url.host == "185.19.28.1"

    async def test_host_header_keeps_the_hostname(self, monkeypatch):
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        seen = await _capture(monkeypatch, _request())
        assert seen.headers["Host"] == "api3.geo.admin.ch"

    async def test_sni_keeps_the_hostname(self, monkeypatch):
        """Without this the handshake presents an IP as the server name and
        certificate validation fails — the failure mode this test exists for."""
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        seen = await _capture(monkeypatch, _request())
        assert seen.extensions.get("sni_hostname") == "api3.geo.admin.ch"

    async def test_path_and_query_survive(self, monkeypatch):
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        seen = await _capture(
            monkeypatch, _request("https://api3.geo.admin.ch/rest/services/height?sr=2056")
        )
        assert seen.url.path == "/rest/services/height"
        assert seen.url.params["sr"] == "2056"

    async def test_private_address_is_refused(self, monkeypatch):
        """Pinning reuses the SEC-004 guard rather than trusting the resolver."""
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("127.0.0.1",))
        with pytest.raises(PermissionError):
            await _capture(monkeypatch, _request())

    async def test_ip_literal_is_left_alone(self, monkeypatch):
        called = False

        def _boom(host):
            nonlocal called
            called = True
            return ()

        monkeypatch.setattr(api_client, "_resolve", _boom)
        seen = await _capture(monkeypatch, _request("https://185.19.28.1/x"))
        assert called is False, "an IP literal must not be re-resolved"
        assert seen.url.host == "185.19.28.1"

    async def test_proxy_disables_rewriting(self, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        seen = await _capture(monkeypatch, _request())
        assert seen.url.host == "api3.geo.admin.ch", "must not pin behind a proxy"
