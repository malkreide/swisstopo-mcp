"""OpenTelemetry tracing (audit finding OBS-006).

structlog already emits a `duration_ms` per tool call, so this adds the missing
half: the *causal* view. A slow tool call is attributable to the upstream
request inside it only if the two share a trace, which is what the httpx
auto-instrumentation gives us.

**Inert unless configured.** `setup_tracing()` does nothing when
`OTEL_EXPORTER_OTLP_ENDPOINT` is unset, which is the local stdio case — the
default install pays no runtime cost and emits nothing.

**What deliberately never becomes a span attribute:** tool arguments. They are
coordinates, addresses and search terms typed by a user, and an observability
backend is the wrong place for them. The finding calls this out explicitly and
it holds regardless of how convenient the debugging would be.
"""
from __future__ import annotations

import os
from typing import Any

from swisstopo_mcp.logging_config import get_logger

_log = get_logger("swisstopo_mcp.observability")

DEFAULT_SERVICE_NAME = "swisstopo-mcp"

# Set once by setup_tracing(); None means tracing is off and the decorators
# below must stay out of the way entirely.
_tracer: Any | None = None
_instrumented = False


def tracing_enabled() -> bool:
    """True when an OTLP endpoint was configured and setup_tracing() ran."""
    return _tracer is not None


def get_tracer() -> Any | None:
    """Return the tracer, or None when tracing is off."""
    return _tracer


def setup_tracing() -> bool:
    """Install a TracerProvider and instrument httpx. Returns True if enabled.

    Must run *before* the shared httpx client is created: the httpx
    auto-instrumentation patches the client class, so a client built earlier
    would never be traced.
    """
    global _tracer, _instrumented

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        _log.debug("tracing_disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT unset")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover - dependency is declared, not optional
        _log.warning("tracing_unavailable", reason="opentelemetry packages missing")
        return False

    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    # OTEL_RESOURCE_ATTRIBUTES (e.g. deployment.environment=production) is read
    # by Resource.create() itself, so it does not need handling here.
    resource = Resource.create({"service.name": service_name})

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    if not _instrumented:
        HTTPXClientInstrumentor().instrument()
        _instrumented = True

    _tracer = trace.get_tracer("swisstopo_mcp")
    _log.info("tracing_enabled", service_name=service_name, endpoint=endpoint)
    return True


def shutdown_tracing() -> None:
    """Flush pending spans. Called from the server lifespan on shutdown."""
    global _tracer
    if _tracer is None:
        return
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception:  # pragma: no cover - shutdown must never mask a real error
        _log.warning("tracing_shutdown_failed", exc_info=True)
    finally:
        _tracer = None


def reset_for_tests() -> None:
    """Clear module state so tests can exercise setup_tracing() repeatedly."""
    global _tracer, _instrumented
    _tracer = None
    _instrumented = False
