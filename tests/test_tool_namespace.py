# tests/test_tool_namespace.py
"""Namespace and tool-definition guards (audit SEC-022).

Six tools shipped without the server prefix — the façade and OpenPLZ ones. The
prefix denotes the *server* identity, not the data source, which is what makes
it a defence against name shadowing between servers. The server's own
instructions advertise joins to sibling MCP servers, so generic names like
`find_commune` were exactly the collision-prone case the check names.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from swisstopo_mcp.server import mcp

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = REPO_ROOT / "tool-hashes.json"


@pytest.fixture(scope="module")
def tool_names():
    import asyncio

    return sorted(t.name for t in asyncio.run(mcp.list_tools()))


class TestEveryToolIsNamespaced:
    def test_all_tools_carry_the_server_prefix(self, tool_names):
        unprefixed = [n for n in tool_names if not n.startswith("swisstopo_")]
        assert unprefixed == [], (
            f"Unprefixed tools would shadow sibling servers: {unprefixed}. "
            "The prefix denotes server identity, not data source — the façade "
            "and OpenPLZ tools carry it too."
        )

    def test_the_six_renamed_tools_are_present(self, tool_names):
        for name in (
            "swisstopo_list_available_layers",
            "swisstopo_query_geodata",
            "swisstopo_query_osm_features",
            "swisstopo_lookup_postal_code",
            "swisstopo_find_commune",
            "swisstopo_search_address",
        ):
            assert name in tool_names

    def test_old_names_are_gone(self, tool_names):
        """A 0.3.0 client must not silently reach an old name."""
        for name in (
            "list_available_layers",
            "query_geodata",
            "query_osm_features",
            "lookup_postal_code",
            "find_commune",
            "search_address",
        ):
            assert name not in tool_names


class TestToolHashSnapshot:
    def test_snapshot_exists_and_covers_every_tool(self, tool_names):
        assert SNAPSHOT.exists(), "run scripts/snapshot_tool_hashes.py"
        hashes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        assert sorted(hashes) == tool_names

    def test_snapshot_is_current(self):
        """Mirrors the CI gate: a changed name, description or input schema
        must not reach a release without showing up in review."""
        result = subprocess.run(
            [sys.executable, "scripts/snapshot_tool_hashes.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_hashes_are_sha256(self):
        hashes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for name, digest in hashes.items():
            assert len(digest) == 64, name
            int(digest, 16)  # raises if not hex
