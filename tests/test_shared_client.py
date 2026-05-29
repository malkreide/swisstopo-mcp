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
