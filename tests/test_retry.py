# tests/test_retry.py
"""Resilience default: exponential-backoff retry (skill Schritt 3.1)."""
from __future__ import annotations

import httpx
import pytest
import respx

from swisstopo_mcp import api_client
from swisstopo_mcp.api_client import request_with_retry

URL = "https://api3.geo.admin.ch/rest/services/test"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Patch out the real 2s/4s/8s backoff so tests run instantly."""
    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(api_client, "_sleep", fake_sleep)


@respx.mock
async def test_happy_path_no_retry():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    resp = await request_with_retry("GET", URL)
    assert resp.json() == {"ok": True}
    assert route.call_count == 1


@respx.mock
async def test_retry_on_503_then_success():
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"recovered": True}),
        ]
    )
    resp = await request_with_retry("GET", URL)
    assert resp.json() == {"recovered": True}
    assert route.call_count == 3


@respx.mock
async def test_retry_on_429():
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"ok": 1})]
    )
    resp = await request_with_retry("GET", URL)
    assert resp.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_no_retry_on_404():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await request_with_retry("GET", URL)
    assert route.call_count == 1  # fail fast, no retry on 4xx


@respx.mock
async def test_retries_exhausted_raises_last_status():
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await request_with_retry("GET", URL)
    assert route.call_count == 4  # initial + 3 retries


@respx.mock
async def test_retry_on_network_error_then_success():
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"ok": 1})]
    )
    resp = await request_with_retry("GET", URL)
    assert resp.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_timeout_exhausted_raises():
    respx.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(httpx.ReadTimeout):
        await request_with_retry("GET", URL)


async def test_host_not_on_allowlist_raises_before_request():
    with pytest.raises(PermissionError, match="Egress-Allow-List"):
        await request_with_retry("GET", "https://evil.example.com/x")
