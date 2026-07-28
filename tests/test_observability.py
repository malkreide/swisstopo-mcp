# tests/test_observability.py
"""Tracing tests (audit OBS-006).

The load-bearing property is that tracing is **inert unless configured**: the
default install and the local stdio workflow must see no behaviour change and
emit nothing.
"""
from __future__ import annotations

import pytest

from swisstopo_mcp import observability
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import ToolResponse


@pytest.fixture(autouse=True)
def _reset():
    observability.reset_for_tests()
    yield
    observability.reset_for_tests()


class TestInertWithoutEndpoint:
    def test_setup_is_a_noop_without_endpoint(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        assert observability.setup_tracing() is False
        assert observability.tracing_enabled() is False
        assert observability.get_tracer() is None

    def test_empty_endpoint_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   ")
        assert observability.setup_tracing() is False

    def test_shutdown_without_setup_is_safe(self):
        observability.shutdown_tracing()  # must not raise

    async def test_decorated_tool_works_untraced(self):
        """The stdio path must be unaffected — no tracer, no span, same result."""

        @log_tool_call("swisstopo_test")
        async def handler() -> ToolResponse:
            return ToolResponse.ok("fine", [{"a": 1}])

        out = await handler()
        assert out.summary == "fine"
        assert observability.get_tracer() is None


class TestSpansWhenEnabled:
    """Drive a real TracerProvider with an in-memory exporter rather than
    asserting on mocks — the point is that spans actually come out."""

    @pytest.fixture
    def spans(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        observability._tracer = provider.get_tracer("test")
        yield exporter
        observability.reset_for_tests()

    async def test_successful_call_emits_one_span(self, spans):
        @log_tool_call("swisstopo_zoning_at")
        async def handler() -> ToolResponse:
            return ToolResponse.ok("ok", [])

        await handler()
        finished = spans.get_finished_spans()
        assert len(finished) == 1
        assert finished[0].name == "mcp.tool/swisstopo_zoning_at"
        assert finished[0].attributes["mcp.tool.name"] == "swisstopo_zoning_at"
        assert finished[0].attributes["mcp.tool.result.is_error"] is False

    async def test_handled_error_is_marked_on_the_span(self, spans):
        """A handled error returns normally, so the flag must come from the
        envelope rather than from an exception."""

        @log_tool_call("swisstopo_get_height")
        async def handler() -> ToolResponse:
            return ToolResponse.error("upstream down")

        await handler()
        span = spans.get_finished_spans()[0]
        assert span.attributes["mcp.tool.result.is_error"] is True

    async def test_raised_exception_is_recorded(self, spans):
        @log_tool_call("swisstopo_boom")
        async def handler() -> ToolResponse:
            raise RuntimeError("kaboom")

        with pytest.raises(RuntimeError):
            await handler()
        span = spans.get_finished_spans()[0]
        assert span.attributes["mcp.tool.result.is_error"] is True
        assert any(e.name == "exception" for e in span.events)

    async def test_arguments_never_reach_span_attributes(self, spans):
        """Coordinates, addresses and search terms are user input and must not
        land in a tracing backend — the finding calls this out explicitly."""

        @log_tool_call("swisstopo_geocode")
        async def handler(search_text: str, lat: float) -> ToolResponse:
            return ToolResponse.ok("ok", [])

        await handler(search_text="Seilergraben 76, Zürich", lat=47.3769)
        attrs = spans.get_finished_spans()[0].attributes
        blob = " ".join(f"{k}={v}" for k, v in attrs.items())
        assert "Seilergraben" not in blob
        assert "47.3769" not in blob
        assert set(attrs) == {"mcp.tool.name", "mcp.tool.result.is_error"}


# ---------------------------------------------------------------------------
# The httpx child spans (audit OBS-006)
#
# `test_arguments_never_reach_span_attributes` above asserts the exclusion on
# the span this module *writes*, and it passed while the leak was live: the
# httpx auto-instrumentation this module *enables* exported `http.url` with the
# full query string. The test's own claim ("must not land in a tracing backend")
# was broader than what it verified.
#
# These tests enable the instrumentation, which is the only way to see it.
# ---------------------------------------------------------------------------

SECRET_QUERY = {"searchText": "Seilergraben 76, Zürich", "lat": 47.3769}


class TestScrubUrl:
    def test_drops_the_query_string(self):
        from swisstopo_mcp.observability import _scrub_url

        out = _scrub_url("https://api3.geo.admin.ch/rest/x?searchText=Z%C3%BCrich&lat=47.3")
        assert out == "https://api3.geo.admin.ch/rest/x"

    def test_drops_the_fragment(self):
        from swisstopo_mcp.observability import _scrub_url

        assert _scrub_url("https://a.example/p#frag") == "https://a.example/p"

    def test_drops_userinfo(self):
        from swisstopo_mcp.observability import _scrub_url

        assert _scrub_url("https://user:pw@a.example/p") == "https://a.example/p"

    def test_keeps_the_port(self):
        from swisstopo_mcp.observability import _scrub_url

        assert _scrub_url("https://a.example:8443/p?q=1") == "https://a.example:8443/p"

    def test_keeps_scheme_host_and_path(self):
        """Scrubbing must not make the span useless — which upstream was called
        and how long it took is the reason the child span exists."""
        from swisstopo_mcp.observability import _scrub_url

        out = _scrub_url("https://api3.geo.admin.ch/rest/services/ech/SearchServer?a=1")
        assert out.startswith("https://api3.geo.admin.ch/")
        assert "SearchServer" in out


class TestHttpxChildSpansCarryNoArguments:
    """End to end: instrument httpx for real, issue a request, read the spans."""

    @pytest.fixture
    def spans(self):
        """Own provider, passed explicitly: the global one can only be set once
        per process, and other tests in this file already claim it."""
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        exporter._provider = provider  # carried to _spans_for
        yield exporter

    @staticmethod
    async def _spans_for(exporter, url, params, fail=False):
        import httpx
        import respx
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        from swisstopo_mcp.observability import _install_url_scrubber

        instrumentor = HTTPXClientInstrumentor()
        _install_url_scrubber(instrumentor, tracer_provider=exporter._provider)
        try:
            with respx.mock:
                route = respx.get(url__regex=r".*")
                if fail:
                    route.mock(side_effect=httpx.ConnectError("down"))
                else:
                    route.mock(return_value=httpx.Response(200, json={}))
                async with httpx.AsyncClient() as client:
                    try:
                        await client.get(url, params=params)
                    except httpx.ConnectError:
                        pass
        finally:
            instrumentor.uninstrument()
        return exporter.get_finished_spans()

    async def test_query_string_is_not_exported(self, spans):
        emitted = await self._spans_for(
            spans, "https://api3.geo.admin.ch/rest/services/ech/SearchServer", SECRET_QUERY
        )
        assert emitted, "no httpx span was recorded — the test would pass vacuously"
        blob = " ".join(
            f"{k}={v}" for s in emitted for k, v in (s.attributes or {}).items()
        )
        assert "Seilergraben" not in blob
        assert "47.3769" not in blob
        assert "searchText" not in blob

    async def test_the_upstream_is_still_identifiable(self, spans):
        emitted = await self._spans_for(
            spans, "https://api3.geo.admin.ch/rest/services/ech/SearchServer", SECRET_QUERY
        )
        blob = " ".join(
            f"{k}={v}" for s in emitted for k, v in (s.attributes or {}).items()
        )
        assert "api3.geo.admin.ch" in blob
        assert "SearchServer" in blob

    async def test_the_error_path_is_scrubbed_too(self, spans):
        """The reason this uses the *request* hook: no response arrives on a
        connection error, so a response hook never runs and the raw URL would
        be exported intact. Measured, not assumed."""
        emitted = await self._spans_for(
            spans, "https://api3.geo.admin.ch/boom", SECRET_QUERY, fail=True
        )
        assert emitted, "no httpx span was recorded on the error path"
        blob = " ".join(
            f"{k}={v}" for s in emitted for k, v in (s.attributes or {}).items()
        )
        assert "Seilergraben" not in blob, "query string leaked on the failure path"
