# tests/test_egress_allowlist.py
"""Regression tests for SEC-021: code-layer egress allow-list."""
from __future__ import annotations

import pytest

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
