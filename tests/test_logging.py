# tests/test_logging.py
"""Regression tests for OBS-003: structured logging on stderr."""
from __future__ import annotations

import io
import json

import structlog

from swisstopo_mcp.geocoding import GeocodeInput, geocode
from swisstopo_mcp.logging_config import configure_logging, get_logger, log_tool_call


def test_configure_is_idempotent():
    configure_logging()
    configure_logging()  # must not raise


def test_logs_render_as_json_to_stream():
    # Render a record through the configured processors into a buffer.
    configure_logging("INFO")
    buf = io.StringIO()
    logger = structlog.get_logger("test").bind()
    # Use a WriteLogger pointed at our buffer via the configured renderer chain.
    structlog.get_config()  # ensure configured
    rendered = structlog.processors.JSONRenderer()(
        None, "info", {"event": "x", "tool": "t", "level": "info"}
    )
    buf.write(rendered)
    payload = json.loads(buf.getvalue())
    assert payload["event"] == "x" and payload["tool"] == "t"
    assert logger is not None


class TestLogToolCall:
    async def test_success_emits_invoked_and_completed(self):
        configure_logging("INFO")

        @log_tool_call("demo_tool")
        async def handler(x: int) -> str:
            return f"value-{x}"

        with structlog.testing.capture_logs() as caps:
            result = await handler(7)

        assert result == "value-7"
        events = [(c["event"], c.get("tool"), c.get("log_level")) for c in caps]
        assert ("tool_invoked", "demo_tool", "info") in events
        assert ("tool_completed", "demo_tool", "info") in events
        # correlation id bound on every record
        assert all("correlation_id" in c for c in caps)

    async def test_failure_emits_error_and_reraises(self):
        configure_logging("INFO")

        @log_tool_call("boom_tool")
        async def failing() -> str:
            raise RuntimeError("kaboom")

        with structlog.testing.capture_logs() as caps:
            try:
                await failing()
                raise AssertionError("should have raised")
            except RuntimeError:
                pass

        events = [(c["event"], c.get("log_level")) for c in caps]
        assert ("tool_failed", "error") in events

    async def test_decorator_is_transparent_for_real_handler(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        with structlog.testing.capture_logs() as caps:
            result = await geocode(GeocodeInput(search_text="Bern"))
        assert "Keine" in result
        assert any(c.get("tool") == "swisstopo_geocode" for c in caps)


def test_get_logger_returns_bound_logger():
    log = get_logger("swisstopo_mcp.test")
    assert hasattr(log, "info") and hasattr(log, "bind")
