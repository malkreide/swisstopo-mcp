# tests/test_dns_pinning.py
"""DNS-pinning transport (audit SEC-005).

`assert_resolved_ip_public` vets the address a host resolves to, but the
connection resolves it again — a rebinding window between check and connect.
`PinnedTransport` closes it by connecting to the vetted address while keeping
SNI and the Host header on the hostname, so certificate validation is unchanged.

These tests cover the *mechanics*, and that is the limit of what they prove.
The non-live suite asserts that the request is rewritten correctly; it does not
and cannot assert that the resulting TLS handshake succeeds, because that needs
a real endpoint. That proof lives in `TestPinnedTlsHandshake` below, which is
`@pytest.mark.live` and therefore deselected by the PR CI job (`pytest -m "not
live"`). A green PR run is evidence about rewriting only — read it that way
(audit SEC-005).

Pinning is **on by default since 0.4.0**, so these are no longer tests of an
opt-in path. Two properties carry that change and are tested here rather than
argued: the transport turns itself off behind a forward proxy, and it never
converts a reachable host into an unreachable one.
"""
from __future__ import annotations

import httpx
import pytest

from swisstopo_mcp import api_client
from swisstopo_mcp.api_client import PinnedTransport, _is_ip_literal, _pinning_enabled
from swisstopo_mcp.config import Settings, settings


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
    """`SWISSTOPO_PIN_DNS` is read once at import into `Settings` (ARCH-004), so
    these patch the settings object rather than the environment — setting the
    variable after startup has no effect, by design."""

    def test_on_by_default(self):
        """0.4.0 flipped this. Default-off meant the TOCTOU window SEC-004
        names stayed open in the configuration almost everyone runs, including
        stdio, which has no network-layer compensation at all."""
        assert Settings().pin_dns is True

    def test_default_is_active_not_merely_declared(self, monkeypatch):
        monkeypatch.setattr(settings, "pin_dns", Settings().pin_dns)
        assert _pinning_enabled() is True

    def test_explicit_opt_out(self, monkeypatch):
        """The kill switch is the migration path for anyone the rewrite
        surprises, so it has to keep working."""
        monkeypatch.setattr(settings, "pin_dns", False)
        assert _pinning_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_truthy_env_values_parse(self, value):
        """pydantic-settings, not us, decides what counts as true."""
        assert Settings(pin_dns=value).pin_dns is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no"])
    def test_falsy_env_values_parse(self, value):
        """Now the load-bearing direction: this is the documented escape hatch."""
        assert Settings(pin_dns=value).pin_dns is False

    def test_disabled_behind_a_forward_proxy(self, monkeypatch):
        """A proxy resolves the name itself, so client-side pinning cannot
        apply — enabling it anyway would only break CONNECT."""
        monkeypatch.setattr(settings, "pin_dns", True)
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


# ---------------------------------------------------------------------------
# Pinning must not make a reachable host unreachable (audit SEC-005 item 3)
#
# This is the property that makes default-on defensible, so it is tested rather
# than asserted. The finding named the concrete case: only `addresses[0]` was
# used, so an AAAA-first answer in an IPv4-only network failed the request
# outright — while *unpinned* httpx would simply have tried the next address.
# A security control whose cost is "some networks lose egress" does not get to
# be a default.
# ---------------------------------------------------------------------------


def _failing_then_ok(fail_hosts: set[str], attempts: list[str]):
    """Parent-transport stub that refuses to connect to specific addresses."""

    async def _stub(self, req):
        attempts.append(req.url.host)
        if req.url.host in fail_hosts:
            raise httpx.ConnectError("network is unreachable", request=req)
        return httpx.Response(200, request=req)

    return _stub


class TestAllResolvedAddressesAreTried:
    async def test_falls_through_to_the_second_address(self, monkeypatch):
        """The exact reported shape: IPv6 first, IPv4 second, no IPv6 route."""
        attempts: list[str] = []
        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("2001:db8::1", "185.19.28.1")
        )
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _failing_then_ok({"2001:db8::1"}, attempts),
        )
        response = await PinnedTransport().handle_async_request(_request())
        assert response.status_code == 200
        assert attempts == ["2001:db8::1", "185.19.28.1"]

    async def test_the_first_working_address_stops_the_walk(self, monkeypatch):
        attempts: list[str] = []
        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("185.19.28.1", "185.19.28.2")
        )
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport, "handle_async_request", _failing_then_ok(set(), attempts)
        )
        await PinnedTransport().handle_async_request(_request())
        assert attempts == ["185.19.28.1"], "a working address must not be retried past"

    async def test_every_address_failing_raises_the_connect_error(self, monkeypatch):
        """Exhausting the list must surface httpx's error, not a masked one —
        'connection refused' is the truth; a PermissionError would not be."""
        attempts: list[str] = []
        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("185.19.28.1", "185.19.28.2")
        )
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _failing_then_ok({"185.19.28.1", "185.19.28.2"}, attempts),
        )
        with pytest.raises(httpx.ConnectError):
            await PinnedTransport().handle_async_request(_request())
        assert attempts == ["185.19.28.1", "185.19.28.2"]

    async def test_the_reported_url_is_the_hostname_not_the_last_ip(self, monkeypatch):
        """A traceback naming 185.19.28.2 sends the reader hunting for a host
        they never configured."""
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _failing_then_ok({"185.19.28.1"}, []),
        )
        request = _request()
        with pytest.raises(httpx.ConnectError):
            await PinnedTransport().handle_async_request(request)
        assert request.url.host == "api3.geo.admin.ch"

    async def test_a_read_error_is_not_retried(self, monkeypatch):
        """Only connect-phase failures are safe to retry. A ReadError means the
        request reached the peer, and sending it again would be a duplicate
        request, not a retry."""
        attempts: list[str] = []

        async def _stub(self, req):
            attempts.append(req.url.host)
            raise httpx.ReadError("connection reset", request=req)

        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("185.19.28.1", "185.19.28.2")
        )
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _stub)
        with pytest.raises(httpx.ReadError):
            await PinnedTransport().handle_async_request(_request())
        assert attempts == ["185.19.28.1"], "a delivered request must not be replayed"

    async def test_every_candidate_is_vetted_not_just_the_first(self, monkeypatch):
        """The walk must not become a way around the SEC-004 guard: a second
        answer pointing at loopback has to be refused before any connection."""
        attempts: list[str] = []
        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("185.19.28.1", "127.0.0.1")
        )
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _failing_then_ok({"185.19.28.1"}, attempts),
        )
        with pytest.raises(PermissionError):
            await PinnedTransport().handle_async_request(_request())
        assert attempts == [], "the guard must run before the first connection"


class TestTheShippedDefaultDoesNotBreakOrdinaryRequests:
    """The end-to-end path, with pinning **on**, through the real client stack.

    This class exists because of a regression it would have caught. Everything
    above drives `PinnedTransport` directly, and `tests/conftest.py` turns
    pinning off for the rest of the suite (a rewritten URL cannot match a
    hostname-registered mock). Between them, flipping the default to on was
    covered by nothing that actually issued a request — and it broke 34 tests
    the moment CI ran it in an environment with no `HTTPS_PROXY` to disable
    pinning silently.

    So: opt back in, build the client the way the server does, and send a real
    request through `request_with_retry`.
    """

    @pytest.fixture
    def pinned(self, monkeypatch):
        monkeypatch.setattr(settings, "pin_dns", True)
        monkeypatch.setattr(api_client, "_resolve", lambda h: ("185.19.28.1",))
        assert _pinning_enabled() is True, "the fixture must actually enable it"

    async def test_the_client_factory_installs_the_pinning_transport(self, pinned):
        client = api_client._build_client()
        try:
            assert isinstance(client._transport, PinnedTransport)
        finally:
            await client.aclose()

    async def test_a_request_still_completes(self, pinned, monkeypatch):
        """The load-bearing one. Pinning is a defence, not a change of outcome:
        the caller asks for a hostname and gets its response back."""
        seen: dict[str, httpx.Request] = {}

        async def _stub(self, req):
            seen["request"] = req
            return httpx.Response(200, json={"ok": True}, request=req)

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _stub)
        response = await api_client.request_with_retry(
            "GET", "https://api3.geo.admin.ch/rest/services/test"
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_the_connection_went_to_the_pinned_address(self, pinned, monkeypatch):
        seen: dict[str, httpx.Request] = {}

        async def _stub(self, req):
            seen["request"] = req
            return httpx.Response(200, json={}, request=req)

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _stub)
        await api_client.request_with_retry(
            "GET", "https://api3.geo.admin.ch/rest/services/test"
        )
        assert seen["request"].url.host == "185.19.28.1"
        assert seen["request"].headers["Host"] == "api3.geo.admin.ch"

    async def test_the_egress_allow_list_still_sees_the_hostname(self, pinned):
        """The guard runs on the URL the caller passed, before the transport
        rewrites anything — so pinning cannot be a way past the allow-list, and
        equally cannot cause a legitimate host to be refused as a bare IP."""
        with pytest.raises(PermissionError, match="Allow-List"):
            await api_client.request_with_retry(
                "GET", "https://attacker.example.com/x"
            )


class TestAStreamingBodyIsNeverReplayed:
    """Walking the list means sending the request twice, which is only correct
    for a buffered body. This server sends none, but the transport is generic
    and a truncated 'retry' would be worse than the error it recovers from."""

    async def test_a_buffered_body_is_replayable(self):
        assert api_client._body_is_replayable(
            httpx.Request("POST", "https://api3.geo.admin.ch/x", content=b"payload")
        )

    async def test_an_empty_body_is_replayable(self):
        assert api_client._body_is_replayable(_request())

    async def test_a_streaming_body_is_not(self):
        async def _chunks():
            yield b"chunk"

        assert not api_client._body_is_replayable(
            httpx.Request("POST", "https://api3.geo.admin.ch/x", content=_chunks())
        )

    async def test_a_streaming_request_tries_one_address_only(self, monkeypatch):
        attempts: list[str] = []

        async def _chunks():
            yield b"chunk"

        monkeypatch.setattr(
            api_client, "_resolve", lambda h: ("185.19.28.1", "185.19.28.2")
        )
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _failing_then_ok({"185.19.28.1", "185.19.28.2"}, attempts),
        )
        request = httpx.Request(
            "POST", "https://api3.geo.admin.ch/x", content=_chunks()
        )
        with pytest.raises(httpx.ConnectError):
            await PinnedTransport().handle_async_request(request)
        assert attempts == ["185.19.28.1"]


# ---------------------------------------------------------------------------
# Live verification (skipped in CI)
#
# The unit tests above prove the transport rewrites the request correctly. They
# cannot prove the resulting TLS handshake succeeds — that needs a real
# endpoint. These close that gap and are the reason SEC-005 could be closed.
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestPinnedTlsHandshake:
    """Connecting to an IP while presenting the hostname as SNI must validate."""

    @pytest.mark.parametrize(
        "host", ["api3.geo.admin.ch", "geodesy.geo.admin.ch"]
    )
    def test_handshake_succeeds_with_hostname_sni(self, host):
        import socket
        import ssl

        ip = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)[0][4][0]
        context = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
        assert host in sans or any(s.startswith("*.") for s in sans)

    def test_handshake_fails_without_hostname_sni(self):
        """The failure mode the SNI preservation exists to avoid: presenting the
        IP as the server name makes the certificate mismatch."""
        import socket
        import ssl

        host = "api3.geo.admin.ch"
        ip = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)[0][4][0]
        context = ssl.create_default_context()
        with pytest.raises(ssl.SSLCertVerificationError):
            with socket.create_connection((ip, 443), timeout=10) as sock:
                context.wrap_socket(sock, server_hostname=ip)


@pytest.mark.live
class TestExtensionPassthrough:
    """The transport sets request.extensions['sni_hostname']; the chain that
    consumes it must stay intact across httpx/httpcore upgrades."""

    def test_httpx_forwards_extensions_to_httpcore(self):
        import inspect

        from httpx._transports import default as httpx_default

        src = inspect.getsource(httpx_default.AsyncHTTPTransport.handle_async_request)
        assert "extensions=request.extensions" in src

    def test_httpcore_reads_sni_hostname(self):
        import inspect

        from httpcore._async import connection

        assert "sni_hostname" in inspect.getsource(connection)
