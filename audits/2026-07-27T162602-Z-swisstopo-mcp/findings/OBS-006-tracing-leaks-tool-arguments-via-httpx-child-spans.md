## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Two of the three claims survive a running interpreter. The no-op behaviour is exactly
as advertised, verified four ways: with `OTEL_EXPORTER_OTLP_ENDPOINT` unset,
`setup_tracing()` returns `False`, `httpx.AsyncClient.send` is not patched, the global
provider stays `ProxyTracerProvider`, and the real stdio server logs
`{"reason": "OTEL_EXPORTER_OTLP_ENDPOINT unset", "event": "tracing_disabled"}`. The
tool span carries exactly `{'mcp.tool.name', 'mcp.tool.result.is_error'}` — no
arguments.

The third is refuted. With tracing enabled, the httpx auto-instrumentation that
`observability.py:79` switches on emits a child span with
`http.url = https://api3.geo.admin.ch/...?searchText=Seilergraben+76%2C+Z%C3%BCrich&lat=47.3769`.
Every tool argument that becomes a query parameter is exported verbatim. The test at
`tests/test_observability.py:104` never enables the instrumentation, so it passes
while the leak path is untested.

### Expected Behavior
- Tool arguments never become span attributes
- Per-call spans with tool name and outcome

### Evidence
- SDK present and wired: pyproject.toml:38-41 declares opentelemetry-api/sdk/exporter-otlp/instrumentation-httpx as runtime (not optional) dependencies; src/swisstopo_mcp/observability.py:58-84 builds a TracerProvider with a Resource carrying service.name, adds BatchSpanProcessor(OTLPSpanExporter()) and calls HTTPXClientInstrumentor().instrument(). setup_tracing() runs first in the lifespan at src/swisstopo_mcp/server.py:36, before create_shared_client() at server.py:37 — the ordering the httpx patching requires.
- RUNTIME VERIFIED — the no-op claim holds. With OTEL_EXPORTER_OTLP_ENDPOINT unset: setup_tracing() → False, tracing_enabled() → False, get_tracer() → None, httpx.AsyncClient.send is NOT patched, and the global provider stays the inert ProxyTracerProvider. A @log_tool_call-decorated handler still returned its result unchanged. Driving the real stdio server with SWISSTOPO_LOG_LEVEL=DEBUG produced {"reason": "OTEL_EXPORTER_OTLP_ENDPOINT unset", "event": "tracing_disabled"} and nothing else tracing-related. Guard at observability.py:53-56; an all-whitespace value also counts as unset (.strip()).
- RUNTIME VERIFIED — the tool span itself excludes arguments. With a real TracerProvider + InMemorySpanExporter and a handler invoked as handler(search_text="Seilergraben 76, Zürich", lat=47.3769), the emitted span `mcp.tool/swisstopo_geocode` carried exactly {'mcp.tool.name': 'swisstopo_geocode', 'mcp.tool.result.is_error': False} — no argument values, no extra keys. Implementation at src/swisstopo_mcp/logging_config.py:88-115.
- RUNTIME REFUTED — the argument-exclusion claim fails end to end. Set OTEL_EXPORTER_OTLP_ENDPOINT, ran setup_tracing() (which returned True and instrumented httpx), then issued a real geo_admin_request through the respx-mocked client. The httpx auto-instrumentation emitted a child span `GET` with http.url = `https://api3.geo.admin.ch/rest/services/ech/SearchServer?searchText=Seilergraben+76%2C+Z%C3%BCrich&lat=47.3769`. The user's address and coordinates land in the observability backend verbatim as a span attribute — via the very instrumentation observability.py:79 enables. The exclusion is enforced on the parent span only; the child span defeats it.
- Handled errors are read from the envelope rather than inferred: logging_config.py:110-115 sets mcp.tool.result.is_error from getattr(result, 'is_error', False), and exceptions are recorded at logging_config.py:99-101. Both covered by tests/test_observability.py:81-102.
- OTLP configuration is env-driven and documented, not hardcoded: deploy/kubernetes.yaml:51-56 sets OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT (empty = off) and OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production; docs/deployment.md:58-60 documents all three.

Gaps:
- The httpx child spans carry full request URLs including query strings. Every tool argument that becomes a query parameter — geocoding search text, coordinates, canton, PLZ, layer and feature IDs, the Overpass area — is exported to the tracing backend. Needs a span processor or an httpx-instrumentation url-sanitising hook that strips or hashes the query string before export.
- tests/test_observability.py:104-117 asserts argument exclusion on the tool span only. It never enables the httpx instrumentation, so the test passes while the actual leak path is untested — the test's own claim ("must not land in a tracing backend") is broader than what it verifies.
- No mcp.user.id attribute. Defensible here (auth_model=none, no identity exists), but the check lists it as a per-call span requirement, so the user-behaviour-analysis workflow the check motivates is unavailable.

### Risk Description
"Arguments are excluded" is true of the span the module writes and false of the system
the module configures. The leak only bites when tracing is switched on — that is,
precisely in the cloud deployment this check applies to. Addresses, coordinates,
canton, PLZ and the Overpass area land in the observability backend, which typically
has a different retention policy and a wider access list than the server itself. The
test's stated claim ("must not land in a tracing backend") is broader than what it
verifies, so the gap is invisible to CI.

### Remediation
1. Sanitise the URL before export — either an httpx-instrumentation hook that strips
   or hashes the query string, or a span processor that rewrites `http.url` and
   `url.query` on child spans.
2. Extend `tests/test_observability.py` to enable the httpx instrumentation and assert
   no argument value appears in any exported span, parent or child. Testing only the
   span you wrote is what let this through.
3. Document the residual: even with query strings stripped, the request path can carry
   identifiers (`collection_id`, feature IDs).

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Implemented and recorded as closed in the same batch. The no-op and tool-span claims hold; the exclusion claim does not survive end to end.

### Auditor Notes
Two of the three claims survive contact with a running interpreter: the
no-op behaviour is exactly as advertised (verified four ways, including
against the real stdio server), and the tool span carries only the tool
name and the error flag. The third does not. "Tool arguments never become
span attributes" is true of the span the module writes and false of the
system the module configures: enabling httpx auto-instrumentation is what
puts `?searchText=Seilergraben+76,+Zürich&lat=47.3769` into an exported
span attribute. Since this only bites when tracing is switched on — i.e.
precisely in the cloud deployment this check applies to — it is a real
defect rather than a documentation nit. Partial.

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed.** Reproduced first: with the instrumentation enabled, the child span
carried
`http.url = https://api3.geo.admin.ch/rest/services/ech/SearchServer?searchText=Seilergraben+76%2C+Z%C3%BCrich&lat=47.3769`
— the finding's measurement exactly.

`_install_url_scrubber` now attaches a hook that rewrites every URL-bearing span
attribute through `_scrub_url`, which drops the query string, the fragment and
any userinfo. Scheme, host and path survive, so the span still answers *which*
upstream was called and how long it took. Both the sync and async hook variants
are registered — `httpx.AsyncClient` uses the async ones and `httpx.Client` the
sync ones, so the choice of client cannot reopen the leak — and `http.url`,
`url.full` and `url.query` are all handled, since which of them the
instrumentation emits depends on the active semantic-convention mode.

**The request hook, not the response hook, and that was measured rather than
assumed.** A comparison run showed the response hook never fires when no
response arrives, so a connection error would have exported its query string
intact:

| hook | success path | connection-error path |
|---|---|---|
| response only | scrubbed | **leaked** |
| request only | scrubbed | scrubbed |

Verified end to end against the real `setup_tracing()` and a real
`geo_admin_request`: `http.url` comes out as
`https://api3.geo.admin.ch/rest/services/ech/SearchServer`.

**The test gap is the substantive half of this fix.**
`test_arguments_never_reach_span_attributes` passed throughout the leak, because
it asserts on the span this module *writes* and never enables the
instrumentation this module *configures*. Eight tests added that do enable it,
including one on the connection-error path and one asserting the upstream is
still identifiable — scrubbing that made the span useless would be a different
kind of failure. Two were verified to fail against the previous implementation,
and each asserts a span was actually recorded first, so they cannot pass
vacuously.

**Residual, stated deliberately:** the path is kept, and it can still carry a
caller-supplied identifier (`collection_id`, a feature id). This narrows the
exposure rather than eliminating it; the docstring says so and names path
templating as the next step if that is ever needed. The absent `mcp.user.id`
attribute remains inapplicable — there is no auth model, so no identity exists.
