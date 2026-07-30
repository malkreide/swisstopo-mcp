# tests/test_shared_client.py
"""Regression tests for SDK-001: shared httpx.AsyncClient reuse via lifespan."""
from __future__ import annotations

import httpx
import pytest

from swisstopo_mcp import api_client
from swisstopo_mcp.api_client import _get_client, create_shared_client, set_shared_client


@pytest.fixture(autouse=True)
def _reset_shared_client():
    set_shared_client(None)
    yield
    set_shared_client(None)


def test_build_client_disables_redirects():
    client = create_shared_client()
    try:
        assert client.follow_redirects is False
    finally:
        # not async-closing in a sync test; drop the reference
        del client


async def test_get_client_falls_back_to_ephemeral_when_no_shared():
    async with await _get_client() as client:
        assert isinstance(client, httpx.AsyncClient)


async def test_get_client_reuses_shared_and_does_not_close_it():
    shared = create_shared_client()
    set_shared_client(shared)
    try:
        async with await _get_client() as c1:
            assert c1 is shared
        # context exit must NOT close the shared client
        assert shared.is_closed is False
        async with await _get_client() as c2:
            assert c2 is shared  # same instance reused across calls
    finally:
        await shared.aclose()


def test_set_shared_client_registers_and_clears():
    assert api_client._shared_client is None
    sentinel = object()
    set_shared_client(sentinel)  # type: ignore[arg-type]
    assert api_client._shared_client is sentinel
    set_shared_client(None)
    assert api_client._shared_client is None


# ---------------------------------------------------------------------------
# Concurrent-session ownership (audit SDK-001)
#
# The tests above exercise set/get in isolation and cannot see the defect that
# actually shipped: under streamable-http the MCPServer lifespan runs once per MCP
# *session*, not once per process. Each new session overwrote the shared client,
# and the first session to disconnect closed it and shut tracing down for every
# session still connected — silently degrading them to a fresh client per tool
# call. These tests assert the ownership property directly.
# ---------------------------------------------------------------------------


@pytest.fixture
def _reset_refcount():
    from swisstopo_mcp import server

    server._resource_refs = 0
    server._resource_client = None
    yield
    server._resource_refs = 0
    server._resource_client = None


class TestSessionLifespanOwnership:
    async def test_second_session_reuses_the_first_clients(self, _reset_refcount):
        from swisstopo_mcp import server

        async with server.lifespan(server.mcp):
            first = api_client._shared_client
            assert first is not None
            async with server.lifespan(server.mcp):
                assert api_client._shared_client is first, (
                    "a second session built its own client and clobbered the first"
                )

    async def test_closing_one_session_leaves_the_others_working(self, _reset_refcount):
        from swisstopo_mcp import server

        outer = server.lifespan(server.mcp)
        await outer.__aenter__()
        shared = api_client._shared_client

        inner = server.lifespan(server.mcp)
        await inner.__aenter__()
        await inner.__aexit__(None, None, None)  # one session disconnects

        try:
            assert api_client._shared_client is shared, (
                "one session's teardown cleared the shared client for the others"
            )
            assert shared is not None and shared.is_closed is False
            async with await _get_client() as c:
                assert c is shared, "surviving session fell back to an ephemeral client"
        finally:
            await outer.__aexit__(None, None, None)

    async def test_last_exit_releases_everything(self, _reset_refcount):
        from swisstopo_mcp import server

        async with server.lifespan(server.mcp):
            shared = api_client._shared_client
        assert api_client._shared_client is None
        assert shared is not None and shared.is_closed is True
        assert server._resource_refs == 0

    async def test_http_app_lifespan_holds_a_reference(self, _reset_refcount):
        """The ASGI-level hold is what makes the HTTP transport safe: while the
        app is up, no session teardown can reach a refcount of zero."""
        from swisstopo_mcp import server

        app = server.build_http_app([])
        async with app.router.lifespan_context(app):
            shared = api_client._shared_client
            assert shared is not None
            # A whole session opens and closes underneath the app.
            async with server.lifespan(server.mcp):
                pass
            assert api_client._shared_client is shared
            assert shared.is_closed is False
        assert api_client._shared_client is None
