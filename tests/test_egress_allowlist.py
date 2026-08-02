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

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://api3.geo.admin.ch/x",
            "gopher://api3.geo.admin.ch/x",
        ],
    )
    def test_non_http_schemes_are_rejected(self, url):
        with pytest.raises(PermissionError):
            assert_host_allowed(url)


class TestResolvedIpGuard:
    def test_private_resolution_is_blocked(self, monkeypatch):
        """A host on the allow-list that resolves to a private range is DNS
        rebinding, not a legitimate move."""
        monkeypatch.setattr(api_client, "_resolve", lambda host: ("127.0.0.1",))
        with pytest.raises(PermissionError, match="interne Adresse"):
            api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    @pytest.mark.parametrize(
        "address",
        [
            "10.1.2.3",
            "172.16.0.9",
            "192.168.1.1",
            "169.254.169.254",
            "::1",
        ],
    )
    def test_each_blocked_range(self, monkeypatch, address):
        monkeypatch.setattr(api_client, "_resolve", lambda host: (address,))
        with pytest.raises(PermissionError):
            api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_public_resolution_passes(self, monkeypatch):
        monkeypatch.setattr(api_client, "_resolve", lambda host: ("185.19.28.1",))
        api_client.assert_resolved_ip_public("api3.geo.admin.ch")


class TestTheFailOpenOnResolutionError:
    """SEC-004 asked for a decision here rather than an inherited default: the
    guard returns instead of raising when the name will not resolve at all.

    The decision is that it stays, and these tests pin its *boundary*, which is
    the part that could rot. Fail-open is only defensible because it applies to
    the absence of an answer — where there is no address for an attacker to have
    supplied — and never to an answer that is merely partly bad.
    """

    def test_resolution_failure_is_not_fatal(self, monkeypatch):
        """A name nothing can connect to is not an SSRF attempt. Raising here
        would rewrite every DNS outage as 'blocked by the rebinding guard' and
        send the reader hunting for an attack instead of a resolver."""

        def boom(host):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(api_client, "_resolve", boom)
        api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_one_private_answer_among_several_still_raises(self, monkeypatch):
        """The boundary. A partial answer is an answer, and the split-horizon
        case — one real address plus one pointing at loopback — is precisely
        the shape a rebinding attack takes."""
        monkeypatch.setattr(api_client, "_resolve", lambda host: ("185.19.28.1", "127.0.0.1"))
        with pytest.raises(PermissionError, match="interne Adresse"):
            api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_an_empty_answer_is_not_treated_as_vetted(self, monkeypatch):
        """Resolving to nothing is the same non-event as failing to resolve:
        no connection follows, so there is nothing to have let through."""
        monkeypatch.setattr(api_client, "_resolve", lambda host: ())
        api_client.assert_resolved_ip_public("api3.geo.admin.ch")

    def test_the_guard_is_not_the_only_thing_between_a_url_and_egress(self, monkeypatch):
        """Why the fail-open is affordable: an unresolvable host still had to
        clear the scheme check and the frozenset before reaching it."""

        def boom(host):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(api_client, "_resolve", boom)
        with pytest.raises(PermissionError, match="Allow-List"):
            api_client.assert_host_allowed("https://attacker.example.com/x")
        with pytest.raises(PermissionError, match="Nicht-HTTPS"):
            api_client.assert_host_allowed("http://api3.geo.admin.ch/x")


# ---------------------------------------------------------------------------
# Documentation consistency (audit SEC-021)
#
# The allow-list drifted from its own documentation before. A review item does
# not catch that reliably; a failing test does.
# ---------------------------------------------------------------------------


class TestAllowListMatchesDocumentation:
    @staticmethod
    def _doc_text() -> str:
        import pathlib

        return (
            pathlib.Path(__file__).resolve().parent.parent / "docs" / "network-egress.md"
        ).read_text(encoding="utf-8")

    @pytest.mark.parametrize("host", sorted(ALLOWED_HOSTS))
    def test_every_allowed_host_is_documented(self, host):
        assert host in self._doc_text(), (
            f"{host} is on ALLOWED_HOSTS but missing from docs/network-egress.md. "
            "The comment on ALLOWED_HOSTS requires the two to stay in sync."
        )

    def test_documentation_lists_no_unknown_hosts(self):
        """The reverse direction: a host removed from code must leave the docs."""
        import re

        table_rows = [
            ln for ln in self._doc_text().splitlines() if ln.startswith("| `") and "." in ln
        ]
        documented = {
            m.group(1)
            for ln in table_rows
            for m in [re.match(r"\| `([^`]+)`", ln)]
            if m and "." in m.group(1) and "/" not in m.group(1)
        }
        stale = documented - set(ALLOWED_HOSTS)
        assert not stale, f"Documented but not on ALLOWED_HOSTS: {sorted(stale)}"


# ---------------------------------------------------------------------------
# Generated egress-proxy ACL (audit SEC-021)
#
# The CI gate for this file compares it byte-for-byte against the output of the
# renderer that produced it. That catches staleness and nothing else: when the
# renderer emitted the host entries at the wrong indent, the committed file
# parsed with `allowed_domains: null` and ten stray strings in `services`, and
# `--check` reported it up to date. These tests read the artefact as the proxy
# would, which is the only way that class of defect is visible.
# ---------------------------------------------------------------------------


class TestGeneratedProxyAcl:
    @staticmethod
    def _acl() -> dict:
        import pathlib

        import yaml

        path = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "smokescreen-acl.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_acl_parses_as_a_single_service(self):
        acl = self._acl()
        assert isinstance(acl.get("services"), list)
        assert len(acl["services"]) == 1, (
            "hosts leaked out of the service object and became siblings in "
            "`services` — an indentation defect in scripts/render_egress_acl.py"
        )
        assert isinstance(acl["services"][0], dict)

    def test_allowed_domains_is_the_code_allow_list(self):
        domains = self._acl()["services"][0]["allowed_domains"]
        assert domains is not None, "allowed_domains parsed as null — the proxy would allow nothing"
        assert sorted(domains) == sorted(ALLOWED_HOSTS)

    def test_default_rule_denies(self):
        acl = self._acl()
        assert acl["default"]["action"] == "enforce"
        assert acl["default"]["allowed_domains"] == []
