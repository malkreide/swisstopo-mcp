# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Geodaten-Erweiterung — 3 new tools consolidating 4 data sources** (13 → 16
  tools, deliberately under the 18-tool budget via a façade pattern; see
  [`docs/geodaten-erweiterung-phase1.md`](docs/geodaten-erweiterung-phase1.md)
  for the Phase-1 live probe and architecture decisions):
  - `query_geodata(layer, point|bbox|commune, …)` — one façade over the amtliches
    Strassenverzeichnis (`strassenverzeichnis`), interkantonale Basisgeodaten via
    the geodienste.ch OGC API Features (`geodienste:<topic>:<canton>`), and the
    bundesweite ÖREB-Kataster availability layer (`oereb-verfuegbarkeit`).
  - `list_available_layers(source?, canton?, free_only?)` — discovery tool for the
    façade; only surfaces geodienste datasets that are free without a contract.
  - `query_osm_features(feature_type, area, radius_m)` — OpenStreetMap POIs
    (schools, playgrounds, …) via Overpass (`overpass.osm.ch`), ODbL. Kept
    separate because of Overpass' distinct failure semantics, licence and
    rate-limits.
- Shared `request_with_retry` HTTP wrapper: exponential backoff (2s/4s/8s) on
  429/5xx and network/timeout errors, fail-fast on other 4xx. `geo_admin_request`
  and `stac_request` now route through it (resilience default).
- Egress allow-list extended with `geodienste.ch` and `overpass.osm.ch`
  (`docs/network-egress.md`).

### Known findings (Phase-1 live probe, 2026-07-19)
- **api3 default SR is LV03 (`sr=21781`), not LV95** — coordinate queries pass
  `sr=2056` explicitly to avoid confusing the 6-digit LV03/LV95 pairs.
- **geodienste `opendata_terms_*` is free text, not a boolean** — the free-access
  check requires `contract_required_* == false` *and* an `opendata_terms_*`
  string starting with "Freie Nutzung".
- **Overpass returns errors as XML/HTML even for `[out:json]`**, and signals
  server-side timeouts as HTTP 200 with an embedded `remark`. `query_osm_features`
  inspects the body before parsing JSON and degrades gracefully.
- **ÖREB is cantonally fragmented**: no nationwide extract API exists — only the
  federal availability layer (`ch.swisstopo-vd.stand-oerebkataster`) is nationwide.
  Grundstück-level extracts stay with the existing ZH/BE `get_oereb_extract` tool.
- Centralised configuration via `pydantic-settings` (`config.py` + `.env.example`)
  for transport/host/port/origins/log level (audit finding ARCH-004).
- Secret-scanning CI workflow (gitleaks) and `.env.example` (audit finding ARCH-005).
- `Context` injection with progress/info logging for the longer-running tools
  `elevation_profile` and `get_oereb_extract` (audit finding SDK-003).
- README "Sessions & Authentication", "Error handling" and "Tool workflows"
  sections (DE/EN) documenting the session model (SEC-009), the execution- vs
  protocol-error contract (OBS-001), and tool-chaining workflows (ARCH-007).
- `<use_case>` / `<important_notes>` tags on all 13 tool descriptions
  (audit finding ARCH-002).
- Hardened container deployment (SEC-007): multi-stage `Dockerfile` (non-root
  UID 10001), `deploy/kubernetes.yaml` (`runAsNonRoot` / `readOnlyRootFilesystem`
  / dropped capabilities / seccomp `RuntimeDefault`) plus an egress
  `NetworkPolicy` (also covers the network layer of SEC-021), a `/healthz`
  liveness endpoint, and `docs/deployment.md`.
- Horizontal-scaling guidance (SCALE-002): the Kubernetes manifest defaults to
  `replicas: 1` with a documented sticky-session example
  (`deploy/ingress-sticky-sessions.yaml`) and a "Scaling out" doc section.
- Structured logging via `structlog`, rendered as JSON to **stderr**; all tool
  handlers log `tool_invoked` / `tool_completed` / `tool_failed` with a bound
  correlation id and duration; level via `SWISSTOPO_LOG_LEVEL` (OBS-003).
- CORS on the Streamable-HTTP app with `expose_headers: Mcp-Session-Id` (SDK-004).
- `.github/dependabot.yml` for monthly pip + GitHub-Actions update PRs (ARCH-012).
- `docs/roadmap.md` and a "Security & Compliance" README section — phase
  declaration, Lethal-Trifecta assessment, MCP-primitives rationale
  (OPS-003 / SEC-019 / ARCH-008).

### Changed
- **All 13 tools now return a structured `ToolResponse` envelope** instead of a
  plain string (SDK-002): `results` / `count` / `match_type` plus `source` /
  `license` / `provenance` / `retrieved_at` and a human-readable Markdown
  `summary`. FastMCP emits structured content with an output schema; the
  per-response attribution also satisfies OGD-CH licensing (CH-004).
- HTTP client is created once at startup via a FastMCP lifespan and reused
  across all tool calls (connection pooling) instead of per call (SDK-001).
- Outbound requests no longer follow redirects (`follow_redirects=False`),
  reducing redirect-based SSRF surface (SEC-004/005).
- All tool input models use Pydantic `strict=True` plus whitelist `pattern`
  constraints on free-text fields (SEC-018).
- Unexpected exceptions no longer leak their raw text to the client; intentional
  validation messages are preserved (OBS-002).
- Empty geocoding results return an actionable hint instead of a bare
  "no results" string (ARCH-003).
- Pinned `mcp[cli]` to the `1.x` major; CI now also runs on `master`
  (ARCH-012 / CI trigger fix).

### Security
- Explicit code-layer egress allow-list (`ALLOWED_HOSTS` frozenset +
  `assert_host_allowed`) checked before every outbound request; documented in
  `docs/network-egress.md` (SEC-021).


## [0.1.0] - 2026-04-02

### Added
- Initial release with 13 tools across 6 API families
- **REST API** (4 tools): Layer search, feature identification, attribute search, feature details
- **Geocoding** (2 tools): Address geocoding, reverse geocoding
- **Height** (2 tools): Point height, elevation profile
- **STAC** (2 tools): Geodata catalog search, collection details
- **WMTS** (1 tool): Map URL generation
- **OEREB** (2 tools): Property ID (EGRID) lookup, cadastral extract
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (DE/EN)
