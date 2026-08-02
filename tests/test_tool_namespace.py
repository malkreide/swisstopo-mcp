# tests/test_tool_namespace.py
"""Namespace and tool-definition guards (audit SEC-022).

Six tools shipped without the server prefix — the façade and OpenPLZ ones. The
prefix denotes the *server* identity, not the data source, which is what makes
it a defence against name shadowing between servers. The server's own
instructions advertise joins to sibling MCP servers, so generic names like
`find_commune` were exactly the collision-prone case the check names.
"""

from __future__ import annotations

import importlib.util
import inspect
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


class TestSnapshotIsInterpreterIndependent:
    """Regression: the first version of this snapshot hashed the raw docstring.

    Python 3.13 strips a docstring's common leading whitespace at compile time
    while 3.11 and 3.12 do not, so the same source hashed differently per
    interpreter — the snapshot passed on 3.11 and 3.12 and failed the 3.13 leg
    of the same CI run.
    """

    @staticmethod
    def _module():
        spec = importlib.util.spec_from_file_location(
            "snap", REPO_ROOT / "scripts" / "snapshot_tool_hashes.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_description_normalisation_is_idempotent(self):
        """cleandoc on the already-dedented 3.13 form must be a no-op, which is
        what makes the three interpreters converge."""
        snap = self._module()
        raw = "Summary.\n\n    Indented continuation.\n"
        once = snap._normalise_description(raw)
        assert snap._normalise_description(once) == once

    def test_indented_and_dedented_descriptions_hash_alike(self):
        snap = self._module()
        indented = "Summary.\n\n    <use_case>Something.</use_case>"
        dedented = inspect.cleandoc(indented)
        assert snap._normalise_description(indented) == snap._normalise_description(dedented)


# ---------------------------------------------------------------------------
# The tool budget is a gate, not an assertion (audit ARCH-006)
#
# The README declares a self-imposed ceiling of 25 tools, and the finding's last
# gap was that nothing enforced it: "nothing fails if tool 26 is registered,
# unlike the tool-hash and egress-ACL snapshots which are gated in CI". A budget
# that only exists in prose is a number, not a budget.
#
# The ceiling itself is a judgement, not a law. Raising it is allowed — but as a
# deliberate edit here and in the README, which is exactly the conversation the
# check wants to force.
# ---------------------------------------------------------------------------

TOOL_BUDGET = 25


class TestToolBudget:
    def test_the_surface_is_within_budget(self, tool_names):
        assert len(tool_names) <= TOOL_BUDGET, (
            f"{len(tool_names)} tools against a budget of {TOOL_BUDGET}. Either "
            "consolidate, or raise TOOL_BUDGET here and update the "
            "'Tool budget and aggregation' section in both READMEs with the "
            "reason — the point is that the number cannot drift silently."
        )

    def test_the_readmes_state_the_same_budget(self):
        """A gate that disagrees with the documentation is worse than neither."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        for name in ("README.md", "README.de.md"):
            text = (root / name).read_text(encoding="utf-8")
            assert str(TOOL_BUDGET) in text, f"{name} does not mention the budget of {TOOL_BUDGET}"

    def test_the_readmes_state_the_actual_count(self, tool_names):
        """The count drifted twice before (13 → 23 → 24 in stale prose)."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        for name in ("README.md", "README.de.md"):
            text = (root / name).read_text(encoding="utf-8")
            count = len(tool_names)
            assert f"{count} tools" in text or f"{count} Tools" in text, (
                f"{name} does not state the current tool count ({count})"
            )
