# tests/test_context.py
"""Tests for Context progress/logging in long-running tools (audit finding SDK-003)."""
from __future__ import annotations

from unittest.mock import AsyncMock

from swisstopo_mcp.height import ElevationProfileInput, elevation_profile
from swisstopo_mcp.models import ToolResponse


async def test_elevation_profile_reports_progress_with_ctx(monkeypatch):
    async def mock_request(path, params=None, **_):
        return [{"alts": {"COMB": 500}, "dist": 0}, {"alts": {"COMB": 510}, "dist": 50}]

    monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
    ctx = AsyncMock()
    result = await elevation_profile(
        ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5"), ctx=ctx
    )
    assert isinstance(result, ToolResponse)
    ctx.info.assert_awaited()  # progress/info emitted via Context
    ctx.report_progress.assert_awaited()


async def test_elevation_profile_works_without_ctx(monkeypatch):
    async def mock_request(path, params=None, **_):
        return [{"alts": {"COMB": 500}, "dist": 0}, {"alts": {"COMB": 510}, "dist": 50}]

    monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
    # ctx is optional — direct calls (and unit tests) pass None
    result = await elevation_profile(ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5"))
    assert isinstance(result, ToolResponse) and result.count == 2


# ---------------------------------------------------------------------------
# Progress must be a cadence, not a completion marker (audit SDK-003)
#
# The two tests above assert only that `ctx.info` and `ctx.report_progress` were
# awaited *at all*. They passed while the single progress call fired
# `progress=1, total=1` after the upstream request had already returned — the
# actual wait was unreported — and while the two genuinely slow tools took no
# context at all. An assertion that cannot fail on the defect it names is not a
# regression test.
# ---------------------------------------------------------------------------


class _Recorder:
    """Records the order of context calls relative to the upstream request."""

    def __init__(self, timeline: list[str]) -> None:
        self._timeline = timeline

    async def info(self, message: str) -> None:
        self._timeline.append(f"info:{message[:30]}")

    async def warning(self, message: str) -> None:
        self._timeline.append(f"warning:{message[:40]}")

    async def error(self, message: str) -> None:  # pragma: no cover - unused
        self._timeline.append("error")

    async def report_progress(self, progress, total=None, message=None) -> None:
        self._timeline.append(f"progress:{progress}/{total}")


class TestProgressArrivesBeforeTheWait:
    async def test_elevation_profile_reports_before_the_upstream_call(self, monkeypatch):
        timeline: list[str] = []

        async def mock_request(path, params=None, **_):
            timeline.append("upstream")
            return [{"alts": {"COMB": 500}, "dist": 0}]

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5"), ctx=_Recorder(timeline)
        )
        upstream = timeline.index("upstream")
        before = [e for e in timeline[:upstream] if e.startswith("progress:")]
        assert before, (
            "progress fired only after the upstream call returned — that is a "
            f"completion marker, not a cadence. Timeline: {timeline}"
        )


class TestTheSlowToolsTakeAContext:
    """The two tools with the longest expected runtime had no `ctx` at all."""

    async def test_query_osm_features_announces_the_wait(self, monkeypatch):
        import httpx

        from swisstopo_mcp import overpass
        from swisstopo_mcp.overpass import QueryOsmFeaturesInput, query_osm_features

        timeline: list[str] = []

        async def fake_request(method, url, **kwargs):
            timeline.append("upstream")
            return httpx.Response(200, json={"elements": []})

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52"),
            ctx=_Recorder(timeline),
        )
        upstream = timeline.index("upstream")
        assert any(e.startswith("info:") for e in timeline[:upstream]), (
            f"the 25 s Overpass wait was not announced. Timeline: {timeline}"
        )

    async def test_find_commune_reports_each_page(self, monkeypatch):
        import httpx

        from swisstopo_mcp import openplz
        from swisstopo_mcp.openplz import FindCommuneInput, find_commune

        pages = [
            httpx.Response(200, json=[{"name": f"G{i}", "key": str(i)} for i in range(50)],
                           headers={"x-total-count": "120"}),
            httpx.Response(200, json=[{"name": f"H{i}", "key": str(i)} for i in range(50)],
                           headers={"x-total-count": "120"}),
            httpx.Response(200, json=[{"name": f"I{i}", "key": str(i)} for i in range(20)],
                           headers={"x-total-count": "120"}),
        ]
        timeline: list[str] = []

        async def fake_request(path, params=None, ctx=None):
            timeline.append("upstream")
            return pages.pop(0)

        monkeypatch.setattr(openplz, "openplz_request", fake_request)
        monkeypatch.setattr(openplz, "_resolve_canton_key", lambda c, ctx=None: _async("ZH"))
        await find_commune(FindCommuneInput(canton="ZH"), ctx=_Recorder(timeline))

        progress = [e for e in timeline if e.startswith("progress:")]
        assert len(progress) >= 3, (
            "a 3-page fetch reported fewer than 3 progress events — that is a "
            f"completion marker again. Timeline: {timeline}"
        )
        assert progress[0] != progress[-1], "progress never advanced"


async def _async(value):
    return value


class TestRetriesAreNotSilent:
    """A full retry chain adds 2+4+8 s of silence, and no ctx reached
    `api_client` at all — so even the context-aware tools said nothing during
    the single longest source of unexplained latency in this server."""

    async def test_each_retry_warns(self, monkeypatch):
        import httpx

        from swisstopo_mcp import api_client

        attempts = {"n": 0}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def request(self, method, url, **kwargs):
                attempts["n"] += 1
                if attempts["n"] <= 2:
                    raise httpx.ConnectError("down")
                return httpx.Response(200, json={}, request=httpx.Request(method, url))

        monkeypatch.setattr(api_client, "_get_client", lambda: _async(_Client()))
        monkeypatch.setattr(api_client, "_sleep", lambda s: _async(None))
        monkeypatch.setattr(api_client, "assert_host_allowed", lambda url: None)

        timeline: list[str] = []
        await api_client.request_with_retry(
            "GET", "https://api3.geo.admin.ch/x", ctx=_Recorder(timeline)
        )
        warnings = [e for e in timeline if e.startswith("warning:")]
        assert len(warnings) == 2, f"expected one warning per retry, got {timeline}"
        assert "api3.geo.admin.ch" in warnings[0]

    async def test_a_broken_context_does_not_fail_the_request(self, monkeypatch):
        """Reporting is best-effort: a session that has gone away must not turn
        a recoverable upstream blip into a failed tool call."""
        import httpx

        from swisstopo_mcp import api_client

        attempts = {"n": 0}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def request(self, method, url, **kwargs):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise httpx.ConnectError("down")
                return httpx.Response(200, json={}, request=httpx.Request(method, url))

        class _DeadContext:
            async def warning(self, message):
                raise RuntimeError("session closed")

        monkeypatch.setattr(api_client, "_get_client", lambda: _async(_Client()))
        monkeypatch.setattr(api_client, "_sleep", lambda s: _async(None))
        monkeypatch.setattr(api_client, "assert_host_allowed", lambda url: None)

        response = await api_client.request_with_retry(
            "GET", "https://api3.geo.admin.ch/x", ctx=_DeadContext()
        )
        assert response.status_code == 200


class TestSwallowedLegendFailureIsSurfaced:
    """`except Exception: meta["legend"] = None` left the caller unable to tell
    "this layer has no legend" from "the legend fetch broke"."""

    async def test_legend_failure_sets_status_and_warns(self, monkeypatch):
        from swisstopo_mcp import rest_api
        from swisstopo_mcp.rest_api import LayerInfoInput, layer_info

        async def fake_meta(path, params=None, **_):
            return {"id": "ch.x", "name": "X", "fields": []}

        async def broken_legend(path, params=None, **_):
            raise RuntimeError("legend endpoint down")

        monkeypatch.setattr(rest_api, "geo_admin_request", fake_meta)
        monkeypatch.setattr(rest_api, "geo_admin_request_text", broken_legend)

        timeline: list[str] = []
        result = await layer_info(LayerInfoInput(layer="ch.x"), ctx=_Recorder(timeline))

        assert result.results[0]["legend"] is None
        assert result.results[0]["legend_status"] == "unavailable"
        assert any(e.startswith("warning:") for e in timeline), (
            "a failed legend fetch was still silent"
        )

    async def test_successful_legend_is_marked_ok(self, monkeypatch):
        from swisstopo_mcp import rest_api
        from swisstopo_mcp.rest_api import LayerInfoInput, layer_info

        async def fake_meta(path, params=None, **_):
            return {"id": "ch.x", "name": "X", "fields": []}

        async def legend(path, params=None, **_):
            return "<p>Legende</p>"

        monkeypatch.setattr(rest_api, "geo_admin_request", fake_meta)
        monkeypatch.setattr(rest_api, "geo_admin_request_text", legend)

        result = await layer_info(LayerInfoInput(layer="ch.x"))
        assert result.results[0]["legend_status"] == "ok"


# ---------------------------------------------------------------------------
# The mechanism, not the instances (audit SDK-003)
#
# Threading `ctx` through by hand is exactly the kind of work that rots: a new
# helper takes an optional `ctx` for symmetry and never forwards it, and the
# tool still *looks* context-aware from its signature. That is not hypothetical
# — it was the state of `_find_by_name`, the most-used mode of
# `swisstopo_find_commune`, one of the two tools this finding named. It took a
# `ctx` and dropped it, so a retry storm on a lookup by name stayed silent
# while the same tool's `canton=` mode reported per page. `_get_canton_index`
# was the same shape: one uncached upstream request on the canton path, with no
# context reaching it.
#
# Per-call assertions cannot catch that class — they only cover the paths
# somebody remembered to write a test for. These two sweep the source instead.
# ---------------------------------------------------------------------------

#: Every helper that reaches an upstream host. A `ctx` in scope must be passed
#: to these, or the retry backoff behind them goes unreported.
REQUEST_HELPERS = {
    "openplz_request",
    "geo_admin_request",
    "geo_admin_request_text",
    "stac_request",
    "request_with_retry",
}


def _functions_taking_ctx():
    """Yield (path, ast node) for every function in src/ that accepts a `ctx`."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parent.parent / "src" / "swisstopo_mcp"
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if "ctx" in [a.arg for a in node.args.args + node.args.kwonlyargs]:
                yield path, node


class TestEveryContextThatIsAcceptedIsAlsoUsed:
    def test_no_function_takes_a_ctx_it_never_references(self):
        import ast

        dead = [
            f"{path.name}:{fn.lineno} {fn.name}"
            for path, fn in _functions_taking_ctx()
            if not any(isinstance(n, ast.Name) and n.id == "ctx" for n in ast.walk(fn))
        ]
        assert dead == [], (
            "these accept a Context and never touch it — the signature promises "
            f"progress reporting the body does not do: {dead}"
        )

    def test_every_call_that_could_carry_the_ctx_does(self):
        """The chain, not just its last link.

        Checking only the five request helpers would have missed
        `_list_by_canton() -> _resolve_canton_key()`: the break was one link
        further up, in a helper that reaches the network only indirectly. So
        the target set is every function in `src/` that accepts a `ctx` —
        derived from the source, not listed here, so a new helper joins it
        automatically.

        `ctx` counts as forwarded whether it is passed positionally or by
        keyword; both styles are in use and neither is wrong.
        """
        import ast

        targets = {fn.name for _, fn in _functions_taking_ctx()} | REQUEST_HELPERS
        missed = []
        for path, fn in _functions_taking_ctx():
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                if name not in targets or name == fn.name:
                    continue
                forwarded = any(
                    isinstance(a, ast.Name) and a.id == "ctx" for a in call.args
                ) or any(kw.arg == "ctx" for kw in call.keywords)
                if not forwarded:
                    missed.append(f"{path.name}:{call.lineno} {fn.name}() -> {name}()")
        assert missed == [], (
            "a callee that accepts a Context was called from a function that has "
            f"one, without passing it — the progress chain breaks here: {missed}"
        )

    def test_the_sweep_actually_looks_at_something(self):
        """A sweep over an empty set passes for the wrong reason."""
        found = {fn.name for _, fn in _functions_taking_ctx()}
        assert len(found) > 10, f"the ctx sweep found almost nothing: {found}"
        assert "_find_by_name" in found


class TestFindCommuneByNameReportsRetries:
    """The behavioural half of the guard above — the path that was actually
    broken, asserted through the public tool rather than the helper."""

    async def test_a_retry_on_the_name_path_warns(self, monkeypatch):
        import httpx

        from swisstopo_mcp import api_client
        from swisstopo_mcp.openplz import FindCommuneInput, find_commune

        attempts = {"n": 0}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def request(self, method, url, **kwargs):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise httpx.ConnectError("down")
                return httpx.Response(
                    200, json=[], request=httpx.Request(method, url)
                )

        monkeypatch.setattr(api_client, "_get_client", lambda: _async(_Client()))
        monkeypatch.setattr(api_client, "_sleep", lambda s: _async(None))
        monkeypatch.setattr(api_client, "assert_host_allowed", lambda url: None)

        timeline: list[str] = []
        result = await find_commune(
            FindCommuneInput(name="Uster"), ctx=_Recorder(timeline)
        )

        assert result.is_error is False, result.summary
        assert any(e.startswith("warning:") for e in timeline), (
            "a retry on the commune-by-name path was silent; the tool takes a "
            f"Context but this mode dropped it. Timeline: {timeline}"
        )
