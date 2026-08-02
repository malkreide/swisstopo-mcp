"""Retry policy toward the geo upstreams (ARCH-014): Retry-After, jitter, budget.

Overpass and geodienste.ch are community/cantonal instances — the upstreams
where a synchronised retry storm does the most damage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from swisstopo_mcp import api_client as c

URL = "https://api3.geo.admin.ch/rest/services/api/MapServer/identify"


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", URL))


class TestParseRetryAfter:
    def test_delta_seconds(self):
        assert c.parse_retry_after(_resp(429, "120")) == 120.0

    def test_http_date_in_the_future(self):
        when = datetime.now(UTC) + timedelta(seconds=90)
        got = c.parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
        assert got is not None
        assert 80 <= got <= 95

    def test_http_date_in_the_past_means_now(self):
        when = datetime.now(UTC) - timedelta(hours=1)
        assert c.parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0

    def test_absent_header(self):
        assert c.parse_retry_after(_resp(429)) is None

    def test_malformed_header_does_not_raise(self):
        assert c.parse_retry_after(_resp(429, "next Tuesday")) is None
        assert c.parse_retry_after(_resp(429, "")) is None
        assert c.parse_retry_after(_resp(429, "-5")) is None

    def test_ignored_on_other_statuses(self):
        assert c.parse_retry_after(_resp(500, "30")) is None

    def test_no_response_at_all(self):
        assert c.parse_retry_after(None) is None


class TestRetryDelay:
    def test_retry_after_beats_the_backoff_table(self):
        # RETRY_BACKOFFS[0] = 2.0 spans [1, 3]s — 9 can only come from the header.
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "9"))
        assert 9.0 <= c.retry_delay(1, exc) <= 9.0 * (1 + c.RETRY_AFTER_JITTER)

    def test_retry_after_is_never_undercut(self):
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "5"))
        for _ in range(50):
            assert c.retry_delay(1, exc) >= 5.0

    def test_absurd_retry_after_is_capped(self):
        # Exactly the cap, not "the cap times jitter": capping happens after
        # jitter, otherwise MAX_DELAY_S would not be a bound at all. Equality
        # still discriminates — the bare table would give 2.0s here.
        exc = httpx.HTTPStatusError("503", request=None, response=_resp(503, "86400"))
        assert c.retry_delay(1, exc) == c.MAX_DELAY_S

    def test_the_cap_is_a_real_bound_not_a_midpoint(self):
        """MAX_DELAY_S must hold even when jitter swings up (Codex review, parlament#35)."""
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "86400"))
        for attempt in range(1, len(c.RETRY_BACKOFFS) + 1):
            for _ in range(20):
                assert c.retry_delay(attempt, None) <= c.MAX_DELAY_S
                assert c.retry_delay(attempt, exc) <= c.MAX_DELAY_S

    def test_delay_is_spread(self):
        draws = {c.retry_delay(3, None) for _ in range(30)}
        assert len(draws) > 1, "delay is deterministic — jitter is not applied"
        base = c.RETRY_BACKOFFS[2]
        assert all(base * (1 - c.JITTER_SPREAD) <= d <= base * (1 + c.JITTER_SPREAD) for d in draws)


@pytest.fixture
def fake_clock(monkeypatch):
    """A clock that only advances when the client sleeps.

    Without it the budget can never run out: patched-out sleeps take no
    wall-clock time, ``time.monotonic()`` never moves, every deadline holds
    forever, and the test would pass whatever the budget logic did.
    """
    now = {"t": 1000.0}
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    monkeypatch.setattr(c.time, "monotonic", lambda: now["t"])
    monkeypatch.setattr(c, "_sleep", _sleep)
    return slept


@respx.mock
async def test_retry_after_reaches_the_sleep(fake_clock):
    respx.get(URL).mock(side_effect=[_resp(429, "7"), httpx.Response(200, json={})])
    await c.request_with_retry("GET", URL, check_host=False)
    assert len(fake_clock) == 1
    assert 7.0 <= fake_clock[0] <= 7.0 * (1 + c.RETRY_AFTER_JITTER)


@respx.mock
async def test_the_client_is_told_the_jittered_wait_not_the_table_value(fake_clock):
    """`_notify_retry` must report the actual wait — otherwise the warning lies."""
    seen: list[str] = []

    class _Ctx:
        async def warning(self, msg):
            seen.append(msg)

    respx.get(URL).mock(side_effect=[_resp(429, "7"), httpx.Response(200, json={})])
    await c.request_with_retry("GET", URL, check_host=False, ctx=_Ctx())
    assert seen, "no retry warning was emitted"
    assert "2 s" not in seen[0], seen[0]  # the table value, where ~7s was waited


@respx.mock
async def test_404_still_fails_fast_without_waiting(fake_clock):
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await c.request_with_retry("GET", URL, check_host=False)
    assert route.call_count == 1
    assert fake_clock == []


@respx.mock
async def test_budget_cuts_the_ladder_short(fake_clock):
    route = respx.get(URL).mock(side_effect=httpx.ConnectError(""))
    with pytest.raises(httpx.ConnectError):
        await c.request_with_retry("GET", URL, check_host=False, total_budget=1.0)
    assert route.call_count < len(c.RETRY_BACKOFFS) + 1, "budget did not bound the ladder"
    assert route.call_count >= 1, "the first attempt must always go out"


@respx.mock
async def test_full_ladder_runs_when_the_budget_allows(fake_clock):
    """Counter-direction: a wide budget must not cut anything short."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectError(""))
    with pytest.raises(httpx.ConnectError):
        await c.request_with_retry("GET", URL, check_host=False, total_budget=600.0)
    assert route.call_count == len(c.RETRY_BACKOFFS) + 1


@respx.mock
async def test_per_request_timeout_is_clamped_to_the_remaining_budget(fake_clock):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={}))
    await c.request_with_retry("GET", URL, check_host=False, total_budget=4.0)
    sent = route.calls.last.request.extensions["timeout"]
    assert sent["read"] == pytest.approx(4.0), sent


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline():
    """The budget must bind even when the httpx timeout never fires.

    httpx applies its timeout per operation and the read timeout restarts with
    every chunk, so a slowly trickling response can outlast the total budget
    without any single read timing out. Hence a real ``asyncio.timeout``.

    Deliberately without ``fake_clock``: this guarantee is about real time, and
    a clock that only moves when something sleeps could not refute it. That
    blind spot is exactly what let the defect through in four sibling repos.
    """
    import asyncio as real_asyncio
    import time as real_time

    async def _slow(request):
        await real_asyncio.sleep(1.0)
        return httpx.Response(200, json={})

    respx.get(URL).mock(side_effect=_slow)
    started = real_time.monotonic()
    with pytest.raises(TimeoutError):
        await c.request_with_retry("GET", URL, check_host=False, total_budget=0.05)
    elapsed = real_time.monotonic() - started
    assert elapsed < 0.5, f"deadline did not cut: {elapsed:.2f}s"


def test_default_budget_stays_under_the_mcp_client_default():
    """Unlike the SPARQL servers there is no long-query case to protect here."""
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert c.TOTAL_BUDGET_S < MCP_DEFAULT_TIMEOUT
