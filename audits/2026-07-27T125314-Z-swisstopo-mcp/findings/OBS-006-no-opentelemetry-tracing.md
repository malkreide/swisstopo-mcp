## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10

### Observed Behavior

The check applies (`is_cloud_deployed == true`, corroborated by `Dockerfile`, `deploy/kubernetes.yaml`, `deploy/ingress-sticky-sessions.yaml`, `docs/deployment.md` and a dual-transport HTTP app with `/healthz` at `src/swisstopo_mcp/server.py:657-683`), and nothing that satisfies it exists. This is an absence, not a partial implementation.

- **No OpenTelemetry SDK anywhere in the dependency tree:** `pyproject.toml:31-40` (`[project].dependencies` = `mcp[cli]`, `httpx`, `pydantic`, `pydantic-settings`, `structlog`) and `pyproject.toml:43-49` (`[project.optional-dependencies].dev` = `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `ruff`). No `opentelemetry-api` / `-sdk` / `-exporter-otlp` / `-instrumentation-httpx`.
- **No tracing code in `src/`:** a case-insensitive grep for `opentelemetry | otel | tracer | start_as_current_span | set_attribute` over `src/` returns zero tracing hits (the only "span"-adjacent matches are the word `lifespan` at `src/swisstopo_mcp/api_client.py:80,82,98` and `src/swisstopo_mcp/server.py:28,44`). There is no observability module and no `traced_tool` decorator; the only cross-cutting instrumentation is the structlog decorator at `src/swisstopo_mcp/logging_config.py:63-91` (OBS-003).
- **No auto-instrumentation of the HTTP client, so upstream latency is untraced:** `src/swisstopo_mcp/api_client.py:88-99` builds the shared `httpx.AsyncClient` with no `HTTPXClientInstrumentor().instrument()` call, and the retry wrapper at `src/swisstopo_mcp/api_client.py:146-187` records nothing beyond a debug log line (`api_client.py:169`). Backend hop latency to `api3.geo.admin.ch`, `geodesy.geo.admin.ch`, `overpass.osm.ch` and `openplzapi.org` is therefore invisible as a child span.
- **No OTLP configuration in any deployment artifact:** a grep for `OTEL_EXPORTER_OTLP_ENDPOINT | OTEL_SERVICE_NAME | OTEL_RESOURCE_ATTRIBUTES` over `deploy/`, `Dockerfile` and `docs/` returns zero hits. `deploy/kubernetes.yaml:39-44` sets only `SWISSTOPO_HTTP_HOST` and `SWISSTOPO_ALLOWED_ORIGINS`; the container has liveness/readiness probes on `/healthz` (`deploy/kubernetes.yaml:50-60`) but no telemetry sidecar, collector reference or service-name tag.
- **No observability plan in the docs either:** a grep for `observab|metric|prometheus|trace|tracing|monitor` over `deploy/`, `docs/`, `README.md` and `SECURITY.md` returns a single unrelated hit (`docs/geodaten-erweiterung-phase1.md:280`, about error messages vs stacktraces). `docs/roadmap.md` lists no tracing item in any phase.

Note: this check was not part of the 2026-05-29 run (36 checks, OBS-006 absent from `verification-results.json`), so this is a first evaluation rather than a regression.

### Expected Behavior

Per the check's Pass Criteria:

- OpenTelemetry SDK installed and initialised
- TracerProvider configured with an OTLP exporter
- Auto-instrumentation active for the HTTP client (httpx)
- One span per tool call carrying `mcp.tool.name`, `mcp.user.id`, `mcp.tool.result.is_error`
- Backend API calls appear automatically as child spans
- No sensitive data in span attributes (no PII, no tokens, no raw argument contents)
- OTLP endpoint configurable via env var
- Service name and environment tag set explicitly

### Evidence

- File: `pyproject.toml:31-40`, `pyproject.toml:43-49` — dependency lists; no `opentelemetry-*` package.
- Grep over `src/`: zero hits for `opentelemetry|otel|tracer|start_as_current_span|set_attribute`.
- File: `src/swisstopo_mcp/api_client.py:88-99` — shared `httpx.AsyncClient` created without instrumentation; `src/swisstopo_mcp/api_client.py:146-187` — retry wrapper, only a debug log at `:169`.
- File: `deploy/kubernetes.yaml:39-44` (env vars: none OTEL), `deploy/kubernetes.yaml:50-60` (probes only).
- File: `src/swisstopo_mcp/logging_config.py:83` — per-call `duration_ms` in unaggregated stderr JSON logs, the only latency signal that exists.
- File: `src/swisstopo_mcp/server.py:657-683` — the HTTP app under audit; `docs/roadmap.md` — no tracing item in any phase.

### Risk Description

Two of the three workflows this check enables are weak for this server, and one is genuinely missing:

- **User-behaviour forensics (weak here).** The server is unauthenticated, read-only, public open data. There is no user identity to attach to a span and no read+exfiltrate pattern to detect. This mitigates severity but does not remove the finding.
- **P99 / slow-tool identification (partially covered).** structlog already emits per-call `duration_ms` (`src/swisstopo_mcp/logging_config.py:83`), but only as unaggregated JSON on stderr, so there is no way to compute a percentile or compare tools without shipping and parsing container logs by hand.
- **Backend-bottleneck attribution (missing, and this is the real gap).** The server fans out to four independent upstream APIs, three of which — `overpass.osm.ch`, `openplzapi.org`, `geodienste.ch` — are community or third-party endpoints with known transient 503s already handled in `src/swisstopo_mcp/api_client.py:130-138`. When a tool call is slow in production there is currently no way to tell whether the latency is in the server, in `api3.geo.admin.ch`, or in Overpass. The operator's only recourse is to reproduce the call by hand and hope the condition persists — which for transient upstream degradation it usually does not. Because the retry wrapper (`api_client.py:146-187`) silently absorbs retries, a request that took three attempts and 20 s is indistinguishable in the logs from one that took 20 s in a single attempt.

### Remediation

Given structlog already emits `duration_ms`, this is an increment rather than a rebuild.

1. `pyproject.toml:31-40`: add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` and `opentelemetry-instrumentation-httpx` to the dependencies (or to an `otel` extra if the stdio users should not pay for them).
2. Add `src/swisstopo_mcp/observability.py` with a `setup_tracing()` that builds a `Resource` from `OTEL_SERVICE_NAME` (default `swisstopo-mcp`) plus `deployment.environment`, installs a `TracerProvider` with a `BatchSpanProcessor(OTLPSpanExporter())`, and calls `HTTPXClientInstrumentor().instrument()`. Make it a no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, so the local stdio path is unaffected.
3. Call `setup_tracing()` from the lifespan at `src/swisstopo_mcp/server.py:25-38`, before `create_shared_client()` — the shared client must be created after instrumentation for the httpx auto-instrumentation to attach, which is why the ordering matters here specifically.
4. Wrap the existing structlog tool decorator at `src/swisstopo_mcp/logging_config.py:63-91` in a span rather than adding a second decorator: it already knows the tool name, the duration and the `is_error` outcome, so set `mcp.tool.name` and `mcp.tool.result.is_error` from the values it already has. Do **not** add `mcp.user.id` — there is no authenticated identity (`auth_model=none`) — and do not put tool arguments into attributes; coordinates and addresses are user input and belong nowhere near an observability backend (SEC-023 synergy).
5. `deploy/kubernetes.yaml:39-44`: add `OTEL_SERVICE_NAME=swisstopo-mcp`, `OTEL_EXPORTER_OTLP_ENDPOINT` pointing at the cluster collector, and `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production`. Document the variables in `.env.example` and `docs/deployment.md`.
6. Add a tracing item to `docs/roadmap.md` so the operational plan matches the deployment posture, and a unit test asserting that `setup_tracing()` is inert without an OTLP endpoint (so CI and stdio users see no behaviour change).

### Effort Estimate

M (1-3d) — SDK setup, one new module, decorator extension, deployment wiring and a collector endpoint to point at.
