# tests/test_egress_allowlist.py
"""Regression tests for SEC-021: code-layer egress allow-list."""
from __future__ import annotations

import socket

import pytest

from swisstopo_mcp import api_client
from swisstopo_mcp.api_client import (
    ALLOWED_HOSTS,
    GEO_ADMIN_BASE,
    STAC_BASE,
    assert_host_allowed,
)
from swisstopo_mcp.oereb import OEREB_ENDPOINTS


class TestAssertHostAllowed:
    def test_allows_geo_admin(self):
        assert_host_allowed(f"{GEO_ADMIN_BASE}/rest/services/ech/SearchServer")

    def test_allows_stac(self):
        assert_host_allowed(f"{STAC_BASE}/collections")

    @pytest.mark.parametrize("host", sorted(ALLOWED_HOSTS))
    def test_each_allowed_host_passes(self, host):
        assert_host_allowed(f"https://{host}/some/path?x=1")

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.com/x",
            "http://169.254.169.254/latest/meta-data/",
            "https://api3.geo.admin.ch.evil.com/x",  # suffix trick
            "https://localhost/x",
        ],
    )
    def test_rejects_disallowed_hosts(self, url):
        with pytest.raises(PermissionError, match="Egress-Allow-List"):
            assert_host_allowed(url)


def test_oereb_endpoints_are_all_allowed():
    """Every canton endpoint in the registry must be on the allow-list."""
    from urllib.parse import urlparse

    for base in OEREB_ENDPOINTS.values():
        host = urlparse(base).hostname
        assert host in ALLOWED_HOSTS, f"{host} missing from ALLOWED_HOSTS"


# ---------------------------------------------------------------------------
# Scheme + resolved-IP guard (audit SEC-004)
# ---------------------------------------------------------------------------


class TestSchemeIsValidated:
    def test_http_is_rejected_even_for_allowed_host(self):
        """An allow-listed host over cleartext http:// used to pass."""
        with pytest.raises(PermissionError, match="Nicht-HTTPS"):
            assert_host_allowed("http://api3.geo.admin.ch/rest/services/height")

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp://api3.geo.admin.ch/x",
        "gopher://api3.geo.admin.ch/x",
    ])
    def test_non_http_schemes_are_rejected(self, url):
        with pytest.raises(PermissionError):
            assert_host_allowed(url)


class TestResolvedIpGuard:
    def test_private_resolution_is_blocked(self, monkeypatch):
        """A host on the allow-list that resolves to a private range is DNS
        rebinding, not a legitimate move."""
        monkeypatch.setattr(
            api_client, "_resolve", lambda host: ("127.0.0.1",)
        )
        with pytest.raises(PermissionError, match="interne Adresse"):
            api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    @pytest.mark.parametrize("address", [
        "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254", "::1",
    ])
    def test_each_blocked_range(self, monkeypatch, address):
        monkeypatch.setattr(api_client, "_resolve", lambda host: (address,))
        with pytest.raises(PermissionError):
            api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_public_resolution_passes(self, monkeypatch):
        monkeypatch.setattr(api_client, "_resolve", lambda host: ("185.19.28.1",))
        api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_resolution_failure_is_not_fatal(self, monkeypatch):
        """httpx gives a better connection error than a masked PermissionError."""
        def boom(host):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(api_client, "_resolve", boom)
        api_client.assert_resolved_ip_public("api3.geo.admin.ch")
