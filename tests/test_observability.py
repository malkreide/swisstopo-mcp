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
