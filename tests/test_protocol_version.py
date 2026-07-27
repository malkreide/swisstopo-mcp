# tests/test_protocol_version.py
"""Drift guard for the negotiated MCP protocol version (audit ARCH-012).

The Python SDK exposes no author-settable protocol pin, so the code-level pin
the check asks for is not expressible. What *is* expressible is a tripwire: the
version this server was audited and documented against is asserted here, so a
routine Dependabot bump of `mcp` cannot move it silently.

When this test fails, the SDK moved the protocol version. That is not
necessarily wrong — update the constant here, the README section and the
CHANGELOG together, per the update policy in README.md.
"""
from __future__ import annotations

from mcp.types import LATEST_PROTOCOL_VERSION

# The version documented in README.md / README.de.md and recorded in CHANGELOG.
DOCUMENTED_PROTOCOL_VERSION = "2025-11-25"


def test_negotiated_protocol_version_matches_documentation():
    assert LATEST_PROTOCOL_VERSION == DOCUMENTED_PROTOCOL_VERSION, (
        f"The MCP SDK now negotiates {LATEST_PROTOCOL_VERSION}, but the docs "
        f"say {DOCUMENTED_PROTOCOL_VERSION}. Update README.md, README.de.md "
        "and CHANGELOG.md together, then adjust this constant."
    )
