# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **Audit remediation batch 1 — five findings closed** (SEC-004, SEC-018,
  SDK-002, ARCH-004, ARCH-012). No breaking changes for clients.
  - **SEC-004 (critical):** `assert_host_allowed` only ever checked the
    hostname, so an allow-listed host over cleartext `http://` passed. It now
    validates the scheme first and adds a resolved-IP guard that blocks any
    allow-listed name answering with a private or link-local address. The guard
    hangs off the same function, so it also covers the two direct-client call
    sites in `oereb.py`. Resolution is cached per host; a resolution *failure*
    is deliberately non-fatal so httpx surfaces the real connection error.
  - **SEC-018:** `validate_sr()` existed but was never called — an arbitrary
    `sr` int was forwarded straight upstream. It is now wired into the three
    `sr` fields, and length bounds were added to the identifier fields.
  - **ARCH-004:** `transport` and `oereb_cantons` became `Settings` fields.
    `--http` still wins on the command line, but `SWISSTOPO_TRANSPORT` is the
    deployment path, and `oereb.py` no longer reads `os.environ` directly —
    which had contradicted `config.py`'s own docstring.
  - **ARCH-012:** both READMEs now name the concrete negotiated protocol
    version (2025-11-25) and an update policy, and
    `tests/test_protocol_version.py` fails if an SDK bump moves it.

### Changed
- **The OEREB canton list is read once at startup instead of on every call.**
  This is what ARCH-004 asks for, but it means changing
  `SWISSTOPO_OEREB_CANTONS` now requires a restart.
- All 23 tool annotations use the typed `ToolAnnotations` instead of plain
  dicts, and a `mypy src/` gate runs in CI (SDK-002). Four handlers in
  `rest_api.py` were annotated `-> str` while returning `ToolResponse`;
  nothing caught it, hence the gate.
- **Fixed the broken HTTP transport (SDK-004 / SCALE-001).**
  `TransportSecuritySettings` is now passed to `FastMCP()`, so the SDK's
  DNS-rebinding protection is told the deployment's real hosts and origins
  instead of falling back to its loopback-only default. Before this, a
  deployment behind an ingress answered **403** to a configured origin and
  **421** to the forwarded `Host` on every `/mcp` request, while `/healthz`
  returned 200 — so the Kubernetes readiness probe stayed green and the
  failure was invisible.
  - New `SWISSTOPO_ALLOWED_HOSTS` setting, documented in `.env.example`,
    `docs/deployment.md` and `deploy/kubernetes.yaml`.
  - Loopback entries use the SDK's `:*` wildcard-port form, because `--port`
    overrides the configured port at runtime.
  - DNS-rebinding protection stays **enabled** — SEC-005 depends on it. The fix
    is to name the right hosts, never to switch the check off. Unconfigured
    origins and hosts are still rejected.
  - `tests/test_http_app.py` now drives the ASGI app end to end. Its previous
    tests inspected middleware kwargs and passed throughout the outage.
- **Re-audit run `2026-07-27T125314-Z` against the 68-check catalogue**
  (`audits/`). 44 checks applicable, 22 pass / 20 partial / 2 fail;
  `production_ready: false`, blocked on SEC-022. This is **not** comparable to
  the previous run's 36/36: the old profile still said `is_cloud_deployed:
  false` although the Dockerfile and `deploy/kubernetes.yaml` had been added as
  remediation for SEC-007/SCALE-002, so 8 checks — most of SCALE among them —
  had never been evaluated. The checks were also re-verified from source rather
  than inherited.
- **Highest-impact open finding (SDK-004 / SCALE-001, pre-existing):**
  `transport_security` is never passed to `FastMCP()`, so the SDK keeps its
  localhost-only allow-list. Reproduced against a running instance: `POST /mcp`
  returns **403** for an origin configured via `SWISSTOPO_ALLOWED_ORIGINS` and
  **421** for the `Host` the shipped Ingress forwards, while `/healthz` returns
  200. The HTTP transport is unusable in any non-localhost deployment and the
  Kubernetes probe masks it.
- Fixed, in this release, the three findings this consolidation itself caused:
  - `SwissPointInput` carried an empty `model_config`, so the base class
    accepted extra fields and coerced strings. Every shipped subclass
    re-declared the strict config, so no tool was permissive — but the base was
    a trap (SEC-018).
  - The ARE, swissBOUNDARIES3D and REFRAME sources set `source` but never
    `license`, so ARE data silently inherited `SWISSTOPO_LICENSE` despite coming
    from a different federal office. Added the missing licence constants and the
    `license` parameter that `ToolResponse.error()` lacked entirely (CH-004).
  - Stale `18-tool budget` references survived the raise to 25 in
    `geodata.py` and `docs/geodaten-erweiterung-phase1.md` (ARCH-006).

### Added
- **Three convenience tools ported from `swiss-geodata-mcp`** (20 → 23 tools),
  completing PR 3 of `docs/merge-plan-swiss-geodata-mcp.md`:
  - `swisstopo_zoning_at` — harmonised building zone at a point
    (`ch.are.bauzonen`) in one call, without a preceding layer lookup. The ARE
    layer is a federal synthesis and **not legally binding**; that caveat is
    carried on every result record, not just in the prose summary, so a client
    reading `results` cannot lose it.
  - `swisstopo_municipality_at` — municipality, canton and official BFS commune
    number at a point (swissBOUNDARIES3D). The layer carries one polygon per
    historical year, so the current-year record is selected.
  - `swisstopo_layer_info` — a layer's queryable fields plus its legend,
    revealing which `search_field` values `swisstopo_find_features` accepts. A
    missing legend is not fatal: the fields are still returned.
- **Tool budget raised from 20 to 25** to accommodate the consolidation. The
  README stated 18 while the CHANGELOG stated 20; both now say 25.
  These three tools also address the open remediation on audit finding
  ARCH-007, which asks for higher-level tools that resolve a common case in a
  single call instead of a discovery chain.
- `bfs_commune_number` is normalised to an integer across tools. The upstream
  layers disagree — `ch.are.bauzonen` serves it as a string, swissBOUNDARIES3D
  as an int — and it is the join key to `swiss-statistics-mcp` and
  `zurich-opendata-mcp`, so it must not depend on which tool produced it.
- **LV95 coordinate input on the point-based tools** (`swisstopo_get_height`,
  `swisstopo_identify_features`, `swisstopo_get_egrid`). Each now takes *either*
  `lat`/`lon` (WGS84) *or* `easting`/`northing` (LV95, EPSG:2056) via the shared
  `SwissPointInput` contract; supplying both, neither, or half a pair is a
  validation error. `swisstopo_elevation_profile` gains
  `coordinate_system="lv95"` for LV95 support points.
  This is PR 2 of `docs/merge-plan-swiss-geodata-mcp.md` and the prerequisite
  for migrating LV95-native clients off `swiss-geodata-mcp`.
  - Passing WGS84 degrees in the LV95 fields is rejected with a message naming
    the mistake, rather than being converted into a point in the wrong place.
  - Height results now carry both `lat`/`lon` and `easting`/`northing`.
  - Existing `lat`/`lon` callers are unaffected.
- **`swisstopo_convert_coordinates` — official LV95<->WGS84 transformation via
  the swisstopo REFRAME service** (19 → 20 tools, exactly at the 20-tool
  budget). This is the first step of the `swiss-geodata-mcp` consolidation
  described in `docs/merge-plan-swiss-geodata-mcp.md`, and the one capability
  that server had which this one lacked.
  - New egress host `geodesy.geo.admin.ch` (SEC-021 allow-list + docs).
  - The input validator rejects swapped axes and out-of-system magnitudes
    instead of silently returning a point in the wrong place — REFRAME labels
    both inputs `easting`/`northing`, so for `wgs84_to_lv95` the easting
    carries the *longitude*, reversing the `lat`/`lon` order used elsewhere.
  - `lv95_to_wgs84` results additionally carry `lat`/`lon` so they can be passed
    straight to the other tools.

### Changed
- The local polynomial helpers (`wgs84_to_lv95` / `lv95_to_wgs84`) remain the
  internal fast path for every height/profile/identify call and were **not**
  replaced by REFRAME. Measured against the official service at four points
  across Switzerland they deviate by 0.05–0.20 m — well below the tolerance
  those tools operate at — so routing them through the network would have added
  a roundtrip per call for irrelevant precision. A `live`-marked test guards the
  assumption by failing if the deviation ever exceeds one metre.

### Fixed
- **`sr=2056` produced silently wrong height, profile and identify results.**
  The parameter was meant to select the input coordinate system, but the WGS84
  field bounds rejected LV95 magnitudes, so the only way to reach the branch was
  to pass WGS84 degrees *with* `sr=2056` — which sent those degrees upstream
  labelled as LV95 metres. `sr` now accepts `4326` only and points at the new
  `easting`/`northing` fields, turning a wrong answer into an explicit error.
- `server.json` declared version `0.1.3` while the package was at `0.2.0`, which
  would have published a wrong version to the MCP Registry.

## [0.2.0] - 2026-07-20

### Added
- **OpenPLZ extension — 3 new tools for the administrative address level**
  (16 → 19 tools, one under the 20-tool budget). This adds the layer swisstopo
  geodata does not cover — the amtliche hierarchy **PLZ → Ort → Gemeinde →
  Bezirk → Kanton** — and, crucially, exposes the **BFS commune number**
  (`bfs_commune_number`) as a named top-level field on every commune-bearing
  response. That number is the official join key to `swiss-statistics-mcp`
  (BFS STAT-TAB) and `zurich-opendata-mcp`, turning the geodata wrapper into a
  semantic connector at the commune level.
  - `lookup_postal_code(postal_code)` — Swiss postal code → locality, commune
    (+BFS number), district, canton.
  - `find_commune(name | bfs_number | canton | district)` — resolve a commune in
    both directions (name ↔ BFS number) or list all communes of a canton /
    district. Canton accepts an abbreviation (`ZH`) or a numeric key (`1`);
    abbreviation→key resolution happens server-side.
  - `search_address(query)` — full-text search over Swiss streets and localities.
- New source module `openplz.py` and `test_openplz.py`. Source: OpenPLZ API
  (openplzapi.org), data from the BFS municipal directory + swisstopo street
  directory (Swiss OGD). Egress allow-list extended with `openplzapi.org`.
- Separate attribution for OpenPLZ (`OPENPLZ_SOURCE` / `OPENPLZ_LICENSE`), kept
  distinct from the swisstopo geo.admin OGD attribution — two sources, two
  licences, not conflated.

### Known findings (OpenPLZ live probe, 2026-07-20)
- **Abbreviation-vs-key trap:** path params are the numeric `key`, not the canton
  abbreviation. `/Cantons/ZH/Districts` returns **HTTP 200 with `[]`** (not an
  error) — the same silent-empty pattern as an unknown PLZ (`?postalCode=9999` →
  `200 []`). An empty OpenPLZ list is almost never proof of "does not exist"; it
  is usually a wrong path parameter. Tools resolve `ZH`→`1` from the live
  `/Cantons` list and annotate every empty result with an explanatory note.
- **Pagination cap:** list endpoints paginate with `pageSize` default 10 and a
  **hard maximum of 50** (`pageSize=100` → HTTP 400). Totals live in the
  `x-total-count` header. `find_commune` iterates pages so a canton with 160
  communes (e.g. ZH) returns all 160, not the first 10.
- **Umlauts must be URL-encoded:** a raw `?name=Zürich` returns HTTP 400;
  `%C3%BC` returns 200. httpx encodes `params` dicts automatically.
- **`historicalCode` ≠ the join key:** for communes it differs from `key` (it is
  the historized-directory record id). The join key is the current `key`;
  `historicalCode` is intentionally not surfaced as a top-level field.
- **No OpenPLZ bulk dump** (only a Swagger UI); underlying dumps live upstream at
  BFS/swisstopo. Architecture A (live-API-only) is adequate for a lookup connector.
- **Reality-check passed:** `/Cantons` returns exactly 26; sample BFS numbers
  match (Zürich 261, Winterthur 230, Uster 198).

### Architecture decision
- **ARCH A (live-API-only)** for the OpenPLZ source: all required endpoints are
  stable, fast (~0.5–1.4 s) and unauthenticated; no dump layer is warranted for a
  lookup connector.

## [0.1.x — pre-0.2.0 Unreleased work]

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
