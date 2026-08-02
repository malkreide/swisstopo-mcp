# tests/test_protocol_version.py
"""Drift guard for the negotiated MCP protocol version (audit ARCH-012).

The Python SDK exposes no author-settable protocol pin, so the code-level pin
the check asks for is not expressible. What *is* expressible is a tripwire: the
version this server was audited and documented against is asserted here, so a
routine Dependabot bump of `mcp` cannot move it silently.

mcp 2.x made that tripwire ambiguous, because one server now serves **two
protocol eras** (`serve_dual_era_loop`; the client's first request decides):

* the **legacy `initialize` handshake** — what today's clients speak. It caps
  at ``LATEST_HANDSHAKE_VERSION``.
* the **modern per-request-envelope era**, which reaches
  ``LATEST_MODERN_VERSION``.

``LATEST_PROTOCOL_VERSION`` is an alias for the *modern* version in 2.x. The
original single assertion compared the documented value against it and failed
after the upgrade — correctly, in the sense that the SDK really did bring a
newer revision, but against the wrong constant for what the docs describe.

Both eras are asserted separately now, so neither can move unnoticed, and the
handshake ceiling is measured against a live server rather than read off a
constant name.
"""

from __future__ import annotations

import json

import pytest
from mcp.types.version import LATEST_HANDSHAKE_VERSION, LATEST_MODERN_VERSION

from swisstopo_mcp.server import build_http_app

# The version documented in README.md / README.de.md and recorded in CHANGELOG:
# what a client using the legacy `initialize` handshake negotiates.
DOCUMENTED_PROTOCOL_VERSION = "2025-11-25"

# The revision the modern envelope era reaches. Pinned so a Dependabot bump
# cannot move it silently either — this is what the old single assertion was
# accidentally checking.
DOCUMENTED_MODERN_VERSION = "2026-07-28"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def test_handshake_version_matches_documentation():
    assert LATEST_HANDSHAKE_VERSION == DOCUMENTED_PROTOCOL_VERSION, (
        f"The MCP SDK's handshake era now tops out at {LATEST_HANDSHAKE_VERSION}, "
        f"but the docs say {DOCUMENTED_PROTOCOL_VERSION}. Update README.md, "
        "README.de.md and CHANGELOG.md together, then adjust this constant."
    )


def test_modern_era_version_matches_documentation():
    assert LATEST_MODERN_VERSION == DOCUMENTED_MODERN_VERSION, (
        f"The MCP SDK's modern era now reaches {LATEST_MODERN_VERSION}, but the "
        f"docs say {DOCUMENTED_MODERN_VERSION}. Update the docs, then adjust "
        "this constant."
    )


def test_the_two_eras_are_actually_different():
    """Guards the reason this file has two assertions instead of one.

    If the SDK ever collapses the eras onto one revision, the split above
    becomes redundant and should be simplified back — this is what says so.
    """
    assert LATEST_MODERN_VERSION > LATEST_HANDSHAKE_VERSION


async def _initialize(requested: str) -> str | None:
    """Run a legacy `initialize` through the real ASGI stack."""
    import httpx

    app = build_http_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            response = await client.post(
                "/mcp",
                headers=_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": requested,
                        "capabilities": {},
                        "clientInfo": {"name": "legacy-client", "version": "1"},
                    },
                },
            )
    body = response.text
    for line in body.splitlines():  # strip SSE framing if present
        if line.startswith("data: "):
            body = line[len("data: ") :]
    return json.loads(body).get("result", {}).get("protocolVersion")


@pytest.mark.parametrize("requested", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"])
async def test_older_clients_keep_their_revision(requested):
    """The migration must not push existing clients onto a new revision."""
    assert await _initialize(requested) == requested


async def test_handshake_caps_at_the_documented_version():
    """The load-bearing case.

    A client asking over the legacy handshake for the modern revision gets the
    ceiling back. This is what makes DOCUMENTED_PROTOCOL_VERSION the right
    description of that era, measured rather than inferred.
    """
    assert await _initialize(DOCUMENTED_MODERN_VERSION) == DOCUMENTED_PROTOCOL_VERSION
