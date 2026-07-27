# tests/test_tool_hygiene.py
"""Self-scan of this server's own tool definitions (audit SEC-014 / SEC-015).

Both findings are documented deferrals to a gateway that does not exist yet.
A deferral is only honest if the premises it rests on stay true, so these tests
enforce them here rather than leaving them as prose in SECURITY.md:

- SEC-014's risk-bounding argument assumes every tool is read-only. If a future
  tool is not, the deferral is void and must be re-evaluated.
- SEC-015's argument assumes tool definitions come from this repository and are
  reviewed. That does not protect against a description written *here* carrying
  invisible characters or override phrasing, which is what this scans for.

The patterns are German and French as well as English on purpose: the
descriptions in this portfolio are German, and an off-the-shelf English pattern
list would sail straight past them.
"""
from __future__ import annotations

import asyncio
import re

import pytest

from swisstopo_mcp.server import mcp

# Zero-width, bidi-override and word-joiner ranges — the classic ways to hide
# text inside a description that a reviewer reads as clean.
# Written as escapes, not literals: a pattern file that contains the very
# characters it detects is invisible to review, which is the failure mode
# this test exists to catch.
INVISIBLE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"
)

OVERRIDE_PATTERNS = [
    # German — the language these descriptions are written in.
    re.compile(
        r"(ignoriere|missachte|vergiss)\s+(alle\s+)?(vorherigen|bisherigen|obigen)",
        re.I,
    ),
    re.compile(r"du\s+bist\s+(jetzt|ab\s+sofort)", re.I),
    re.compile(r"system\s*[-_ ]?prompt", re.I),
    # French — the second language of the federal geodata this server serves.
    re.compile(r"(ignore[sz]?|oublie[sz]?)\s+(toutes\s+)?les\s+instructions", re.I),
    # English.
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
]


@pytest.fixture(scope="module")
def tools():
    return asyncio.run(mcp.list_tools())


class TestEveryToolIsReadOnly:
    """SEC-014's deferral rests on this. If it ever fails, the deferral is void."""

    def test_all_tools_declare_read_only(self, tools):
        offenders = [t.name for t in tools if not (t.annotations and t.annotations.readOnlyHint)]
        assert offenders == [], (
            f"Tools without readOnlyHint: {offenders}. SEC-014's risk-bounding "
            "argument assumes a read-only surface — re-evaluate the deferral in "
            "SECURITY.md before merging a write-capable tool."
        )

    def test_no_tool_is_destructive(self, tools):
        offenders = [
            t.name for t in tools if t.annotations and t.annotations.destructiveHint
        ]
        assert offenders == []


class TestDescriptionsAreClean:
    """SEC-015: the gateway would scan across servers; this scans our own."""

    def test_no_invisible_characters(self, tools):
        offenders = [t.name for t in tools if INVISIBLE.search(t.description or "")]
        assert offenders == [], f"Invisible characters in descriptions: {offenders}"

    @pytest.mark.parametrize("pattern", OVERRIDE_PATTERNS, ids=lambda p: p.pattern[:28])
    def test_no_override_phrasing(self, tools, pattern):
        offenders = [t.name for t in tools if pattern.search(t.description or "")]
        assert offenders == [], f"Override-style phrasing in: {offenders}"

    def test_tool_names_are_plain_ascii(self, tools):
        """Homoglyph substitution in a name is how one server shadows another."""
        offenders = [t.name for t in tools if not t.name.isascii()]
        assert offenders == []

    def test_descriptions_are_present_and_substantial(self, tools):
        """An empty description is its own problem: the model picks blind."""
        thin = [t.name for t in tools if len(t.description or "") < 40]
        assert thin == [], f"Descriptions too thin to select on: {thin}"
