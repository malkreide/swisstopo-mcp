"""Guards against the version drift that made the User-Agent lie.

Three numbers had come apart: `pyproject.toml` said 0.3.0, `__init__.__version__`
said 0.2.0, and the hard-coded `USER_AGENT` in `api_client.py` said 0.1 — the
latter never having been current since the first release. Every request to
geo.admin.ch, REFRAME, STAC, Overpass and OpenPLZ carried that stale value.

These tests fail if anyone reintroduces a literal.
"""

import tomllib
from pathlib import Path

import swisstopo_mcp
from swisstopo_mcp import api_client

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


def test_version_matches_pyproject():
    """The single source of truth is pyproject.toml, via distribution metadata."""
    assert swisstopo_mcp.__version__ == _pyproject_version()


def test_user_agent_carries_the_real_version():
    expected = (
        f"SwisstopoMCP/{_pyproject_version()} "
        "(MCP Server; +https://github.com/malkreide/swisstopo-mcp)"
    )
    assert api_client.USER_AGENT == expected


def test_user_agent_is_not_a_source_checkout_marker():
    """In CI the package is installed, so the fallback must not be in play.

    If this fails, `importlib.metadata` did not find the distribution — the
    User-Agent would then go out as `0.0.0+source` instead of a real version.
    """
    assert "+source" not in api_client.USER_AGENT
