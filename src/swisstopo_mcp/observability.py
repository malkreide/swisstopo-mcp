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

That exclusion has to be enforced in two places, which is what the re-audit
caught: the tool span this module writes never carried arguments, but the httpx
auto-instrumentation it *enables* exported `http.url` complete with the query
string — `?searchText=Seilergraben+76,+Zürich&lat=47.3769`. True of the span we
write, false of the system we configure. `_scrub_url` and the request hook below
close that; see `_install_url_scrubber`.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from swisstopo_mcp.logging_config import get_logger

_log = get_logger("swisstopo_mcp.observability")

DEFAULT_SERVICE_NAME = "swisstopo-mcp"

# Set once by setup_tracing(); None means tracing is off and the decorators
# below must stay out of the way entirely.
_tracer: Any | None = None
_instrumented = False


# Span attributes that carry a full request URL. The name depends on which HTTP
# semantic-convention version the instrumentation emits (`http.url` in the
# stable-legacy mode, `url.full`/`url.query` in the newer one), so all of them
# are scrubbed rather than guessing which is active.
_URL_ATTRIBUTES = ("http.url", "url.full")
_QUERY_ATTRIBUTES = ("url.query",)


def _scrub_url(url: str) -> str:
    """Drop the query string, fragment and any userinfo from a URL.

    What survives is scheme, host and path — enough to see *which* upstream was
    called and how long it took, which is the whole point of the child span.
    What goes is the query string, where every tool argument that becomes a
    parameter ends up: search text, coordinates, canton, PLZ, the Overpass area.

    The path is deliberately kept. It can still carry an identifier the caller
    supplied (`collection_id`, a feature id), so this narrows the exposure
    rather than eliminating it — a trade against making the span useless. If
    that ever needs to go too, template the path here.
    """
    try:
        parts = urlsplit(url)
    except ValueError:  # pragma: no cover - urlsplit is very permissive
        return "<unparseable>"
    # netloc without userinfo: hostname[:port]
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _scrub_span_urls(span: Any) -> None:
    """Overwrite any URL-bearing attribute the instrumentation already set."""
    if span is None or not span.is_recording():
        return
    attributes = span.attributes or {}
    for key in _URL_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str):
            span.set_attribute(key, _scrub_url(value))
    for key in _QUERY_ATTRIBUTES:
        if key in attributes:
            span.set_attribute(key, "")


async def _async_request_hook(span: Any, request: Any) -> None:
    _scrub_span_urls(span)


def _sync_request_hook(span: Any, request: Any) -> None:
    _scrub_span_urls(span)


def _install_url_scrubber(instrumentor: Any, tracer_provider: Any | None = None) -> None:
    """Instrument httpx with the URL scrubber attached.

    `tracer_provider` is for tests: the global provider can only be set once per
    process, so a test that needs its own exporter passes it here rather than
    fighting `set_tracer_provider`. Production leaves it None and the
    instrumentation resolves the global provider itself.

    The *request* hook, not the response hook: measured against this
    instrumentation version, the request hook fires on both the success and the
    connection-error path, while the response hook never runs when no response
    arrives — so a failed upstream call would export its query string intact.
    `tests/test_observability.py` covers both paths, so an instrumentation
    upgrade that reorders this fails the build rather than silently reopening
    the leak.

    `httpx.AsyncClient` uses the async hooks and `httpx.Client` the sync ones;
    both are registered so the choice of client cannot reopen it either.
    """
    kwargs: dict[str, Any] = {
        "request_hook": _sync_request_hook,
        "async_request_hook": _async_request_hook,
    }
    if tracer_provider is not None:
        kwargs["tracer_provider"] = tracer_provider
    instrumentor.instrument(**kwargs)


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
        _install_url_scrubber(HTTPXClientInstrumentor())
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
